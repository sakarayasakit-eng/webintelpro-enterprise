"""
WebIntelPro Enterprise X
Confidence Engine

Combines matched evidence sources into a single confidence score using a
noisy-OR model:  confidence = 1 - PRODUCT(1 - weight_i) over matched sources.

This lets a single strong, specific signal (e.g. a response header or a
script URL) identify a technology on its own, while multiple independent
signals reinforce each other toward higher confidence.
"""

from __future__ import annotations

from typing import Dict

from .rules import RuleResult


class ConfidenceEngine:

    # Extra, independently-weaker credit for each additional distinct pattern
    # matched within the same source (e.g. three different script URLs for
    # the same technology is stronger corroboration than just one).
    EXTRA_EVIDENCE_FACTOR = 0.3
    MAX_EXTRA_PER_SOURCE = 3

    # Evidential strength of each source (probability the match is real).
    WEIGHTS = {
    "headers": 0.60,
    "cookies": 0.55,
    "scripts": 0.50,
    # Downloaded JavaScript bundle *contents* (Phase 2A bundle intelligence).
    # Weighed like "scripts": a runtime marker inside a bundle is strong,
    # direct evidence. Only fingerprints from the JS-bundle stage use this
    # source key, so it never affects HTML/header/cookie scoring.
    "js_bundle": 0.50,
    "meta": 0.45,
    "stylesheets": 0.40,
    "inline": 0.35,
    "dom": 0.30,
    "json_ld": 0.30,
    "favicon": 0.25,
    "canonical": 0.15,

    "html": 0.30,
    "body": 0.30,
    "comments": 0.20,
    "url": 0.40,
    "dns": 0.45,
    "tls": 0.40,
    "http2": 0.25,
    "http3": 0.30,
    "response": 0.40,
}

    def calculate(self, matches: Dict[str, RuleResult]) -> float:
        product = 1.0
        matched_any = False

        for source, result in matches.items():
            if not result.matched:
                continue
            matched_any = True
            weight = self.WEIGHTS.get(source, 0.10)
            product *= (1.0 - weight)

            # Multiple distinct matched patterns within the same source are
            # corroborating but not independent evidence, so each extra one
            # only contributes a fraction of the source's base weight, with
            # a cap so a source with many patterns can't dominate the score.
            extra_matches = min(
                len(set(result.evidence)) - 1, self.MAX_EXTRA_PER_SOURCE
            )
            if extra_matches > 0:
                extra_weight = weight * self.EXTRA_EVIDENCE_FACTOR
                product *= (1.0 - extra_weight) ** extra_matches

        if not matched_any:
            return 0.0

        return round(1.0 - product, 3)

    def breakdown(self, matches: Dict[str, RuleResult]) -> Dict[str, dict]:
        """Per-source detail for debug/evidence mode: what matched, the base
        weight used, and how many extra corroborating patterns were counted."""
        info: Dict[str, dict] = {}
        for source, result in matches.items():
            if not result.matched:
                continue
            distinct = sorted(set(result.evidence))
            info[source] = {
                "weight": self.WEIGHTS.get(source, 0.10),
                "patterns": distinct,
                "extra_matches": min(
                    len(distinct) - 1, self.MAX_EXTRA_PER_SOURCE
                ),
            }
        return info
