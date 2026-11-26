"""Engagement request -> Terraform variables for infra/terraform/modules/engagement."""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any

from . import config
from .engagement import Classification, Engagement


def resource_suffix(engagement_id: str) -> str:
    """Globally unique, name-safe suffix for storage, Key Vault and Azure OpenAI names (<= 18 characters)."""
    alnum = re.sub(r"[^a-z0-9]", "", engagement_id)[:14]
    return alnum + hashlib.sha256(engagement_id.encode()).hexdigest()[:4]


def tfvars(e: Engagement, address_space: str, platform: dict[str, Any] | None = None) -> dict[str, Any]:
    p = platform or config.platform()
    rules = p["classification"][e.classification.value]
    return {
        "engagement_id": e.id,
        "resource_suffix": resource_suffix(e.id),
        "client": e.client,
        "location": e.region,
        "stage": e.stage.value,
        "address_space": address_space,
        "budget_eur": e.budget_eur,
        "budget_alert_thresholds": [round(p["budget"]["alert_at"] * 100), round(p["budget"]["block_at"] * 100)],
        "budget_start_date": e.start.replace(day=1).isoformat() + "T00:00:00Z",
        "budget_end_date": e.expires.isoformat() + "T00:00:00Z",
        "owner_email": e.owner,
        # Azure OpenAI capacity is counted in units of 1,000 tokens per minute
        "model_deployments": [
            {"name": m.model, "model": m.model, "capacity": math.ceil(m.tokens_per_minute / 1000)} for m in e.models
        ],
        "dedicated_key_vault": bool(rules.get("dedicated_key_vault", False))
        or e.classification == Classification.client_restricted,
        "fine_tuning_storage": e.fine_tuning,
        "replicas": p["stages"][e.stage.value]["replicas"],
        "tags": e.tags(),
    }


def to_json(v: dict[str, Any]) -> str:
    return json.dumps(v, indent=2, sort_keys=True) + "\n"


def argocd_apps(engagements: list[Engagement]) -> str:
    """Parameters for the Argo CD ApplicationSet: one application per engagement, on its stage's overlay."""
    apps = [
        {
            "id": e.id,
            "stage": e.stage.value,
            "namespace": f"eng-{e.id}",
            "client": e.client,
            "classification": e.classification.value,
        }
        for e in sorted(engagements, key=lambda x: x.id)
    ]
    return json.dumps(apps, indent=2) + "\n"


def render_all(engagements: list[Engagement], allocations: dict[str, str]) -> tuple[dict[str, str], str, str]:
    """Allocate address ranges and render every engagement. Returns (allocations, ipam.json, tfvars.json).
    Allocations of engagements that no longer exist are released; existing ones never move."""
    from . import ipam

    hub = config.platform()["hub"]
    keep = {k: v for k, v in allocations.items() if k in {e.id for e in engagements}}
    alloc = ipam.allocate(
        keep, [e.id for e in engagements], hub["address_space"], [hub["hub_prefix"]], hub["spoke_prefix_length"]
    )
    tf = {"engagements": {e.id: tfvars(e, alloc[e.id]) for e in engagements}}
    return alloc, to_json(dict(sorted(alloc.items()))), to_json(tf)
