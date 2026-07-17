"""WebIntelPro Enterprise X - shared grading helpers for analyzers."""

from __future__ import annotations


def grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def clamp(score: int) -> int:
    return max(0, min(100, score))
