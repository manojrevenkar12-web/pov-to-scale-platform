"""The luck of one engagement, drawn once per seed and shared by every design."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from .. import config
from ..engagement import Engagement


@dataclass
class Release:
    """The release put forward for one promotion. `bad` releases carry a regression."""

    bad: bool
    requests: int
    p95_latency_ms: float
    error_rate: float
    eval_score: float
    cost_per_1k_requests_eur: float
    slo_budget_remaining: float


@dataclass
class Luck:
    index: int
    client: str
    request: Engagement  # what the team asks for, possibly against the rules
    fixed: Engagement  # the same request once a policy finding is fixed
    usage: float  # planned spend / budget
    runaway_day: int | None
    runaway_factor: float
    wins_pilot: bool
    wins_scaled: bool
    pilot_weeks: float
    forgets_teardown: bool
    noticed_after: int
    public_endpoint: bool
    reuses_key: bool
    cidr_pick: int
    cross_client_mix: bool
    env_days: dict[str, float]
    rebuild_weeks: float
    migrate_weeks: float
    releases: dict[str, list[Release]] = field(default_factory=dict)  # stage -> attempts in order
    incidents: list[tuple[float, float, float]] = field(default_factory=list)  # (burn detect, user detect, fix)
    natural_incidents: int = 0  # incidents in the first six months at scale, before any bad release


def _u(rng: random.Random, lo_hi: list[float]) -> float:
    return rng.uniform(lo_hi[0], lo_hi[1])


def _release(rng: random.Random, stage: str, cfg: dict[str, Any], gate: dict[str, Any]) -> Release:
    """Draw a release's true quality, then what the observation window measures (with noise)."""
    t = gate["stages"][stage]
    bad = rng.random() < cfg["release"]["bad"]
    noise = cfg["release"]["noise"]

    def around(limit: float, good_share: float, bad_share: float) -> float:
        share = bad_share if bad else good_share
        return limit * share * (1 + rng.gauss(0, noise))

    eval_true = t["eval_score"] + (-0.05 if bad else 0.06)

    return Release(
        bad=bad,
        requests=int(rng.uniform(800, 20000)),
        p95_latency_ms=around(t["p95_latency_ms"], 0.65, 1.25),
        error_rate=max(0.0, around(t["error_rate"], 0.4, 1.6)),
        eval_score=min(0.99, eval_true + rng.gauss(0, cfg["release"]["eval_noise"])),
        cost_per_1k_requests_eur=around(t["cost_per_1k_requests_eur"], 0.6, 1.2),
        slo_budget_remaining=max(0.0, min(1.0, rng.gauss(0.8 if not bad else 0.35, 0.15))),
    )


def draw(seed: int, cfg: dict[str, Any], i: int) -> Luck:
    rng = random.Random(seed * 1_000_003 + i)
    y, e, people = cfg["year"], cfg["engagement"], cfg["people"]
    plat = config.platform()
    start = date.fromisoformat(str(y["start"])) + timedelta(days=rng.randrange(0, 365))
    classes = list(e["classification"])
    cls = rng.choices(classes, weights=[e["classification"][c] for c in classes])[0]
    eu_regions = plat["regions"]["eu"]
    region = rng.choice(["germanywestcentral", "swedencentral", "westeurope"])
    models = [{"model": "gpt-4o-mini", "tokens_per_minute": 60000}, {"model": "gpt-4o", "tokens_per_minute": 40000}]
    weeks = _u(rng, e["pov_weeks"])
    budget = round(_u(rng, e["budget_eur"]), -2)
    fine_tuning = rng.random() < e["fine_tuning"]
    consent = rng.random() > e["bad_request"]["fine_tune_without_consent"] / max(e["fine_tuning"], 1e-9)
    bad_region = rng.random() < e["bad_request"]["non_eu_region"]
    bad_model = rng.random() < e["bad_request"]["model_not_in_region"]
    client = f"client-{rng.randrange(cfg['year']['clients']):02d}"
    base = dict(
        id=f"eng-{seed}-{i:03d}",
        client=client,
        owner=f"owner{i}@example.com",
        cost_center=f"RB-{i:04d}",
        stage="pov",
        classification=cls,
        region=region,
        start=start,
        expires=start + timedelta(days=round(weeks * 7)),
        budget_eur=budget,
        models=models,
        fine_tuning=fine_tuning,
        client_consent_fine_tuning=fine_tuning and consent,
    )
    request = dict(base)
    if bad_region:
        request["region"] = "eastus"
    if bad_model:
        request["models"] = [*models, {"model": "gpt-4.1", "tokens_per_minute": 30000}]
        if request["region"] == "swedencentral":  # gpt-4.1 is deployed there; pick a region without it
            request["region"] = "germanywestcentral"
    fixed = dict(base, region=region if region in eu_regions else "germanywestcentral")
    fixed["client_consent_fine_tuning"] = fine_tuning  # fixing means getting consent or dropping fine-tuning
    runaway = rng.random() < e["runaway"]
    luck = Luck(
        index=i,
        client=client,
        request=Engagement.model_validate(request),
        fixed=Engagement.model_validate(fixed),
        usage=rng.lognormvariate(0, e["usage_of_budget"]["sigma"]) * e["usage_of_budget"]["median"],
        runaway_day=rng.randrange(3, max(4, round(weeks * 7) - 2)) if runaway else None,
        runaway_factor=_u(rng, e["runaway_factor"]),
        wins_pilot=rng.random() < e["wins_pilot"],
        wins_scaled=rng.random() < e["wins_scaled"],
        pilot_weeks=_u(rng, e["pilot_weeks"]),
        forgets_teardown=rng.random() < people["forgets_teardown"],
        noticed_after=round(_u(rng, people["noticed_after_days"])),
        public_endpoint=rng.random() < people["public_endpoint"],
        reuses_key=rng.random() < people["reuses_key_across_clients"],
        cidr_pick=min(int(rng.paretovariate(1.2)) - 1, people["popular_cidrs"] - 1),
        cross_client_mix=rng.random() < cfg["shared"]["cross_client_mix"],
        env_days={
            "ticket": _u(rng, cfg["days"]["ticket_env"]),
            "shared": _u(rng, cfg["days"]["shared_env"]),
            "platform": _u(rng, cfg["days"]["platform_env"]),
        },
        rebuild_weeks=_u(rng, cfg["weeks"]["rebuild_for_production"]),
        migrate_weeks=_u(rng, cfg["weeks"]["migrate_out_of_shared"]),
    )
    gate = config.promotion()
    for stage in ("pilot", "scaled"):
        luck.releases[stage] = [_release(rng, stage, cfg, gate) for _ in range(4)]
    inc = cfg["incidents"]
    n = _poisson(rng, inc["per_month_scaled"] * 6)
    for _ in range(n + inc["bad_release_incidents"]):
        luck.incidents.append(
            (
                _u(rng, inc["detect_minutes"]["burn_rate"]),
                _u(rng, inc["detect_minutes"]["user_report"]),
                _u(rng, inc["fix_minutes"]),
            )
        )
    luck.natural_incidents = n
    return luck


def _poisson(rng: random.Random, lam: float) -> int:
    """Knuth's method; lam is small here."""
    k, p, limit = 0, 1.0, math.exp(-lam)
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1
