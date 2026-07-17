"""Tests for Core Web Vitals rating + graceful fallback (no browser).

The browser is always stubbed here. These tests must not depend on whether
Playwright and its binaries happen to be installed, and must not launch a real
browser or load a real page: that made the suite slow, online, and dependent on
example.com being reachable.
"""

from modules import vitals
from modules.vitals import measure, _rate


def test_rating_thresholds():
    assert _rate("lcp", 2000) == "good"
    assert _rate("lcp", 3000) == "needs-improvement"
    assert _rate("lcp", 5000) == "poor"
    assert _rate("cls", 0.05) == "good"
    assert _rate("cls", 0.3) == "poor"
    assert _rate("ttfb", None) == "unknown"


def test_measure_graceful_without_browser(monkeypatch):
    """No usable browser -> report unavailable instead of raising.

    The absence is simulated, not assumed: this asserts the fallback path
    itself, so it holds whether or not a browser is installed here.
    """
    def no_browser(url, timeout):
        raise ImportError("No module named 'playwright'")

    monkeypatch.setattr(vitals, "_with_playwright", no_browser)
    out = measure("https://example.com", timeout=3)
    assert out["available"] is False
    assert "reason" in out


def test_measure_reports_metrics_when_a_browser_is_available(monkeypatch):
    """The happy path, with the browser stubbed: raw timings -> rated metrics."""
    def fake_browser(url, timeout):
        return {"lcp": 2000.0, "cls": 0.05, "fcp": 3500.0, "ttfb": None}

    monkeypatch.setattr(vitals, "_with_playwright", fake_browser)
    out = measure("example.com", timeout=3)

    assert out["available"] is True
    assert out["engine"] == "playwright"
    assert out["metrics"]["lcp"] == {"value": 2000.0, "rating": "good"}
    assert out["metrics"]["fcp"] == {"value": 3500.0, "rating": "poor"}
    # A metric the page never reported stays None rather than becoming 0.
    assert out["metrics"]["ttfb"] == {"value": None, "rating": "unknown"}
