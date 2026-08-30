"""Offline tests for the AdSense/monetization observable risk-factor report."""

from modules import adsense_readiness as ar


def _base_site(**overrides):
    site = {
        "duplicate_content": {"clusters": [], "summary": {}},
        "indexability": {"query_variants": {"groups": []}},
        "pages": [],
        "averages": {"security": 90, "accessibility": 90},
    }
    site.update(overrides)
    return site


def test_no_factors_on_clean_site():
    site = _base_site(pages=[{"status": "ok", "word_count": 800}])
    result = ar.assess(site)
    assert result["factors"] == []
    assert result["summary"]["total"] == 0
    assert "disclaimer" in result and result["disclaimer"]


def test_high_risk_duplicate_cluster_flagged():
    site = _base_site(duplicate_content={
        "clusters": [{"risk": "HIGH", "size": 5, "similarity_pct": 95.0}],
        "summary": {},
    }, pages=[{"status": "ok", "word_count": 800}])
    result = ar.assess(site)
    assert any(f["severity"] == "high" for f in result["factors"])
    assert all(f["confidence"] for f in result["factors"])


def test_thin_content_flagged():
    site = _base_site(pages=[{"status": "ok", "word_count": 50} for _ in range(8)])
    result = ar.assess(site)
    factor = next(f for f in result["factors"] if "Thin" in f["factor"])
    assert factor["confidence"] == "possible"
    assert factor["severity"] == "medium"  # >5 thin pages


def test_low_security_flagged():
    site = _base_site(averages={"security": 40, "accessibility": 90},
                      pages=[{"status": "ok", "word_count": 800}])
    result = ar.assess(site)
    assert any("security" in f["factor"].lower() for f in result["factors"])


def test_disclaimer_never_claims_approval():
    site = _base_site(pages=[{"status": "ok", "word_count": 800}])
    result = ar.assess(site)
    text = result["disclaimer"].lower()
    assert "not" in text and ("prediction" in text or "predict" in text)
