"""Prometheus exposition without a client library: counters, a histogram and gauges."""

from __future__ import annotations

import threading
from collections import defaultdict

BUCKETS = (0.25, 0.5, 1, 2, 4, 8, 16, 30)


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.counters: dict[tuple[str, tuple], float] = defaultdict(float)
        self.gauges: dict[tuple[str, tuple], float] = {}
        self.hist: dict[tuple, list[float]] = {}

    def inc(self, name: str, value: float = 1.0, **labels: str) -> None:
        with self._lock:
            self.counters[(name, tuple(sorted(labels.items())))] += value

    def set(self, name: str, value: float, **labels: str) -> None:
        with self._lock:
            self.gauges[(name, tuple(sorted(labels.items())))] = value

    def observe(self, seconds: float, **labels: str) -> None:
        key = tuple(sorted(labels.items()))
        with self._lock:
            h = self.hist.setdefault(key, [0.0] * (len(BUCKETS) + 2))  # buckets..., count, sum
            for i, b in enumerate(BUCKETS):
                if seconds <= b:
                    h[i] += 1
            h[-2] += 1
            h[-1] += seconds

    def get(self, name: str, **labels: str) -> float:
        return self.counters.get((name, tuple(sorted(labels.items()))), 0.0)

    def render(self) -> str:
        def lbl(items: tuple, extra: str = "") -> str:
            parts = [f'{k}="{v}"' for k, v in items] + ([extra] if extra else [])
            return "{" + ",".join(parts) + "}" if parts else ""

        lines = []
        with self._lock:
            for (name, items), v in sorted(self.counters.items()):
                lines.append(f"{name}{lbl(items)} {v:g}")
            for (name, items), v in sorted(self.gauges.items()):
                lines.append(f"{name}{lbl(items)} {v:g}")
            for items, h in sorted(self.hist.items()):
                for i, b in enumerate(BUCKETS):
                    le = f'le="{b:g}"'
                    lines.append(f"gateway_request_seconds_bucket{lbl(items, le)} {h[i]:g}")
                inf = 'le="+Inf"'
                lines.append(f"gateway_request_seconds_bucket{lbl(items, inf)} {h[-2]:g}")
                lines.append(f"gateway_request_seconds_count{lbl(items)} {h[-2]:g}")
                lines.append(f"gateway_request_seconds_sum{lbl(items)} {h[-1]:g}")
        return "\n".join(lines) + "\n"
