"""
WebIntelPro Enterprise X
Core Analysis Engine

crawl -> technology detection -> SEO / security / performance / accessibility
-> overall scoring -> prioritized recommendations. Optionally enriches a live
scan with robots.txt / sitemap / TLS site checks.
"""

from __future__ import annotations

from crawler import WebCrawler
from technology.detector import TechnologyDetector
from modules.technical_seo import TechnicalSEOAnalyzer
from modules.security import SecurityAnalyzer
from modules.performance import PerformanceAnalyzer
from modules.accessibility import AccessibilityAnalyzer
from modules.intelligence import IntelligenceEngine
from modules.grading import grade

_OVERALL_WEIGHTS = {"seo": 0.25, "security": 0.30, "performance": 0.25, "accessibility": 0.20}


class AnalysisEngine:

    def __init__(self, timeout: int = 20, user_agent: str = "",
                 use_cache: bool = False, site_checks: bool = False,
                 debug: bool = False, analyze_js: bool = False,
                 analyze_runtime: bool = False):
        self.crawler = WebCrawler(timeout=timeout, user_agent=user_agent)
        self.detector = TechnologyDetector()
        self.seo = TechnicalSEOAnalyzer()
        self.security = SecurityAnalyzer()
        self.performance = PerformanceAnalyzer()
        self.accessibility = AccessibilityAnalyzer()
        self.intelligence = IntelligenceEngine()
        self.use_cache = use_cache
        self.site_checks = site_checks
        self.debug = debug
        # Phase 2A: when True, detection additionally downloads and inspects
        # JavaScript bundles. Off by default so behaviour is unchanged.
        self.analyze_js = analyze_js
        # Phase 2B: when True, detection additionally reads the page's
        # JavaScript runtime surface (no browser, no extra requests) and
        # attaches structured findings. Off by default.
        self.analyze_runtime = analyze_runtime

    def analyze(self, url: str, html: str = "", headers: dict | None = None,
                cookies: dict | None = None, crawl=None) -> dict:
        headers = headers or {}
        cookies = cookies or {}

        set_cookie = list(getattr(crawl, "set_cookie", []) or [])
        if not set_cookie and headers.get("Set-Cookie"):
            set_cookie = [headers["Set-Cookie"]]

        technology = self.detector.detect(url, html, headers, cookies,
                                           debug=self.debug, analyze_js=self.analyze_js,
                                           analyze_runtime=self.analyze_runtime)
        parsed = self.detector.parser.parse(html)

        seo = self.seo.analyze(parsed, url)
        security = self.security.analyze(headers, url, parsed, set_cookie)
        performance = self.performance.analyze(html, parsed, headers, crawl, url)
        accessibility = self.accessibility.analyze(parsed)

        overall = self._overall(seo, security, performance, accessibility)
        recommendations = self.intelligence.recommend(
            seo, security, performance, accessibility, technology)
        rec_summary = self.intelligence.summarize(recommendations)

        return {
            "url": url, "technology": technology,
            "seo": seo, "security": security, "performance": performance,
            "accessibility": accessibility, "overall": overall,
            "recommendations": recommendations, "recommendation_summary": rec_summary,
        }

    def analyze_url(self, url: str) -> dict:
        crawl = None
        if self.use_cache:
            from core.cache import CrawlCache
            crawl = CrawlCache().get(url)
        if crawl is None:
            crawl = self.crawler.crawl(url)
            if self.use_cache:
                from core.cache import CrawlCache
                CrawlCache().put(crawl)

        result = self.analyze(url=crawl.final_url, html=crawl.html,
                              headers=crawl.headers, cookies=crawl.cookies, crawl=crawl)
        result["crawl"] = crawl

        if self.site_checks:
            try:
                from modules.site_checks import run_all
                site = run_all(crawl.final_url)
                result["site"] = site
                extra = self.intelligence.site_recommendations(site)
                if extra:
                    from modules.intelligence import SEVERITY_RANK
                    result["recommendations"] = sorted(
                        result["recommendations"] + extra,
                        key=lambda r: SEVERITY_RANK.get(r["severity"], 9))
                    result["recommendation_summary"] = self.intelligence.summarize(
                        result["recommendations"])
            except Exception:
                result["site"] = {}
        return result

    def _overall(self, seo, security, performance, accessibility) -> dict:
        parts = {"seo": seo["score"], "security": security["score"],
                 "performance": performance["score"], "accessibility": accessibility["score"]}
        score = round(sum(parts[k] * w for k, w in _OVERALL_WEIGHTS.items()))
        return {"score": score, "grade": grade(score), "parts": parts}
