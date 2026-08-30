"""Offline tests for multi-page site crawling (mocked crawler)."""

import pytest

from sitecrawl import SiteCrawler
from crawler import CrawlResult, WebCrawler

def _page(title, body, links):
    lk = "".join(f"<a href='{h}'>{t}</a>" for h, t in links)
    return (f"<html lang='en'><head><title>{title}</title></head>"
            f"<body><h1>{title}</h1>{body}{lk}</body></html>")

SITE = {
    "https://demo.com": _page("Home", "<img src='a.png'>",
                              [("/about", "About"), ("/contact", "Contact"),
                               ("https://external.com/x", "Ext")]),
    "https://demo.com/about": _page("About", "<p>About us</p>", [("/", "Home")]),
    "https://demo.com/contact": _page("Contact", "<form><input type='text'></form>",
                                      [("/about", "About")]),
}
HEADERS = {"Server": "nginx", "Content-Encoding": "gzip", "Cache-Control": "max-age=1"}


@pytest.fixture(autouse=True)
def _mock(monkeypatch):
    def fake(self, url):
        html = SITE.get(url) or SITE.get(url.rstrip("/"))
        if html is None:
            raise RuntimeError("404")
        return CrawlResult(url=url, final_url=url, status_code=200, html=html,
                           headers=HEADERS, cookies={}, elapsed=0.05)
    monkeypatch.setattr(WebCrawler, "crawl", fake)


def test_site_crawl_follows_internal_links():
    site = SiteCrawler(max_pages=10, use_cache=False).crawl_site("https://demo.com")
    urls = {p["url"] for p in site["pages"]}
    assert "https://demo.com" in urls
    assert "https://demo.com/about" in urls        # discovered internal link
    assert "https://demo.com/contact" in urls
    assert not any("external.com" in u for u in urls)   # stays on-domain
    assert site["pages_ok"] == 3


def test_site_crawl_aggregates():
    site = SiteCrawler(max_pages=10, use_cache=False).crawl_site("https://demo.com")
    for dim in ["overall", "seo", "security", "performance", "accessibility"]:
        assert 0 <= site["averages"][dim] <= 100
    assert site["worst"]["overall"]["url"] in {p["url"] for p in site["pages"]}
    assert isinstance(site["technologies"], list)
    # security issues recur across pages
    assert any(r["pages_affected"] >= 2 for r in site["recommendations"])


def test_site_crawl_respects_max_pages():
    site = SiteCrawler(max_pages=1, use_cache=False).crawl_site("https://demo.com")
    assert site["pages_crawled"] == 1


def test_site_crawl_wires_new_analysis_sections():
    site = SiteCrawler(max_pages=10, use_cache=False).crawl_site("https://demo.com")
    assert "duplicate_content" in site
    assert "clusters" in site["duplicate_content"] and "summary" in site["duplicate_content"]
    assert "indexability" in site
    assert set(site["indexability"].keys()) == {"query_variants", "canonicals", "internal_links"}
    assert "adsense_readiness" in site
    assert "disclaimer" in site["adsense_readiness"]
    assert "crawl_reliability" in site
    assert site["crawl_reliability"]["attempted"] == site["pages_crawled"]
    assert site["crawl_reliability"]["successful"] == site["pages_ok"]
    # raw per-page signals retained (P1 requirement)
    for p in site["pages"]:
        if p["status"] == "ok":
            assert "title" in p and "canonical" in p and "word_count" in p


def test_site_crawl_consolidates_fragmented_recurring_issues(monkeypatch):
    """1 unlabelled field on one page vs 3 on another must roll up into ONE
    recurring recommendation (with a distribution), not two separate lines
    that only differ by the embedded count -- this was a real report-quality
    bug (visible in the actual fincalcyou production report)."""
    site_html = {
        "https://demo2.com": _page(
            "Home", "<form><input type='text'></form>",  # 1 unlabelled field
            [("/two", "Two")]),
        "https://demo2.com/two": _page(
            "Two", "<form><input type='text'><input type='email'><input type='tel'></form>",  # 3
            [("/", "Home")]),
    }

    def fake(self, url):
        html = site_html.get(url) or site_html.get(url.rstrip("/"))
        if html is None:
            raise RuntimeError("404")
        return CrawlResult(url=url, final_url=url, status_code=200, html=html,
                           headers=HEADERS, cookies={}, elapsed=0.05)
    monkeypatch.setattr(WebCrawler, "crawl", fake)

    site = SiteCrawler(max_pages=10, use_cache=False).crawl_site("https://demo2.com")
    unlabel_recs = [r for r in site["recommendations"]
                    if r["area"] == "Accessibility" and "form field" in r["issue"]]
    assert len(unlabel_recs) == 1, f"expected one consolidated line, got {unlabel_recs}"
    rec = unlabel_recs[0]
    assert rec["pages_affected"] == 2
    assert rec["distribution"]["min"] == 1
    assert rec["distribution"]["max"] == 3


def test_site_crawl_consolidates_ratio_style_recurring_issues(monkeypatch):
    """'5/8 images missing alt text' vs '2/3 images missing alt text' must
    also consolidate (ratio-count variant of the same bucketing bug)."""
    site_html = {
        "https://demo4.com": _page(
            "Home",
            "<img><img><img src='a.png'><img src='b.png'><img src='c.png'>"
            "<img src='d.png'><img src='e.png'><img src='f.png'>",  # 8 imgs, 2 with alt-missing avoided via src only (no alt attr on any -> 8/8 actually)
            [("/two", "Two")]),
        "https://demo4.com/two": _page(
            "Two", "<img><img><img src='x.png'>",  # 3 imgs, all missing alt
            [("/", "Home")]),
    }

    def fake(self, url):
        html = site_html.get(url) or site_html.get(url.rstrip("/"))
        if html is None:
            raise RuntimeError("404")
        return CrawlResult(url=url, final_url=url, status_code=200, html=html,
                           headers=HEADERS, cookies={}, elapsed=0.05)
    monkeypatch.setattr(WebCrawler, "crawl", fake)

    site = SiteCrawler(max_pages=10, use_cache=False).crawl_site("https://demo4.com")
    alt_recs = [r for r in site["recommendations"]
                if r["area"] == "Accessibility" and "missing alt text" in r["issue"]]
    assert len(alt_recs) == 1, f"expected one consolidated line, got {alt_recs}"
    assert alt_recs[0]["pages_affected"] == 2


def test_site_crawl_forwards_phase2_flags_to_detector(monkeypatch):
    """Regression test for the wiring bug: --crawl silently ignored
    --js-bundles/--runtime-analysis/--api-discovery/--ai-detection/
    --auth-detection because SiteCrawler couldn't accept or forward them.
    A page carrying an OpenAI SDK signature should only be identified as
    using OpenAI when analyze_ai_stack=True is actually threaded through to
    TechnologyDetector.detect()."""
    ai_html = ("<html><head><title>Home</title></head><body><h1>Home</h1>"
              "<script>import { OpenAI } from \"openai\"; "
              "const c = new OpenAI({apiKey: \"sk-x\"});</script></body></html>")

    def fake(self, url):
        return CrawlResult(url=url, final_url=url, status_code=200, html=ai_html,
                           headers=HEADERS, cookies={}, elapsed=0.05)
    monkeypatch.setattr(WebCrawler, "crawl", fake)

    off = SiteCrawler(max_pages=1, use_cache=False).crawl_site("https://ai-demo.com")
    assert "OpenAI" not in off["pages"][0]["technologies"]

    on = SiteCrawler(max_pages=1, use_cache=False,
                     analyze_ai_stack=True).crawl_site("https://ai-demo.com")
    assert "OpenAI" in on["pages"][0]["technologies"]


def test_site_crawl_site_checks_and_vitals_wiring(monkeypatch):
    """site_checks/measure_vitals run once for the whole crawl (not once per
    page -- see SiteCrawler.__init__), only when explicitly requested, and
    are absent from the output entirely when not requested (matching the
    pre-fix output shape exactly, so existing consumers see no change)."""
    def fake_crawl(self, url):
        return CrawlResult(url=url, final_url=url, status_code=200,
                           html=_page("Home", "", []), headers=HEADERS,
                           cookies={}, elapsed=0.05)
    monkeypatch.setattr(WebCrawler, "crawl", fake_crawl)

    import modules.site_checks as site_checks_mod
    import modules.vitals as vitals_mod
    calls = {"site_checks": 0, "vitals": 0}

    def fake_run_all(url):
        calls["site_checks"] += 1
        return {"robots": {"exists": True, "disallow": 1, "sitemaps": []},
                "sitemap": {"exists": True, "urls": 5},
                "tls": {"checked": True, "protocol": "TLSv1.3",
                        "expires_in_days": 60, "issuer": "Test"}}

    def fake_measure(url, timeout=20):
        calls["vitals"] += 1
        return {"available": True, "engine": "playwright",
                "metrics": {"lcp": {"value": 1000.0, "rating": "good"}}}

    monkeypatch.setattr(site_checks_mod, "run_all", fake_run_all)
    monkeypatch.setattr(vitals_mod, "measure", fake_measure)

    # off by default -- no keys, no calls
    off = SiteCrawler(max_pages=3, use_cache=False).crawl_site("https://demo.com")
    assert "site_checks" not in off and "vitals" not in off
    assert calls == {"site_checks": 0, "vitals": 0}

    # on -- keys present, called exactly once regardless of page count
    on = SiteCrawler(max_pages=3, use_cache=False, site_checks=True,
                     measure_vitals=True).crawl_site("https://demo.com")
    assert on["site_checks"]["robots"]["exists"] is True
    assert on["vitals"]["available"] is True
    assert calls == {"site_checks": 1, "vitals": 1}, (
        "site_checks/vitals must run once per crawl, not once per page")


def test_query_variant_detection(monkeypatch):
    site_html = {
        "https://demo3.com/": _page("Home", "", [
            ("/?cur=AED", "AED"), ("/?cur=USD", "USD"), ("/?cur=GBP", "GBP")]),
        "https://demo3.com/?cur=AED": _page("Home AED", "", []),
        "https://demo3.com/?cur=USD": _page("Home USD", "", []),
        "https://demo3.com/?cur=GBP": _page("Home GBP", "", []),
    }

    def fake(self, url):
        html = site_html.get(url) or site_html.get(url.rstrip("/"))
        if html is None:
            raise RuntimeError("404")
        return CrawlResult(url=url, final_url=url, status_code=200, html=html,
                           headers=HEADERS, cookies={}, elapsed=0.05)
    monkeypatch.setattr(WebCrawler, "crawl", fake)

    site = SiteCrawler(max_pages=10, use_cache=False).crawl_site("https://demo3.com/")
    qv = site["indexability"]["query_variants"]
    assert qv["paths_with_query_variants"] >= 1
    group = qv["groups"][0]
    assert group["variant_count"] >= 3
    # none of these pages declare a canonical -> should be flagged, not silently ignored
    assert group["canonicalizes_to_single_url"] is False
