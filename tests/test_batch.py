"""Offline tests for batch scanning (mocked crawler)."""

import json

import pytest

from batch import BatchScanner
from crawler import CrawlResult, WebCrawler

HEADERS = {"Server": "nginx"}
PLAIN_HTML = "<html><head><title>Home</title></head><body><h1>Home</h1></body></html>"
AI_HTML = ("<html><head><title>AI Co</title></head><body><h1>AI Co</h1>"
          "<script>import { OpenAI } from \"openai\"; "
          "const c = new OpenAI({apiKey: \"sk-x\"});</script></body></html>")


@pytest.fixture(autouse=True)
def _mock_crawl(monkeypatch):
    def fake(self, url):
        html = AI_HTML if "ai" in url else PLAIN_HTML
        return CrawlResult(url=url, final_url=url, status_code=200, html=html,
                           headers=HEADERS, cookies={}, elapsed=0.05)
    monkeypatch.setattr(WebCrawler, "crawl", fake)


def test_batch_scan_summary_and_files(tmp_path):
    out_dir = str(tmp_path / "batch")
    res = BatchScanner(use_cache=False).scan(
        ["https://a.com", "https://b.com"], out_dir=out_dir, formats=["json"])
    assert res["count"] == 2
    assert len(res["summary"]) == 2
    assert all(row["status"] == "ok" for row in res["summary"])

    with open(f"{out_dir}/summary.json") as f:
        summary = json.load(f)
    assert len(summary) == 2
    import os
    assert os.path.exists(f"{out_dir}/summary.csv")


def test_batch_forwards_phase2_flags_to_engine(tmp_path):
    """Regression test: batch mode silently ignored --js-bundles/
    --runtime-analysis/--api-discovery/--ai-detection/--auth-detection
    because BatchScanner.__init__ only accepted timeout/use_cache. A site
    carrying an OpenAI SDK signature should only be identified as using
    OpenAI when analyze_ai_stack=True actually reaches the detector -- and
    since batch.py doesn't return per-URL technology names in its summary
    row, we verify via the saved per-site JSON report instead."""
    out_dir = str(tmp_path / "batch_off")
    BatchScanner(use_cache=False).scan(
        ["https://ai-site.com"], out_dir=out_dir, formats=["json"])
    with open(f"{out_dir}/ai_site_com.json") as f:
        off = json.load(f)
    off_names = {t["name"] for t in off["technology"]["technologies"]}
    assert "OpenAI" not in off_names

    out_dir_on = str(tmp_path / "batch_on")
    BatchScanner(use_cache=False, analyze_ai_stack=True).scan(
        ["https://ai-site.com"], out_dir=out_dir_on, formats=["json"])
    with open(f"{out_dir_on}/ai_site_com.json") as f:
        on = json.load(f)
    on_names = {t["name"] for t in on["technology"]["technologies"]}
    assert "OpenAI" in on_names


def test_batch_site_checks_off_by_default(tmp_path, monkeypatch):
    """site_checks defaults to False so batch scans stay fully offline
    unless explicitly requested -- verifies modules.site_checks.run_all is
    never called without the flag."""
    import modules.site_checks as site_checks_mod
    calls = []
    monkeypatch.setattr(site_checks_mod, "run_all", lambda url: calls.append(url) or {})

    out_dir = str(tmp_path / "batch")
    BatchScanner(use_cache=False).scan(["https://a.com"], out_dir=out_dir, formats=["json"])
    assert calls == []

    out_dir2 = str(tmp_path / "batch2")
    BatchScanner(use_cache=False, site_checks=True).scan(
        ["https://a.com"], out_dir=out_dir2, formats=["json"])
    assert calls == ["https://a.com"]
