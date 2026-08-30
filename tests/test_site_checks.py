"""Offline tests for site-check recommendation logic (no network)."""

from modules.intelligence import IntelligenceEngine


def test_site_recs_missing_robots_sitemap():
    site = {"robots": {"exists": False}, "sitemap": {"exists": False}, "tls": {}}
    recs = IntelligenceEngine().site_recommendations(site)
    issues = [r["issue"] for r in recs]
    assert "No robots.txt" in issues
    assert any(i.startswith("No sitemap.xml") for i in issues)


def test_site_recs_expiring_cert():
    site = {"robots": {"exists": True}, "sitemap": {"exists": True},
            "tls": {"checked": True, "expires_in_days": 5, "protocol": "TLSv1.3"}}
    recs = IntelligenceEngine().site_recommendations(site)
    assert any(r["severity"] == "high" and "expires" in r["issue"] for r in recs)


def test_site_recs_old_tls():
    site = {"tls": {"checked": True, "expires_in_days": 200, "protocol": "TLSv1.1"}}
    recs = IntelligenceEngine().site_recommendations(site)
    assert any("Outdated TLS" in r["issue"] for r in recs)


def test_site_recs_clean():
    site = {"robots": {"exists": True}, "sitemap": {"exists": True},
            "tls": {"checked": True, "expires_in_days": 300, "protocol": "TLSv1.3"}}
    assert IntelligenceEngine().site_recommendations(site) == []
