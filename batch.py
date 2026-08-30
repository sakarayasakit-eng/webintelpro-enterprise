"""
WebIntelPro Enterprise X
Batch Scanner

Scans multiple URLs and produces per-site reports plus an aggregate summary.
"""

from __future__ import annotations

import csv
import json
import os

from engine import AnalysisEngine
from reporter import ReportGenerator


class BatchScanner:

    def __init__(self, timeout: int = 20, use_cache: bool = True, debug: bool = False,
                 site_checks: bool = False,
                 analyze_js: bool = False, analyze_runtime: bool = False,
                 analyze_api: bool = False, analyze_ai_stack: bool = False,
                 analyze_auth: bool = False):
        # scan() calls engine.analyze_url() per URL, which already reads all
        # of these off the engine instance -- same fix shape as
        # CompetitorComparison.__init__ (see the comment there for why no
        # special-casing is needed and why the defaults are all False).
        self.engine = AnalysisEngine(
            timeout=timeout, use_cache=use_cache, debug=debug, site_checks=site_checks,
            analyze_js=analyze_js, analyze_runtime=analyze_runtime,
            analyze_api=analyze_api, analyze_ai_stack=analyze_ai_stack,
            analyze_auth=analyze_auth)
        self.reporter = ReportGenerator()

    def scan(self, urls: list, out_dir: str = "reports/batch",
             formats: list | None = None) -> dict:
        formats = formats or ["json"]
        os.makedirs(out_dir, exist_ok=True)
        summary = []

        for url in urls:
            row = {"url": url}
            try:
                result = self.engine.analyze_url(url)
                o = result["overall"]
                row.update({
                    "status": "ok",
                    "score": o["score"], "grade": o["grade"],
                    "seo": o["parts"]["seo"], "security": o["parts"]["security"],
                    "performance": o["parts"]["performance"],
                    "accessibility": o["parts"]["accessibility"],
                    "technologies": result["technology"].total_detected,
                    "server": result["technology"].server or "",
                    "cms": result["technology"].cms or "",
                    "critical": result["recommendation_summary"]["by_severity"]["critical"],
                    "high": result["recommendation_summary"]["by_severity"]["high"],
                })
                self._save_site(result, out_dir, url, formats)
            except Exception as exc:  # noqa: BLE001
                row.update({"status": f"error: {type(exc).__name__}: {exc}"})
            summary.append(row)

        self._write_summary(summary, out_dir)
        return {"count": len(urls), "summary": summary, "out_dir": out_dir}

    def _save_site(self, result, out_dir, url, formats):
        slug = self._slug(url)
        base = os.path.join(out_dir, slug)
        if "json" in formats:
            self.reporter.save_json(result, base + ".json")
        if "html" in formats:
            self.reporter.save_html(result, base + ".html")
        if "excel" in formats:
            self.reporter.save_excel(result, base + ".xlsx")
        if "pdf" in formats:
            self.reporter.save_pdf(result, base + ".pdf")

    def _write_summary(self, summary, out_dir):
        with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        if summary:
            keys = sorted({k for row in summary for k in row})
            with open(os.path.join(out_dir, "summary.csv"), "w",
                      newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=keys)
                w.writeheader()
                w.writerows(summary)

    @staticmethod
    def _slug(url: str) -> str:
        s = url.replace("https://", "").replace("http://", "")
        return "".join(c if c.isalnum() else "_" for c in s).strip("_")[:60] or "site"

    @staticmethod
    def load_urls(path: str) -> list:
        with open(path, "r", encoding="utf-8") as f:
            return [ln.strip() for ln in f
                    if ln.strip() and not ln.strip().startswith("#")]
