"""Spend per engagement. In production this sits in Azure Cache for Redis or Cosmos DB; the interface
is the same, so the gateway and its tests do not care."""

from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class Ledger:
    _spent: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    _alerted: set[str] = field(default_factory=set)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def spent(self, engagement: str) -> float:
        with self._lock:
            return self._spent[engagement]

    def add(self, engagement: str, eur: float) -> float:
        with self._lock:
            self._spent[engagement] += eur
            return self._spent[engagement]

    def first_alert(self, engagement: str) -> bool:
        """True once per engagement, so the owner is notified once, not on every request."""
        with self._lock:
            if engagement in self._alerted:
                return False
            self._alerted.add(engagement)
            return True


@dataclass
class TokenBucket:
    """Tokens-per-minute limit for one engagement and model."""

    capacity: float
    tokens: float
    updated: float

    def take(self, n: float, now: float) -> bool:
        self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.capacity / 60)
        self.updated = now
        if n > self.tokens:
            return False
        self.tokens -= n
        return True
