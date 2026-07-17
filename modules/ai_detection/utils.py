"""
WebIntelPro Enterprise X
AI Stack Detection (Phase 2D) - Utilities

Small, dependency-light text primitives shared across the sub-detectors and
the orchestrator. Mirrors :mod:`modules.api_discovery.utils`, minus the
network-bearing reachability helpers -- this sub-system is passive-only, so
there is nothing here that performs I/O.

One invariant holds for everything in this module: **never raises**.
Malformed input yields an empty/neutral result, never an exception to the
caller.
"""

from __future__ import annotations

from typing import Iterable, List


def clamp(text: str, max_bytes: int) -> str:
    """Return at most ``max_bytes`` characters of ``text`` (0 = no cap)."""
    if not text or max_bytes <= 0 or len(text) <= max_bytes:
        return text or ""
    return text[:max_bytes]


def dedupe(items: Iterable[str]) -> List[str]:
    """Order-preserving de-duplication of strings."""
    seen = set()
    out: List[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out
