"""
WebIntelPro
Technology Detection Utilities

Reusable helper functions for technology detection.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional


def normalize_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """
    Normalize HTTP header names to lowercase.
    """
    return {str(k).lower(): str(v) for k, v in headers.items()}


def contains_any(text: str, keywords: Iterable[str]) -> bool:
    """
    Return True if any keyword exists in the text (case-insensitive).
    """
    if not text:
        return False

    text = text.lower()
    return any(keyword.lower() in text for keyword in keywords)


def regex_search(pattern: str, text: str, flags: int = re.IGNORECASE) -> Optional[str]:
    """
    Return the first regex match or None.
    """
    match = re.search(pattern, text, flags)
    if not match:
        return None

    if match.groups():
        return match.group(1)

    return match.group(0)


def extract_version(text: str) -> Optional[str]:
    """
    Extract a version number such as:
        1.2
        2.4.58
        17.0.1
    """
    return regex_search(r"(\d+(?:\.\d+)+)", text)


def unique_list(values: Iterable[str]) -> List[str]:
    """
    Remove duplicates while preserving order.
    """
    seen = set()
    result = []

    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)

    return result


def clamp_confidence(score: float) -> float:
    """
    Keep confidence between 0.0 and 1.0.
    """
    return max(0.0, min(1.0, score))