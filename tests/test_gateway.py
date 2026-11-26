from fastapi.testclient import TestClient

from gateway.app import State, create_app
from gateway.pii import redact
from gateway.upstream import FakeUpstream

from .conftest import make


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def client(**engs):
    es = engs or {
        "alpha-pov": make(
            id="alpha-pov",
            client="alpha-co",
            budget_eur=1.0,
            models=[
                {"model": "gpt-4o", "tokens_per_minute": 100000},
                {"model": "gpt-4o-mini", "tokens_per_minute": 100000},
            ],
        ),
        "gamma-pov": make(
            id="gamma-pov",
            client="gamma-co",
            budget_eur=0.05,
            models=[{"model": "gpt-4o", "tokens_per_minute": 1000000}],
        ),
        "beta-pov": make(
            id="beta-pov",
            client="beta-co",
            classification="client-restricted",
            region="swedencentral",
            budget_eur=50.0,
            models=[{"model": "gpt-4o-mini", "tokens_per_minute": 2000}],
        ),
    }
    up, clock = FakeUpstream(), Clock()
    state = State(es, up, clock=clock)
    return TestClient(create_app(state)), state, up, clock


def call(c, eid, model="gpt-4o-mini", text="hello", caller=None, max_tokens=64):
    return c.post(
        "/v1/chat/completions",
        json={"model": model, "messages": [{"role": "user", "content": text}], "max_tokens": max_tokens},
        headers={"x-engagement-id": eid, "x-caller-engagements": caller if caller is not None else eid},
    )


def test_happy_path_books_cost_and_metrics():
    c, state, _, _ = client()
    r = call(c, "alpha-pov", "gpt-4o", "Summarise the price list")
    assert r.status_code == 200, r.text
    assert r.json()["usage"]["prompt_tokens"] > 0 and r.headers["x-served-model"] == "gpt-4o"
    assert state.ledger.spent("alpha-pov") > 0
    text = c.get("/metrics").text
    assert 'gateway_requests_total{code="200",engagement="alpha-pov",model="gpt-4o"} 1' in text
    assert 'gateway_request_seconds_bucket{engagement="alpha-pov",le="+Inf"} 1' in text


def test_caller_cannot_use_another_clients_engagement():
    c, _, up, _ = client()
    r = call(c, "beta-pov", caller="alpha-pov")
    assert r.status_code == 403 and r.json()["detail"]["reason"] == "not-on-engagement"
    assert up.calls == []
    assert call(c, "nope", caller="nope").status_code == 404


def test_model_must_be_deployed_for_the_engagement():
    c, *_ = client()
    assert call(c, "beta-pov", model="gpt-4o").json()["detail"]["reason"] == "model-not-deployed"


def test_personal_data_is_redacted_before_it_leaves_for_client_restricted_work():
    c, state, up, _ = client()
    text = "Call Anna at +49 151 23456789 or anna.weber@kunde.de, IBAN DE89 3704 0044 0532 0130 00"
    r = call(c, "beta-pov", text=text)
    assert r.status_code == 200
    sent = up.calls[-1][1][0]["content"]
    assert "anna.weber@kunde.de" not in sent and "23456789" not in sent and "DE89" not in sent
    assert "[EMAIL]" in sent and "[PHONE]" in sent and "[IBAN]" in sent
    assert state.metrics.get("gateway_redactions_total", engagement="beta-pov") == 3


def test_internal_work_is_not_rewritten():
    c, _, up, _ = client()
    call(c, "alpha-pov", text="mail me at lena@example.com")
    assert "lena@example.com" in up.calls[-1][1][0]["content"]


def test_budget_alerts_once_then_blocks():
    c, state, up, _ = client()
    codes = [call(c, "gamma-pov", "gpt-4o", "x" * 4000, max_tokens=2000).status_code for _ in range(20)]
    assert 402 in codes and codes[0] == 200
    first_block = codes.index(402)
    assert all(code == 402 for code in codes[first_block:])
    assert state.ledger.spent("gamma-pov") <= 0.05
    assert len(state.notifications) == 1 and "gamma-pov" in state.notifications[0]
    n = len(up.calls)
    call(c, "gamma-pov", "gpt-4o", "x" * 4000, max_tokens=2000)
    assert len(up.calls) == n  # a request that could overrun never reaches the model
    assert call(c, "gamma-pov", "gpt-4o", "short", max_tokens=16).status_code == 200  # one that fits still does


def test_rate_limit_refills_over_time():
    c, _, _, clock = client()
    assert call(c, "beta-pov", text="a" * 4000, max_tokens=500).status_code == 200
    assert call(c, "beta-pov", text="a" * 4000, max_tokens=500).json()["detail"]["reason"] == "rate-limited"
    clock.t += 60
    assert call(c, "beta-pov", text="a" * 4000, max_tokens=500).status_code == 200


def test_falls_back_to_the_smaller_model_on_throttling():
    c, state, up, _ = client()
    up.failing["gpt-4o"] = 429
    r = call(c, "alpha-pov", "gpt-4o", "hi")
    assert r.status_code == 200 and r.json()["model"] == "gpt-4o-mini"
    assert state.metrics.get("gateway_fallbacks_total", engagement="alpha-pov", model="gpt-4o") == 1


def test_no_fallback_on_a_hard_error_and_502_when_nothing_answers():
    c, _, up, _ = client()
    up.failing["gpt-4o"] = 400
    assert call(c, "alpha-pov", "gpt-4o").status_code == 502
    up.failing.update({"gpt-4o": 503, "gpt-4o-mini": 503})
    r = call(c, "alpha-pov", "gpt-4o")
    assert r.status_code == 502 and r.json()["detail"]["tried"] == ["gpt-4o", "gpt-4o-mini"]


def test_budget_endpoint_is_scoped_to_the_caller():
    c, *_ = client()
    call(c, "alpha-pov")
    assert c.get("/v1/engagements/alpha-pov/budget", headers={"x-caller-engagements": "alpha-pov"}).json()["used"] > 0
    assert c.get("/v1/engagements/alpha-pov/budget", headers={"x-caller-engagements": "beta-pov"}).status_code == 403


def test_redaction_rules():
    text, counts = redact("card 4111 1111 1111 1111, order 1234 5678 9012 3456, ref 2026-11-26")
    assert "[CARD]" in text and "1234 5678 9012 3456" in text and "2026-11-26" in text
    assert counts["card"] == 1


def test_each_engagement_reaches_only_its_own_backend():
    es = {
        "alpha-pov": make(id="alpha-pov", client="alpha-co"),
        "beta-pov": make(id="beta-pov", client="beta-co"),
    }
    a, b = FakeUpstream(), FakeUpstream()
    c = TestClient(create_app(State(es, {"alpha-pov": a, "beta-pov": b})))
    assert call(c, "beta-pov").status_code == 200
    assert len(b.calls) == 1 and a.calls == []
