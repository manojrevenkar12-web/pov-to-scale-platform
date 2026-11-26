"""Typed access to config/*.yaml. Settings live in files, not in code."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from . import CONFIG


def load(name: str, base: Path = CONFIG) -> dict[str, Any]:
    with open(base / f"{name}.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache
def platform() -> dict[str, Any]:
    return load("platform")


@lru_cache
def promotion() -> dict[str, Any]:
    return load("promotion")


@lru_cache
def pricing() -> dict[str, Any]:
    return load("pricing")
