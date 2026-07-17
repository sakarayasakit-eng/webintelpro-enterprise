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
