"""Tests for trend tracking."""

from types import SimpleNamespace

from trends import TrendTracker


def _result(url, overall, parts, tech=5):
    return {"url": url, "overall": {"score": overall, "parts": parts},
            "technology": SimpleNamespace(total_detected=tech)}


def test_record_and_history(tmp_path):
    t = TrendTracker(path=str(tmp_path / "trends.json"))
    parts = {"seo": 80, "security": 70, "performance": 90, "accessibility": 85}
    t.record(_result("https://x.com", 80, parts))
    t.record(_result("https://x.com", 88, {**parts, "security": 85}))
    hist = t.history("https://x.com")
    assert len(hist) == 2
    d = t.delta("https://x.com")
    assert d["overall"] == 8 and d["security"] == 15
    assert "Change since previous scan" in t.format_history("https://x.com")


def test_history_empty(tmp_path):
    t = TrendTracker(path=str(tmp_path / "trends.json"))
    assert "No history" in t.format_history("https://none.com")


def test_record_site(tmp_path):
    t = TrendTracker(path=str(tmp_path / "trends.json"))
    site = {"start_url": "https://x.com",
            "averages": {"overall": 75, "seo": 80, "security": 60,
                         "performance": 85, "accessibility": 70},
            "technologies": ["A", "B"], "pages_ok": 4}
    t.record_site(site)
    assert t.history("https://x.com")[0]["scope"] == "site"
