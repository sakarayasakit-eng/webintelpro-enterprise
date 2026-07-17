"""Offline tests for competitor comparison (mocked crawler)."""

import pytest

from compare import CompetitorComparison
from reporter import ReportGenerator
from crawler import CrawlResult, WebCrawler

SITES = {
    "https://mysite.com": (
        "<html lang='en'><head><title>My Site - great products and services</title>"
        "<meta name='description' content='" + "x" * 140 + "'>"
        "<meta name='viewport' content='width=device-width'>"
        "<link rel='canonical' href='https://mysite.com/'>"
        "<script src='https://js.stripe.com/v3/'></script>"
        "<script type='application/ld+json'>{}</script></head>"
        "<body><h1>Hi</h1><img src='a.png' alt='a'></body></html>",
        {"Server": "nginx", "Strict-Transport-Security": "max-age=1",
         "Content-Security-Policy": "default-src 'self'", "X-Frame-Options": "DENY",
         "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer",
         "Permissions-Policy": "geolocation=()", "Content-Encoding": "gzip",
         "Cache-Control": "max-age=1"}),
    "https://rival1.com": (
        "<html><head><title>Rival</title>"
        "<script src='https://widget.intercom.io/widget/x'></script></head>"
        "<body><img src='a.png'></body></html>",
        {"Server": "Apache", "X-Powered-By": "PHP/7.4"}),
    "https://rival2.com": (
        "<html lang='en'><head><title>Rival Two Site Title Goes Right Here</title>"
        "<script src='/_next/static/main.js'></script></head>"
        "<body><h1>Two</h1></body></html>",
        {"Server": "Vercel", "Strict-Transport-Security": "max-age=1"}),
}


@pytest.fixture(autouse=True)
def _mock_crawl(monkeypatch):
    def fake(self, url):
        html, headers = SITES[url]
        return CrawlResult(url=url, final_url=url, status_code=200, html=html,
                           headers=headers, cookies={}, elapsed=0.05)
    monkeypatch.setattr(WebCrawler, "crawl", fake)


def test_comparison_structure():
    cmp = CompetitorComparison(use_cache=False).compare(
        "https://mysite.com", ["https://rival1.com", "https://rival2.com"])
    assert len(cmp["sites"]) == 3
    assert cmp["sites"][0]["primary"] is True
    # mysite has full security headers -> should win overall
    assert cmp["winner"] == "https://mysite.com"
    for dim in ["overall", "seo", "security", "performance", "accessibility"]:
        assert cmp["dimensions"][dim]["winner"]
    # rival1 has Intercom, mysite does not -> shows up as a gap
    assert "Intercom" in cmp["tech_gap"]["missing"]
    # mysite has Stripe, rivals don't -> unique
    assert "Stripe" in cmp["tech_gap"]["unique"]


def test_comparison_reports(tmp_path):
    cmp = CompetitorComparison(use_cache=False).compare(
        "https://mysite.com", ["https://rival1.com"])
    rep = ReportGenerator()
    txt = rep.comparison_console_str(cmp)
    assert "Competitor Comparison" in txt and "Overall winner" in txt
    hp = tmp_path / "c.html"
    rep.save_comparison_html(cmp, str(hp))
    assert hp.read_text().startswith("<!doctype html>")
    jp = tmp_path / "c.json"
    rep.save_comparison_json(cmp, str(jp))
    import json
    assert json.loads(jp.read_text())["primary"] == "https://mysite.com"
