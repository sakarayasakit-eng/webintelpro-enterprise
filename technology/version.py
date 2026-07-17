"""
WebIntelPro Enterprise X
Version Detection Engine

Extracts software version numbers from the text surrounding a matched
fingerprint signal (see RuleResult.contexts in rules.py, which starts each
context string at the position of the matched pattern).

Two extraction strategies, tried in order:
  1. Keyword-anchored: an explicit "version" label or a "vX.Y" token,
     searched across the whole context. The literal keyword makes these
     low-risk regardless of distance from the matched pattern.
  2. Proximity-anchored: a bare "X.Y[.Z]" number, but only if it appears
     immediately after the matched pattern (within a few characters), so an
     unrelated number later in the context (e.g. from a different header
     concatenated after the real one) is not mistaken for the version.

Extracted numbers are also sanity-checked (not all-zero, no absurdly long
numeric component) before being accepted.
"""

from __future__ import annotations

import re
from typing import Optional

# 2-4 dot-separated numeric components, each 1-4 digits (rejects things like
# long numeric IDs, timestamps, or a stray 5+ digit component).
_NUM = r"\d{1,4}(?:\.\d{1,4}){1,3}"

# How close (in characters) a bare number must be to the start of the
# context -- i.e. to the matched fingerprint pattern itself -- to be trusted
# without an explicit "version"/"v" keyword.
PROXIMITY_WINDOW = 24


class VersionEngine:
    """Extract a plausible version number from matched-signal context text."""

    KEYWORD_PATTERNS = [
        re.compile(r"version[\"'=:\s]+v?(" + _NUM + r")", re.IGNORECASE),
        re.compile(r"\bv(" + _NUM + r")\b", re.IGNORECASE),
    ]

    _BARE_NUMBER = re.compile(r"(?<![\d.])(" + _NUM + r")(?![\d.])")

    def extract(self, text: str) -> Optional[str]:
        if not text:
            return None

        for pattern in self.KEYWORD_PATTERNS:
            match = pattern.search(text)
            if match and self._plausible(match.group(1)):
                return match.group(1)

        nearby = text[:PROXIMITY_WINDOW]
        match = self._BARE_NUMBER.search(nearby)
        if match and self._plausible(match.group(1)):
            return match.group(1)

        return None

    @staticmethod
    def _plausible(version: str) -> bool:
        parts = version.split(".")
        if len(parts) < 2:
            return False
        if all(p == "0" for p in parts):
            return False
        if any(len(p) > 4 for p in parts):
            return False
        return True
