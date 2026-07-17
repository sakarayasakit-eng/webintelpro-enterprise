"""Tests for Core Web Vitals rating + graceful fallback (no browser)."""

from modules.vitals import measure, _rate


def test_rating_thresholds():
    assert _rate("lcp", 2000) == "good"
    assert _rate("lcp", 3000) == "needs-improvement"
    assert _rate("lcp", 5000) == "poor"
    assert _rate("cls", 0.05) == "good"
    assert _rate("cls", 0.3) == "poor"
    assert _rate("ttfb", None) == "unknown"


def test_measure_graceful_without_browser():
    # No Playwright/browser in the test environment -> graceful unavailable.
    out = measure("https://example.com", timeout=3)
    assert out["available"] is False
    assert "reason" in out
