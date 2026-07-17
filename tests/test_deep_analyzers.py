"""Tests for the deeper analyzer checks (v3)."""

from technology.parser import HTMLParser, resource_hosts, mixed_content
from crawler import CrawlResult
from modules.technical_seo import TechnicalSEOAnalyzer
from modules.security import SecurityAnalyzer
from modules.performance import PerformanceAnalyzer
from modules.accessibility import AccessibilityAnalyzer


def test_seo_noindex_and_og():
    html = ("<html lang='en'><head><title>T</title>"
            "<meta name='robots' content='noindex,nofollow'>"
            "<meta property='og:title' content='x'></head><body><h1>H</h1></body></html>")
    parsed = HTMLParser().parse(html)
    r = TechnicalSEOAnalyzer().analyze(parsed, "https://x.com")
    assert r["noindex"] is True
    assert r["og_complete"] is False
    assert any("noindex" in i.lower() for i in r["issues"])


def test_security_cookie_flags_and_mixed_content():
    html = "<html><head><script src='http://cdn.example/x.js'></script></head><body></body></html>"
    parsed = HTMLParser().parse(html)
    set_cookie = ["sid=abc; Path=/", "theme=dark; Secure; HttpOnly; SameSite=Lax"]
    r = SecurityAnalyzer().analyze({"content-security-policy": "default-src 'self' 'unsafe-inline'"},
                                   "https://x.com", parsed, set_cookie)
    assert len(r["insecure_cookies"]) == 1          # sid missing flags
    assert r["csp_unsafe"] is True
    assert r["mixed_content"] == 1                   # http script on https page


def test_performance_third_party_and_network():
    html = ("<html><head>"
            "<script src='https://cdn.other.com/a.js'></script>"
            "<script src='/local.js'></script></head><body></body></html>")
    parsed = HTMLParser().parse(html)
    crawl = CrawlResult(url="https://x.com", final_url="https://x.com", status_code=200,
                        html=html, headers={}, cookies={}, http_version="1.1",
                        redirect_chain=[{"status": 301, "url": "http://x.com"}], ttfb=1.5)
    r = PerformanceAnalyzer().analyze(html, parsed, {}, crawl, "https://x.com")
    assert r["third_party"] == 1
    assert r["http_version"] == "1.1"
    assert any("TTFB" in i for i in r["issues"])


def test_accessibility_labels_and_landmarks():
    html = ("<html lang='en'><head><title>T</title></head><body>"
            "<form><input type='text' id='name'><input type='email' aria-label='Email'></form>"
            "<a href='/x'></a></body></html>")
    parsed = HTMLParser().parse(html)
    r = AccessibilityAnalyzer().analyze(parsed)
    assert r["unlabelled_inputs"] == 1               # text input has no label
    assert r["links_without_text"] == 1
    assert r["has_main"] is False


def test_resource_host_helpers():
    html = ("<html><head><script src='https://cdn.other.com/a.js'></script>"
            "<script src='https://www.x.com/b.js'></script>"
            "<script src='http://x.com/c.js'></script></head><body></body></html>")
    parsed = HTMLParser().parse(html)
    third, total = resource_hosts(parsed, "https://x.com")
    assert total == 3 and third == 1
    assert mixed_content(parsed, "https://x.com") == 1
