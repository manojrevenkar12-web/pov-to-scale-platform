"""Budget enforcement shared by the AI gateway and the lab: alert at 80%, block at 100%."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from . import config

ALLOW, ALERT, BLOCK = "allow", "alert", "block"


class Verdict(StrEnum):
    allow = ALLOW
    alert = ALERT
    block = BLOCK


def decide(spent: float, budget: float, request_cost: float, cfg: dict[str, Any] | None = None) -> Verdict:
    """Verdict for a request of estimated cost, given what was spent so far."""
    b = (cfg or config.platform())["budget"]
    if budget <= 0:
        return Verdict.block
    if spent >= budget * b["block_at"] or spent + request_cost > budget * b["block_at"]:
        return Verdict.block
    if spent + request_cost >= budget * b["alert_at"]:
        return Verdict.alert
    return Verdict.allow


def token_cost(model: str, input_tokens: int, output_tokens: int, pricing: dict[str, Any] | None = None) -> float:
    p = (pricing or config.pricing())["models"].get(model)
    if p is None:
        raise KeyError(f"no price for {model}")
    return (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000


@dataclass(frozen=True)
class Forecast:
    daily_burn: float
    days_left: float


def forecast(daily_spend: list[float], spent: float, budget: float, window: int = 7) -> Forecast:
    recent = daily_spend[-window:] or [0.0]
    burn = sum(recent) / len(recent)
    left = budget - spent
    return Forecast(burn, float("inf") if burn <= 0 else max(0.0, left / burn))
