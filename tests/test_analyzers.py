from technology.parser import HTMLParser
from modules.technical_seo import TechnicalSEOAnalyzer
from modules.security import SecurityAnalyzer
from modules.performance import PerformanceAnalyzer
from modules.accessibility import AccessibilityAnalyzer


def test_seo_scoring(wordpress_html):
    parsed = HTMLParser().parse(wordpress_html)
    r = TechnicalSEOAnalyzer().analyze(parsed)
    assert r["has_h1"] is True
    assert r["h1_count"] == 1
    assert 0 <= r["score"] <= 100
    assert r["grade"] in ("A", "B", "C", "D", "F")


def test_security_flags_missing_headers():
    r = SecurityAnalyzer().analyze({"Server": "nginx"}, "https://x.example")
    assert r["https"] is True
    assert r["csp"] is False
    assert any("Content-Security-Policy" in i for i in r["issues"])


def test_security_http_penalised():
    r = SecurityAnalyzer().analyze({}, "http://x.example")
    assert r["https"] is False
    assert any("HTTPS" in i for i in r["issues"])


def test_performance_compression(wordpress_html):
    parsed = HTMLParser().parse(wordpress_html)
    r = PerformanceAnalyzer().analyze(wordpress_html, parsed,
                                      {"Content-Encoding": "gzip"})
    assert r["gzip"] is True


def test_accessibility_alt_text(wordpress_html):
    parsed = HTMLParser().parse(wordpress_html)
    r = AccessibilityAnalyzer().analyze(parsed)
    assert r["total_images"] == 2
    assert r["missing_alt"] == 1   # one img has no alt
    assert r["has_h1"] is True
