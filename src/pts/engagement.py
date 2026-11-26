"""An engagement is one client piece of work on the platform: a PoV, then maybe a pilot, then a
scaled rollout. Every engagement gets its own isolated environment, budget and end date."""

from __future__ import annotations

import re
from datetime import date
from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator

SLUG = re.compile(r"^[a-z][a-z0-9-]{2,30}[a-z0-9]$")


class Stage(StrEnum):
    pov = "pov"
    pilot = "pilot"
    scaled = "scaled"

    @property
    def next(self) -> Stage | None:
        order = [Stage.pov, Stage.pilot, Stage.scaled]
        i = order.index(self)
        return order[i + 1] if i + 1 < len(order) else None


class Classification(StrEnum):
    public = "public"
    internal = "internal"
    confidential = "confidential"
    client_restricted = "client-restricted"


class ModelQuota(BaseModel):
    model: str
    tokens_per_minute: int = Field(gt=0, le=2_000_000)


class Engagement(BaseModel):
    id: str
    client: str
    owner: str  # email of the accountable consultant or engineer
    cost_center: str
    stage: Stage = Stage.pov
    classification: Classification
    region: str
    start: date
    expires: date
    budget_eur: float = Field(gt=0)
    models: list[ModelQuota]
    fine_tuning: bool = False
    client_consent_fine_tuning: bool = False
    description: str = ""

    @field_validator("id", "client")
    @classmethod
    def slug(cls, v: str) -> str:
        if not SLUG.match(v):
            raise ValueError(f"{v!r} must be a lowercase slug (letters, digits, dashes)")
        return v

    @field_validator("owner")
    @classmethod
    def email(cls, v: str) -> str:
        if not re.match(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", v):
            raise ValueError("owner must be an email address")
        return v

    @property
    def weeks(self) -> float:
        return (self.expires - self.start).days / 7

    def tags(self) -> dict[str, str]:
        return {
            "engagement": self.id,
            "client": self.client,
            "owner": self.owner,
            "stage": self.stage.value,
            "classification": self.classification.value,
            "expires": self.expires.isoformat(),
            "cost-center": self.cost_center,
        }


def load(path: Path) -> Engagement:
    with open(path, encoding="utf-8") as f:
        return Engagement.model_validate(yaml.safe_load(f))


def load_all(directory: Path) -> list[Engagement]:
    return [load(p) for p in sorted(directory.glob("*.yaml"))]


def dump(e: Engagement) -> str:
    return yaml.safe_dump(e.model_dump(mode="json"), sort_keys=False)
