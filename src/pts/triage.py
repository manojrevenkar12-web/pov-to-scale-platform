"""Read-only incident triage. Takes an Alertmanager webhook payload and the gateway's metrics, and
writes a first note for the on-call engineer: what fired, for which engagement, the likely cause and
the runbook steps. It suggests read-only commands and never runs anything."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import ROOT

RUNBOOKS = ROOT / "runbooks"


def parse_metrics(text: str) -> dict[tuple[str, frozenset], float]:
    out = {}
    for line in text.splitlines():
        m = re.match(r"^([a-z_]+)(\{(.*)\})?\s+([-+0-9.eE]+|NaN|\+Inf)$", line.strip())
        if not m:
            continue
        labels = frozenset(re.findall(r'(\w+)="([^"]*)"', m.group(3) or ""))
        out[(m.group(1), labels)] = float(m.group(4))
    return out


def _sum(ms: dict, name: str, **want: str) -> float:
    return sum(v for (n, labels), v in ms.items() if n == name and set(want.items()) <= labels)


@dataclass
class Note:
    alert: str
    engagement: str
    severity: str
    causes: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    runbook: str = ""

    def markdown(self) -> str:
        lines = [f"### {self.alert} on `{self.engagement}` ({self.severity})", ""]
        lines += ["Likely causes, from the gateway's own counters:"] + [f"- {c}" for c in self.causes or ["none seen"]]
        lines += ["", f"Runbook: `{self.runbook}`"] + [f"{i}. {s}" for i, s in enumerate(self.steps, 1)]
        lines += [
            "",
            "Read-only checks to run:",
            "```",
            *self.commands,
            "```",
            "",
            "This note is a suggestion. Nothing was changed.",
        ]
        return "\n".join(lines) + "\n"


def runbook_for(alert: str) -> Path | None:
    for p in sorted(RUNBOOKS.glob("*.md")):
        head = p.read_text(encoding="utf-8").split("\n---", 1)[0]
        if re.search(rf"^alerts:.*\b{re.escape(alert)}\b", head, re.M):
            return p
    return None


def triage(alert: dict[str, Any], metrics_text: str = "") -> Note:
    labels = alert.get("labels", {})
    name, eid = labels.get("alertname", "unknown"), labels.get("engagement", "unknown")
    note = Note(name, eid, labels.get("severity", "unknown"))
    ms = parse_metrics(metrics_text)
    total = _sum(ms, "gateway_requests_total", engagement=eid)
    upstream = _sum(ms, "gateway_upstream_errors_total", engagement=eid)
    throttled = _sum(ms, "gateway_upstream_errors_total", engagement=eid, code="429")
    refused_budget = _sum(ms, "gateway_refused_total", engagement=eid, reason="budget-exhausted")
    rate_limited = _sum(ms, "gateway_refused_total", engagement=eid, reason="rate-limited")
    fallbacks = _sum(ms, "gateway_fallbacks_total", engagement=eid)
    used = _sum(ms, "gateway_budget_used_ratio", engagement=eid)
    if refused_budget:
        note.causes.append(
            f"{refused_budget:.0f} requests refused for budget ({used:.0%} used): the owner must "
            "raise the budget or stop a runaway caller"
        )
    if throttled:
        note.causes.append(
            f"Azure OpenAI throttled {throttled:.0f} calls (429); {fallbacks:.0f} served by the "
            "fallback model: quota is too small for the load"
        )
    elif upstream:
        note.causes.append(
            f"{upstream:.0f} upstream errors that are not throttling: check the Azure OpenAI "
            "resource health and the private endpoint"
        )
    if rate_limited:
        note.causes.append(f"{rate_limited:.0f} requests over the engagement's tokens-per-minute quota")
    if total and not note.causes:
        note.causes.append("the gateway sees no errors of its own: look at the engagement's service (pods, latency)")
    rb = runbook_for(name)
    if rb:
        note.runbook = str(rb.relative_to(ROOT))
        body = rb.read_text(encoding="utf-8").split("\n---", 1)[-1]
        note.steps = [
            re.sub(r"^\d+\.\s*", "", line).strip() for line in body.splitlines() if re.match(r"^\d+\.\s", line)
        ][:5]
    ns = f"eng-{eid}"
    note.commands = [
        f"kubectl -n {ns} get pods,deploy,hpa",
        f"kubectl -n {ns} logs deploy/agent-service --since=30m --tail=200",
        f"kubectl -n {ns} get events --sort-by=.lastTimestamp | tail -20",
        "az monitor metrics list --resource <aoai-resource-id> --metric ProcessedPromptTokens,Ratelimit "
        "--interval PT5M --offset 2h",
    ]
    return note
