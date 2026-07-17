from engine import AnalysisEngine
from modules.intelligence import IntelligenceEngine


def test_recommendations_prioritised(wordpress_html, wordpress_headers, wordpress_cookies):
    result = AnalysisEngine().analyze("http://acme.example", wordpress_html,
                                      wordpress_headers, wordpress_cookies)
    recs = result["recommendations"]
    assert recs, "expected recommendations"
    # HTTP (not HTTPS) must yield a critical item, sorted first
    assert recs[0]["severity"] == "critical"
    assert any("HTTPS" in r["issue"] for r in recs)
    summary = result["recommendation_summary"]
    assert summary["total"] == len(recs)
    assert summary["by_severity"]["critical"] >= 1


def test_clean_site_has_no_criticals():
    seo = {"title": "A great descriptive page title for testing here", "title_ok": True,
           "title_length": 45, "meta_description": "x" * 140, "has_h1": True,
           "multiple_h1": False, "h1_count": 1, "has_canonical": True,
           "canonical_absolute": True, "has_viewport": True, "open_graph": 3,
           "og_complete": True, "json_ld": 1, "noindex": False, "thin_content": False}
    sec = {"https": True, "csp": True, "csp_unsafe": False, "hsts": True,
           "hsts_max_age": 31536000, "mixed_content": 0, "insecure_cookies": [],
           "x_frame_options": True, "x_content_type": True, "referrer_policy": True,
           "permissions_policy": True, "powered_by": ""}
    perf = {"gzip": True, "brotli": False, "cache_control": True, "scripts": 5,
            "html_size": 20000, "third_party": 2, "redirects": 0,
            "http_version": "2.0", "ttfb": 0.1}
    acc = {"total_images": 3, "missing_alt": 0, "language": True,
           "skipped_heading_levels": False, "unlabelled_inputs": 0, "has_main": True,
           "landmark_count": 3, "links_without_text": 0}
    recs = IntelligenceEngine().recommend(seo, sec, perf, acc)
    assert recs == []
