from technology.detector import TechnologyDetector
from technology.fingerprints import TECH_FINGERPRINTS


def names(report):
    return {t.name for t in report.technologies}


def test_fingerprint_db_schema():
    required = ["name", "category", "headers", "meta", "scripts", "inline", "dom"]
    assert len(TECH_FINGERPRINTS) >= 100
    for fp in TECH_FINGERPRINTS:
        for key in required:
            assert key in fp, f"{fp.get('name')} missing {key}"


def test_detects_core_stack(wordpress_html, wordpress_headers, wordpress_cookies):
    d = TechnologyDetector()
    r = d.detect("https://acme.example", wordpress_html,
                 wordpress_headers, wordpress_cookies)
    found = names(r)
    assert "WordPress" in found
    assert "WooCommerce" in found
    assert "Stripe" in found
    assert "Nginx" in found
    assert r.server == "Nginx"
    assert r.cms == "WordPress"


def test_single_header_signal_detects():
    d = TechnologyDetector()
    r = d.detect("https://x.example", "<html></html>",
                 {"Strict-Transport-Security": "max-age=1"}, {})
    assert "HSTS" in names(r)


def test_version_extraction():
    d = TechnologyDetector()
    r = d.detect("https://x.example",
                 '<meta name="generator" content="WordPress 6.4">',
                 {"Server": "nginx/1.25.3"}, {})
    versions = {t.name: t.version for t in r.technologies}
    assert versions.get("WordPress") == "6.4"
    assert versions.get("Nginx") == "1.25.3"


def test_no_false_positive_on_empty():
    d = TechnologyDetector()
    r = d.detect("https://x.example", "<html><body></body></html>", {}, {})
    assert r.total_detected == 0
