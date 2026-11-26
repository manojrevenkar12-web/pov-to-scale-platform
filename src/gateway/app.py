"""The AI gateway. It sits behind Azure API Management, which validates the caller's Entra ID token
and forwards the engagements the caller may use in `x-caller-engagements`. The gateway then

1. refuses a call for an engagement the caller is not on (no cross-client use),
2. refuses a model the engagement has no deployment for,
3. redacts personal data from prompts of confidential and client-restricted engagements,
4. checks the engagement's token rate and budget (alert at 80%, block at 100%),
5. calls Azure OpenAI and falls back to the cheaper model on 429/503,
6. books the cost and exports metrics for the SLO and budget alerts.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from pts import config
from pts.budget import Verdict, decide, token_cost
from pts.engagement import Classification, Engagement

from .ledger import Ledger, TokenBucket
from .metrics import Metrics
from .pii import redact
from .upstream import FakeUpstream, Upstream, UpstreamError

log = logging.getLogger("gateway")
REDACT = {Classification.confidential, Classification.client_restricted}
RETRYABLE = {429, 503}


class Message(BaseModel):
    role: str = Field(pattern="^(system|user|assistant)$")
    content: str = Field(max_length=200_000)


class ChatRequest(BaseModel):
    model: str
    messages: list[Message] = Field(min_length=1, max_length=200)
    max_tokens: int = Field(default=512, ge=1, le=16_384)


@dataclass
class State:
    engagements: dict[str, Engagement]
    upstream: Upstream | dict[str, Upstream]  # one backend, or one per engagement (its own Azure OpenAI)
    ledger: Ledger = field(default_factory=Ledger)
    metrics: Metrics = field(default_factory=Metrics)
    clock: callable = time.monotonic
    buckets: dict[tuple[str, str], TokenBucket] = field(default_factory=dict)
    notifications: list[str] = field(default_factory=list)

    def upstream_for(self, eid: str) -> Upstream:
        if isinstance(self.upstream, dict):
            return self.upstream[eid]
        return self.upstream

    def bucket(self, e: Engagement, model: str) -> TokenBucket:
        key = (e.id, model)
        if key not in self.buckets:
            tpm = next(m.tokens_per_minute for m in e.models if m.model == model)
            self.buckets[key] = TokenBucket(tpm, tpm, self.clock())
        return self.buckets[key]


def create_app(state: State) -> FastAPI:
    app = FastAPI(title="pov-to-scale AI gateway", version="0.1.0")
    app.state.gw = state
    fallback = config.pricing().get("fallback", {})

    def refuse(status: int, reason: str, engagement: str, msg: str) -> HTTPException:
        state.metrics.inc("gateway_refused_total", engagement=engagement, reason=reason)
        return HTTPException(status, {"reason": reason, "message": msg})

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True, "engagements": len(state.engagements)}

    @app.get("/metrics", response_class=PlainTextResponse)
    def metrics() -> str:
        return state.metrics.render()

    @app.get("/v1/engagements/{eid}/budget")
    def budget(eid: str, x_caller_engagements: str = Header(default="")) -> dict:
        e = _authorize(state, eid, x_caller_engagements, refuse)
        spent = state.ledger.spent(eid)
        return {
            "engagement": eid,
            "budget_eur": e.budget_eur,
            "spent_eur": round(spent, 6),
            "used": round(spent / e.budget_eur, 6),
        }

    @app.post("/v1/chat/completions")
    def chat(
        req: ChatRequest,
        request: Request,
        x_engagement_id: str = Header(),
        x_caller_engagements: str = Header(default=""),
    ) -> JSONResponse:
        started = state.clock()
        e = _authorize(state, x_engagement_id, x_caller_engagements, refuse)
        deployed = {m.model for m in e.models}
        if req.model not in deployed:
            raise refuse(404, "model-not-deployed", e.id, f"{req.model} is not deployed for {e.id}")
        messages = [m.model_dump() for m in req.messages]
        if e.classification in REDACT:
            total = 0
            for m in messages:
                m["content"], counts = redact(m["content"])
                total += sum(counts.values())
            if total:
                state.metrics.inc("gateway_redactions_total", total, engagement=e.id)
        est_in = sum(len(m["content"]) for m in messages) // 4 + 1
        est_cost = token_cost(req.model, est_in, req.max_tokens)
        verdict = decide(state.ledger.spent(e.id), e.budget_eur, est_cost)
        if verdict != Verdict.allow:
            _notify(state, e, state.ledger.spent(e.id), verdict)
        if verdict == Verdict.block:
            raise refuse(
                402,
                "budget-exhausted",
                e.id,
                f"{e.id} has used its €{e.budget_eur:,.0f} budget; ask the owner {e.owner} to raise it",
            )
        if not state.bucket(e, req.model).take(est_in + req.max_tokens, state.clock()):
            raise refuse(429, "rate-limited", e.id, f"{e.id} is over its tokens-per-minute quota for {req.model}")

        tried, result = [], None
        for model in [req.model, fallback.get(req.model)]:
            if not model or model not in deployed:
                continue
            tried.append(model)
            try:
                result = state.upstream_for(e.id).complete(model, messages, req.max_tokens)
                break
            except UpstreamError as err:
                state.metrics.inc("gateway_upstream_errors_total", engagement=e.id, model=model, code=str(err.status))
                if err.status not in RETRYABLE:
                    break
        elapsed = state.clock() - started
        if result is None:
            state.metrics.inc("gateway_requests_total", engagement=e.id, model=req.model, code="502")
            state.metrics.observe(elapsed, engagement=e.id)
            raise HTTPException(502, {"reason": "upstream-unavailable", "tried": tried})

        cost = token_cost(result.model, result.input_tokens, result.output_tokens)
        spent = state.ledger.add(e.id, cost)
        after = decide(spent, e.budget_eur, 0.0)
        if after != Verdict.allow:
            _notify(state, e, spent, after)
        state.metrics.inc("gateway_requests_total", engagement=e.id, model=result.model, code="200")
        for kind, n in (("input", result.input_tokens), ("output", result.output_tokens)):
            state.metrics.inc("gateway_tokens_total", n, engagement=e.id, model=result.model, kind=kind)
        state.metrics.inc("gateway_spend_eur_total", cost, engagement=e.id)
        state.metrics.set("gateway_budget_used_ratio", spent / e.budget_eur, engagement=e.id)
        state.metrics.observe(elapsed, engagement=e.id)
        if result.model != req.model:
            state.metrics.inc("gateway_fallbacks_total", engagement=e.id, model=req.model)
        return JSONResponse(
            {
                "model": result.model,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": result.content}}],
                "usage": {"prompt_tokens": result.input_tokens, "completion_tokens": result.output_tokens},
                "cost_eur": round(cost, 6),
            },
            headers={"x-budget-used": f"{spent / e.budget_eur:.4f}", "x-served-model": result.model},
        )

    return app


def _notify(state: State, e: Engagement, spent: float, verdict: Verdict) -> None:
    """Tell the owner once, at the first request that reaches the alert or block level."""
    if state.ledger.first_alert(e.id):
        what = "new requests are refused" if verdict == Verdict.block else "requests continue until 100%"
        state.notifications.append(
            f"{e.owner}: {e.id} is at {spent / e.budget_eur:.0%} of its €{e.budget_eur:,.2f} budget; {what}"
        )


def _authorize(state: State, eid: str, caller: str, refuse) -> Engagement:
    e = state.engagements.get(eid)
    if e is None:
        raise refuse(404, "unknown-engagement", eid, f"no engagement {eid}")
    allowed = {x.strip() for x in caller.split(",") if x.strip()}
    if eid not in allowed:
        raise refuse(403, "not-on-engagement", eid, f"the caller is not on engagement {eid}")
    return e


def production() -> FastAPI:
    """Container entry point. GATEWAY_ENDPOINTS maps each engagement to its own Azure OpenAI endpoint
    (from `terraform output engagements`); tokens come from the pod's workload identity."""
    import json
    import os

    from azure.identity import DefaultAzureCredential

    from pts import ROOT
    from pts.engagement import load_all

    from .upstream import AzureOpenAI

    cred = DefaultAzureCredential()

    def token() -> str:
        return cred.get_token("https://cognitiveservices.azure.com/.default").token

    endpoints = json.loads(os.environ["GATEWAY_ENDPOINTS"])
    es = {e.id: e for e in load_all(ROOT / "engagements") if e.id in endpoints}
    ups = {eid: AzureOpenAI(endpoints[eid], token) for eid in es}
    return create_app(State(es, ups))


def demo() -> FastAPI:
    """`uvicorn gateway.app:demo --factory` with the sample engagements and a fake backend."""
    from pts import ROOT
    from pts.engagement import load_all

    es = {e.id: e for e in load_all(ROOT / "engagements")}
    return create_app(State(es, FakeUpstream()))
