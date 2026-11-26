"""Run a year of engagements under one design. The platform designs call the real policy checks,
address allocation, budget decisions and promotion gate; the hand-built designs skip what a person
would skip, at the rates in config/lab.yaml."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .. import config, gate, ipam, policy
from ..budget import Verdict, decide
from .world import Luck, draw


class Design(StrEnum):
    ad_hoc = "ad_hoc"  # each team gets a hand-built subscription through an IT ticket
    shared = "shared"  # one shared subscription and Azure OpenAI resource for every PoV
    platform = "platform"  # this repository
    no_budgets = "platform_no_budgets"  # ablation: gateway does not enforce budgets
    no_gate = "platform_no_gate"  # ablation: promotion without the SLO/eval gate

    @property
    def label(self) -> str:
        return {
            "ad_hoc": "Hand-built per PoV (ticket)",
            "shared": "One shared subscription",
            "platform": "Platform",
            "platform_no_budgets": "Platform without budgets",
            "platform_no_gate": "Platform without promotion gate",
        }[self.value]

    @property
    def on_platform(self) -> bool:
        return self.value.startswith("platform")


DESIGNS = [Design.ad_hoc, Design.shared, Design.platform, Design.no_budgets, Design.no_gate]


@dataclass
class Outcome:
    env_days: float = 0.0
    policy_block: bool = False
    violation: bool = False  # a request against residency, model or consent rules reached Azure
    isolation_incident: bool = False
    security_finding: bool = False
    unapproved_overrun: float = 0.0
    idle_spend: float = 0.0
    blocked_days: int = 0
    weeks_to_scaled: float | None = None
    incidents: int = 0
    bad_in_prod: int = 0
    gate_stops: int = 0
    incident_minutes: list[float] = field(default_factory=list)
    hours: float = 0.0


def spend(
    luck: Luck, budget: float, days: int, usage: float, cfg: dict[str, Any], enforce: bool, runaway: bool, o: Outcome
) -> None:
    """Day by day spend of one stage. With enforcement the gateway's real budget decision runs."""
    plat = config.platform()
    daily = budget * usage / days
    spent, limit, factor = 0.0, budget, 1.0
    fixed_runaway = False
    noticed = cfg["engagement"]["runaway_noticed_days"]
    for day in range(days):
        if runaway and luck.runaway_day is not None and day >= luck.runaway_day and not fixed_runaway:
            factor = luck.runaway_factor
            if not enforce and day >= luck.runaway_day + noticed:  # the invoice review finds it
                fixed_runaway, factor = True, 1.0
                o.hours += 1
        cost = daily * factor
        if enforce and decide(spent, limit, cost, plat) == Verdict.block:
            if factor > 1:  # the owner is told and stops the loop or rotates the leaked key
                fixed_runaway, factor = True, 1.0
                o.hours += 1
            else:  # real demand outgrew the budget: the owner approves more
                limit *= cfg["engagement"]["legit_overrun_raise"]
                o.hours += cfg["engineer_hours"]["budget_raise"]
            o.blocked_days += 1
            continue
        spent += cost
    if not enforce:
        o.unapproved_overrun += max(0.0, spent - budget)


def promote(
    luck: Luck, stage: str, use_gate: bool, cfg: dict[str, Any], o: Outcome, current: float | None
) -> tuple[float, bool, float]:
    """Return (weeks spent on gate fixes, whether the promoted release is bad, its eval score).
    `current` is the eval score of the release already running in the previous stage."""
    attempts = luck.releases[stage]
    if not use_gate:
        o.hours += cfg["engineer_hours"]["promotion"]
        return 0.0, attempts[0].bad, attempts[0].eval_score
    weeks = 0.0
    for k, r in enumerate(attempts):
        m = gate.Metrics(
            r.requests, r.p95_latency_ms, r.error_rate, r.eval_score, r.cost_per_1k_requests_eur, r.slo_budget_remaining
        )
        o.hours += cfg["engineer_hours"]["promotion"]
        if gate.evaluate(stage, m, current_eval=current).promote or k == len(attempts) - 1:
            return weeks, r.bad, r.eval_score
        o.gate_stops += 1
        weeks += cfg["weeks"]["gate_fix"]
        o.hours += cfg["engineer_hours"]["gate_fix"]
    return weeks, attempts[-1].bad, attempts[-1].eval_score


def simulate(luck: Luck, d: Design, live: dict[str, str], cfg: dict[str, Any]) -> Outcome:
    o = Outcome()
    h = cfg["engineer_hours"]
    req = luck.request
    findings = policy.errors(policy.check(req, today=req.start))
    days = (req.expires - req.start).days

    # --- getting an environment -------------------------------------------------------------------
    if d.on_platform:
        o.env_days = luck.env_days["platform"]
        o.hours += h["platform_review"]
        if findings:
            o.policy_block = True
            o.env_days += cfg["days"]["policy_fix"]
            o.hours += h["policy_fix"]
        space = config.platform()["hub"]
        live.update(
            ipam.allocate(live, [req.id], space["address_space"], [space["hub_prefix"]], space["spoke_prefix_length"])
        )
    elif d == Design.ad_hoc:
        o.env_days = luck.env_days["ticket"]
        o.hours += h["hand_build"]
        o.violation = bool(findings)
        o.security_finding = luck.public_endpoint
        o.isolation_incident = luck.reuses_key
        # hand-picked ranges cluster on a few popular /22s; a clash breaks peering until someone re-plans
        pick = f"10.{64 + luck.cidr_pick // 64}.{(luck.cidr_pick % 64) * 4}.0/22"
        if ipam.overlaps([*live.values(), pick]):
            o.env_days += cfg["days"]["cidr_clash"]
            o.hours += 8
        live[req.id] = pick
    else:  # shared
        o.env_days = luck.env_days["shared"]
        o.hours += h["shared_onboard"]
        o.violation = bool(findings)
        o.isolation_incident = luck.cross_client_mix and req.classification.value in (
            "confidential",
            "client-restricted",
        )

    # --- spending through the PoV (and the pilot, if it wins one) ------------------------------
    enforce = d in (Design.platform, Design.no_gate)
    spend(luck, req.budget_eur, days, luck.usage, cfg, enforce, True, o)
    if luck.wins_pilot:
        spend(luck, req.budget_eur * 3, round(luck.pilot_weeks * 7), luck.usage, cfg, enforce, False, o)

    # --- after the PoV ends ---------------------------------------------------------------------------
    if d == Design.ad_hoc:
        if luck.forgets_teardown and not luck.wins_pilot:
            o.idle_spend = cfg["idle_eur_per_day"] * luck.noticed_after
        elif not luck.wins_pilot:
            o.hours += h["hand_teardown"]
    # on the platform the expiry date tears it down; in the shared design there is nothing to tear down

    # --- from PoV to production ---------------------------------------------------------------------
    use_gate = d in (Design.platform, Design.no_budgets)
    if luck.wins_pilot:
        extra = 0.0
        if d == Design.ad_hoc:
            extra, o.hours = luck.rebuild_weeks, o.hours + h["rebuild"]
        elif d == Design.shared:
            extra, o.hours = luck.migrate_weeks, o.hours + h["migrate"]
        fix_pilot, bad_pilot, pilot_eval = promote(luck, "pilot", use_gate, cfg, o, None)
        if luck.wins_scaled:
            fix_scaled, bad_scaled, _ = promote(luck, "scaled", use_gate, cfg, o, pilot_eval)
            o.weeks_to_scaled = extra + fix_pilot + luck.pilot_weeks + fix_scaled
            o.bad_in_prod = int(bad_scaled)
            n = luck.natural_incidents + (cfg["incidents"]["bad_release_incidents"] if bad_scaled else 0)
            for burn, user, fix in luck.incidents[:n]:
                o.incidents += 1
                o.incident_minutes.append((burn if d.on_platform else user) + fix)
                o.hours += h["incident"]
        elif bad_pilot:
            o.bad_in_prod = 1
    return o


METRICS = [
    ("env_days", "Days to a working PoV environment (median)", "days", "lower"),
    ("violations", "Requests against residency, model or consent rules that reached Azure", "per year", "lower"),
    ("policy_blocks", "Requests stopped by the policy check and fixed first", "per year", "info"),
    ("isolation", "Client-data isolation incidents", "per year", "lower"),
    ("security", "Public endpoints found on client environments", "per year", "lower"),
    ("overrun_keur", "Unapproved spend over budget", "k€ per year", "lower"),
    ("idle_keur", "Spend on forgotten environments", "k€ per year", "lower"),
    ("blocked_days", "Days a PoV waited on a budget decision", "per year", "info"),
    ("weeks_to_scaled", "PoV end to scaled go-live (median)", "weeks", "lower"),
    ("bad_in_prod", "Regressed releases that reached production", "per year", "lower"),
    ("incidents", "Production incidents, first 6 months at scale", "per year", "lower"),
    ("mttr", "Time to restore (mean)", "minutes", "lower"),
    ("engineer_hours", "Engineer time, incl. running the platform", "hours per year", "lower"),
]


def year(seed: int, d: Design, cfg: dict[str, Any] | None = None) -> dict[str, float]:
    c = cfg or config.load("lab")
    lucks = [draw(seed, c, i) for i in range(c["year"]["engagements"])]
    lucks.sort(key=lambda lk: lk.request.start)
    live: dict[str, str] = {}
    ends: dict[str, object] = {}
    outs = []
    for lk in lucks:
        # environments that have ended give their address range back
        for eid in [k for k, end in ends.items() if end < lk.request.start]:
            live.pop(eid, None)
            ends.pop(eid)
        outs.append(simulate(lk, d, live, c))
        ends[lk.request.id] = lk.request.expires
    minutes = [m for o in outs for m in o.incident_minutes]
    scaled = [o.weeks_to_scaled for o in outs if o.weeks_to_scaled is not None]
    hours = sum(o.hours for o in outs) + (c["engineer_hours"]["platform_ops_per_month"] * 12 if d.on_platform else 0)
    return {
        "env_days": statistics.median(o.env_days for o in outs),
        "violations": sum(o.violation for o in outs),
        "policy_blocks": sum(o.policy_block for o in outs),
        "isolation": sum(o.isolation_incident for o in outs),
        "security": sum(o.security_finding for o in outs),
        "overrun_keur": sum(o.unapproved_overrun for o in outs) / 1000,
        "idle_keur": sum(o.idle_spend for o in outs) / 1000,
        "blocked_days": sum(o.blocked_days for o in outs),
        "weeks_to_scaled": statistics.median(scaled) if scaled else 0.0,
        "bad_in_prod": sum(o.bad_in_prod for o in outs),
        "incidents": sum(o.incidents for o in outs),
        "mttr": statistics.fmean(minutes) if minutes else 0.0,
        "engineer_hours": hours,
        "scaled": len(scaled),
        "gate_stops": sum(o.gate_stops for o in outs),
    }
