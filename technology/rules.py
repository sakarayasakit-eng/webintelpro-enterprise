"""
WebIntelPro Enterprise X
Technology Rule Engine

Evaluates case-insensitive signatures against a text source.

Two matching modes, chosen automatically per signature:
  * Plain-word signatures (only [a-z0-9], e.g. "ember", "render") are matched
    with word boundaries, so "ember" does NOT match inside "remember" or
    "September". This is the main defense against false positives.
  * Signatures containing any delimiter (/, ., -, :, _, (, etc. such as
    "wp-content", "js.stripe.com", "_next/") keep fast substring matching.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import List


@dataclass
class RuleResult:
    matched: bool = False
    evidence: List[str] = field(default_factory=list)
    contexts: List[str] = field(default_factory=list)

    def merge(self, other: "RuleResult") -> None:
        if other.matched:
            self.matched = True
        self.evidence.extend(other.evidence)
        self.contexts.extend(other.contexts)


@lru_cache(maxsize=4096)
def _is_plain_word(value: str) -> bool:
    return re.fullmatch(r"[a-z0-9]+", value) is not None


@lru_cache(maxsize=4096)
def _boundary_pattern(value: str):
    return re.compile(r"(?<![a-z0-9])" + re.escape(value) + r"(?![a-z0-9])")


class RuleEngine:

    CONTEXT = 60

    @staticmethod
    def match(rule_values: List[str], source: str) -> RuleResult:
        result = RuleResult()
        if not rule_values or not source:
            return result

        low = source.lower()

        for value in rule_values:
            needle = value.lower()

            if _is_plain_word(needle):
                m = _boundary_pattern(needle).search(low)
                idx = m.start() if m else -1
            else:
                idx = low.find(needle)

            if idx != -1:
                result.matched = True
                result.evidence.append(value)
                end = min(len(source), idx + len(needle) + RuleEngine.CONTEXT)
                result.contexts.append(source[idx:end])

        return result
