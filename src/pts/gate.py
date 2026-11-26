"""Promotion gate. A release moves pov -> pilot -> scaled only when every check for the target stage
passes. The same function runs in the Argo CD pre-sync hook, in CI and in the lab."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import config


@dataclass(frozen=True)
class Metrics:
    requests: int
    p95_latency_ms: float
    error_rate: float
    eval_score: float
    cost_per_1k_requests_eur: float
    slo_budget_remaining: float = 1.0  # share of the 30-day error budget left


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


@dataclass
class Decision:
    target: str
    checks: list[Check] = field(default_factory=list)

    @property
    def promote(self) -> bool:
        return bool(self.checks) and all(c.ok for c in self.checks)

    def failed(self) -> list[str]:
        return [c.name for c in self.checks if not c.ok]


def evaluate(
    target: str, m: Metrics, current_eval: float | None = None, rules: dict[str, Any] | None = None
) -> Decision:
    cfg = rules or config.promotion()
    if target not in cfg["stages"]:
        raise ValueError(f"no promotion rules for stage {target!r}")
    t = cfg["stages"][target]
    d = Decision(target)

    def add(name: str, ok: bool, detail: str) -> None:
        d.checks.append(Check(name, ok, detail))

    add("traffic", m.requests >= cfg["min_requests"], f"{m.requests} requests (need {cfg['min_requests']})")
    lat = t["p95_latency_ms"]
    add("latency", m.p95_latency_ms <= lat, f"p95 {m.p95_latency_ms:.0f} ms (max {lat})")
    add("errors", m.error_rate <= t["error_rate"], f"{m.error_rate:.2%} errors (max {t['error_rate']:.2%})")
    add("eval", m.eval_score >= t["eval_score"], f"eval {m.eval_score:.2f} (min {t['eval_score']:.2f})")
    if current_eval is not None:
        drop = current_eval - m.eval_score
        add("regression", drop <= t["eval_regression"], f"eval drop {drop:+.3f} (max {t['eval_regression']})")
    add(
        "cost",
        m.cost_per_1k_requests_eur <= t["cost_per_1k_requests_eur"],
        f"€{m.cost_per_1k_requests_eur:.2f} per 1k requests (max €{t['cost_per_1k_requests_eur']:.2f})",
    )
    if t["slo_budget_remaining"] > 0:
        add(
            "error-budget",
            m.slo_budget_remaining >= t["slo_budget_remaining"],
            f"{m.slo_budget_remaining:.0%} of the error budget left (min {t['slo_budget_remaining']:.0%})",
        )
    return d


QUERIES = {
    "requests": 'sum(increase(gateway_requests_total{{engagement="{e}"}}[{w}h]))',
    "p95_latency_ms": (
        'histogram_quantile(0.95, sum(rate(gateway_request_seconds_bucket{{engagement="{e}"}}[{w}h])) by (le)) * 1000'
    ),
    "error_rate": (
        'sum(rate(gateway_requests_total{{engagement="{e}",code=~"5.."}}[{w}h]))'
        ' / sum(rate(gateway_requests_total{{engagement="{e}"}}[{w}h]))'
    ),
    "cost_per_1k_requests_eur": (
        'sum(increase(gateway_spend_eur_total{{engagement="{e}"}}[{w}h]))'
        ' / sum(increase(gateway_requests_total{{engagement="{e}"}}[{w}h])) * 1000'
    ),
    "eval_score": 'max(engagement_eval_score{{engagement="{e}"}})',
    "error_ratio_30d": (
        'sum(increase(gateway_requests_total{{engagement="{e}",code=~"5.."}}[30d]))'
        ' / sum(increase(gateway_requests_total{{engagement="{e}"}}[30d]))'
    ),
}


def from_prometheus(url: str, engagement: str, slo_target: float = 0.995, client=None) -> Metrics:
    """Read a release's observation window from Prometheus. A missing series fails closed."""
    import httpx

    http = client or httpx.Client(timeout=30)
    w = config.promotion()["window_hours"]
    values = {}
    for key, q in QUERIES.items():
        r = http.get(f"{url}/api/v1/query", params={"query": q.format(e=engagement, w=w)})
        r.raise_for_status()
        result = r.json()["data"]["result"]
        if not result:
            raise ValueError(f"no data for {key} of {engagement}; the gate does not promote without evidence")
        values[key] = float(result[0]["value"][1])
    budget = 1 - slo_target
    return Metrics(
        requests=int(values["requests"]),
        p95_latency_ms=values["p95_latency_ms"],
        error_rate=values["error_rate"],
        eval_score=values["eval_score"],
        cost_per_1k_requests_eur=values["cost_per_1k_requests_eur"],
        slo_budget_remaining=max(0.0, 1 - values["error_ratio_30d"] / budget),
    )
