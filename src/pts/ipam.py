"""Address allocation for engagement spokes. Each engagement gets its own /22 from the hub's range,
so peering never fails on overlapping networks and no two clients share address space."""

from __future__ import annotations

import ipaddress
from collections.abc import Iterable


class IpamError(Exception):
    pass


def overlaps(cidrs: Iterable[str]) -> list[tuple[str, str]]:
    nets = sorted((ipaddress.ip_network(c) for c in cidrs), key=lambda n: (int(n.network_address), n.prefixlen))
    out = []
    for i, a in enumerate(nets):
        for b in nets[i + 1 :]:
            if int(b.network_address) > int(a.broadcast_address):
                break
            if a.overlaps(b):
                out.append((str(a), str(b)))
    return out


def allocate(
    existing: dict[str, str], wanted: Iterable[str], space: str, reserved: Iterable[str], prefix: int
) -> dict[str, str]:
    """Keep existing allocations, give each new engagement the lowest free /prefix."""
    pool = ipaddress.ip_network(space)
    taken = [ipaddress.ip_network(c) for c in [*reserved, *existing.values()]]
    for c in taken:
        if not c.subnet_of(pool):
            raise IpamError(f"{c} is outside {pool}")
    if overlaps(str(c) for c in taken):
        raise IpamError(f"existing allocations overlap: {overlaps(str(c) for c in taken)}")
    out = dict(existing)
    candidates = pool.subnets(new_prefix=prefix)
    for eid in wanted:
        if eid in out:
            continue
        for cand in candidates:
            if not any(cand.overlaps(t) for t in taken):
                out[eid] = str(cand)
                taken.append(cand)
                break
        else:
            raise IpamError(f"{pool} has no free /{prefix} left for {eid}")
    return out
