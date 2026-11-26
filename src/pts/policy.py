"""Policy checks on an engagement request, run before anything is provisioned. The provisioning agent
and CI run the same checks; a request with an error never becomes a Terraform change."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from . import config
from .engagement import Classification, Engagement

ERROR, WARNING = "error", "warning"


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str
    message: str

    def __str__(self) -> str:
        return f"{self.severity:7} {self.rule} {self.message}"


def minutes_to_spend(e: Engagement, pricing: dict[str, Any], out_share: float = 0.25) -> float:
    """How many minutes of full-quota use would spend the whole budget."""
    per_minute = 0.0
    for m in e.models:
        p = pricing["models"].get(m.model, {"input": 0, "output": 0})
        blended = (1 - out_share) * p["input"] + out_share * p["output"]
        per_minute += m.tokens_per_minute * blended / 1_000_000
    return float("inf") if per_minute == 0 else e.budget_eur / per_minute


def check(
    e: Engagement,
    others: list[Engagement] | None = None,
    today: date | None = None,
    platform: dict[str, Any] | None = None,
    pricing: dict[str, Any] | None = None,
) -> list[Finding]:
    p = platform or config.platform()
    pr = pricing or config.pricing()
    today = today or date.today()
    out: list[Finding] = []

    def err(rule: str, msg: str) -> None:
        out.append(Finding(rule, ERROR, msg))

    def warn(rule: str, msg: str) -> None:
        out.append(Finding(rule, WARNING, msg))

    regions = p["regions"]
    if e.region not in regions["allowed"]:
        err("PTS001", f"region {e.region} is not allowed; use one of {', '.join(regions['allowed'])}")
    else:
        available = regions["models"].get(e.region, [])
        for m in e.models:
            if m.model not in available:
                err("PTS002", f"{m.model} is not deployed in {e.region}; available: {', '.join(available)}")
    rules = p["classification"][e.classification.value]
    if rules.get("eu_only") and e.region not in regions["eu"]:
        err("PTS003", f"{e.classification.value} data must stay in an EU region, not {e.region}")
    stage = p["stages"][e.stage.value]
    if e.expires <= e.start:
        err("PTS004", "expires must be after start")
    elif e.weeks > stage["max_weeks"]:
        err("PTS004", f"a {e.stage.value} runs at most {stage['max_weeks']} weeks, this one {e.weeks:.0f}")
    if e.expires < today:
        err("PTS007", f"expired on {e.expires}; extend it or tear it down")
    if e.budget_eur > stage["max_budget_eur"]:
        err("PTS005", f"a {e.stage.value} budget is capped at €{stage['max_budget_eur']:,}; promote it first")
    if e.fine_tuning:
        allowed = rules.get("fine_tuning")
        if allowed is False:
            err("PTS006", f"fine-tuning is not allowed on {e.classification.value} data")
        elif allowed == "consent" and not e.client_consent_fine_tuning:
            err("PTS006", f"fine-tuning on {e.classification.value} data needs the client's written consent")
    for o in others or []:
        if o.id == e.id:
            err("PTS008", f"engagement id {e.id} is already used")
    if not e.models:
        err("PTS009", "at least one model deployment is needed")
    minutes = minutes_to_spend(e, pr)
    if minutes < 60 * 24 * 3:
        warn(
            "PTS010",
            f"the quota can spend the whole budget in {minutes / 60:.0f} hours of full use; "
            "the gateway will block at 100%",
        )
    if e.classification == Classification.client_restricted and e.stage.value == "pov" and len(e.models) > 3:
        warn("PTS011", "client-restricted PoVs should start with at most three model deployments")
    return out


def errors(findings: list[Finding]) -> list[Finding]:
    return [f for f in findings if f.severity == ERROR]


# --- static checks on the Terraform source -------------------------------------------------------------

TF_RULES = [
    ("TF001", re.compile(r"public_network_access_enabled\s*=\s*true"), "public network access must stay off"),
    ("TF002", re.compile(r"local_auth_enabled\s*=\s*true"), "key authentication must stay off; use Entra ID"),
    ("TF003", re.compile(r"min_tls_version\s*=\s*\"1\.[01]\""), "TLS below 1.2"),
    (
        "TF004",
        re.compile(r"allow_blob_public_access\s*=\s*true|allow_nested_items_to_be_public\s*=\s*true"),
        "public blob access",
    ),
    ("TF005", re.compile(r"purge_protection_enabled\s*=\s*false"), "Key Vault purge protection must be on"),
    ("TF006", re.compile(r"(?i)(api_key|password|secret)\s*=\s*\"[^\"$]{8,}\""), "hard-coded credential"),
]


def check_terraform(root: Path) -> list[Finding]:
    out = []
    for path in sorted(root.rglob("*.tf")):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            for rule, pat, msg in TF_RULES:
                if pat.search(code):
                    out.append(Finding(rule, ERROR, f"{path.relative_to(root)}:{n}: {msg}"))
    for path in sorted(root.rglob("main.tf")):
        text = path.read_text(encoding="utf-8")
        for block in re.finditer(r'resource\s+"(azurerm_[a-z_]+)"\s+"(\w+)"\s*{', text):
            kind = block.group(1)
            if kind in TAGGABLE:
                body = _block(text, block.end())
                if "tags" not in body:
                    where = f"{path.relative_to(root)}: {kind}.{block.group(2)}"
                    out.append(Finding("TF007", ERROR, f"{where} has no tags"))
    return out


TAGGABLE = {
    "azurerm_resource_group",
    "azurerm_virtual_network",
    "azurerm_key_vault",
    "azurerm_cognitive_account",
    "azurerm_log_analytics_workspace",
    "azurerm_storage_account",
    "azurerm_api_management",
    "azurerm_private_endpoint",
    "azurerm_user_assigned_identity",
}


def _block(text: str, start: int) -> str:
    depth, i = 1, start
    while i < len(text) and depth:
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        i += 1
    return text[start:i]
