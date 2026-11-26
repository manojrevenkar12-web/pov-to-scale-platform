import json

import httpx
import pytest

from pts import gate
from pts.cli import main

GOOD = gate.Metrics(
    requests=5000,
    p95_latency_ms=1800,
    error_rate=0.002,
    eval_score=0.9,
    cost_per_1k_requests_eur=5.0,
    slo_budget_remaining=0.8,
)


def test_a_good_release_is_promoted_to_scaled():
    d = gate.evaluate("scaled", GOOD, current_eval=0.89)
    assert d.promote and d.failed() == []


@pytest.mark.parametrize(
    ("change", "failed"),
    [
        ({"requests": 100}, ["traffic"]),
        ({"p95_latency_ms": 3200}, ["latency"]),
        ({"error_rate": 0.01}, ["errors"]),
        ({"eval_score": 0.84}, ["eval", "regression"]),
        ({"cost_per_1k_requests_eur": 9.5}, ["cost"]),
        ({"slo_budget_remaining": 0.3}, ["error-budget"]),
    ],
)
def test_each_rule_can_stop_a_promotion(change, failed):
    m = gate.Metrics(**{**GOOD.__dict__, **change})
    d = gate.evaluate("scaled", m, current_eval=0.89)
    assert not d.promote and d.failed() == failed


def test_pilot_is_more_lenient_and_ignores_the_error_budget():
    m = gate.Metrics(**{**GOOD.__dict__, "p95_latency_ms": 3500, "slo_budget_remaining": 0.0})
    assert gate.evaluate("pilot", m).promote
    with pytest.raises(ValueError):
        gate.evaluate("pov", m)


def prom(values: dict[str, float | None]):
    def handler(request: httpx.Request) -> httpx.Response:
        q = request.url.params["query"]
        key = next(k for k, tmpl in gate.QUERIES.items() if tmpl.format(e="eng-a", w=72) == q)
        v = values.get(key)
        result = [] if v is None else [{"metric": {}, "value": [0, str(v)]}]
        return httpx.Response(200, json={"status": "success", "data": {"resultType": "vector", "result": result}})

    return httpx.Client(transport=httpx.MockTransport(handler), base_url="http://prom")


def test_reads_the_window_from_prometheus():
    c = prom(
        {
            "requests": 4200,
            "p95_latency_ms": 1900,
            "error_rate": 0.001,
            "cost_per_1k_requests_eur": 4.1,
            "eval_score": 0.91,
            "error_ratio_30d": 0.001,
        }
    )
    m = gate.from_prometheus("http://prom", "eng-a", client=c)
    assert m.requests == 4200 and m.slo_budget_remaining == pytest.approx(0.8)
    assert gate.evaluate("scaled", m).promote


def test_missing_evidence_fails_closed():
    c = prom({"requests": 4200})
    with pytest.raises(ValueError, match="no data"):
        gate.from_prometheus("http://prom", "eng-a", client=c)


def test_cli_exit_codes(tmp_path):
    good, bad = tmp_path / "good.json", tmp_path / "bad.json"
    good.write_text(json.dumps(GOOD.__dict__))
    bad.write_text(json.dumps({**GOOD.__dict__, "error_rate": 0.2}))
    assert main(["gate", "--stage", "scaled", "--metrics", str(good)]) == 0
    assert main(["gate", "--stage", "scaled", "--metrics", str(bad)]) == 1
