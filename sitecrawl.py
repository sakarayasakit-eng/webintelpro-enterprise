"""
WebIntelPro Enterprise X
Multi-page Site Crawler

Follows same-domain internal links from a starting URL, analyzes each page,
and aggregates site-wide scores, the worst pages, the union of detected
technologies, and recommendations that recur across the site.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from urllib.parse import urljoin, urlparse, urldefrag

from crawler import WebCrawler
from engine import AnalysisEngine
from technology.parser import HTMLParser
from modules import duplicate_detection, indexability, adsense_readiness

_DIMENSIONS = ["overall", "seo", "security", "performance", "accessibility"]
_SEVERITY = {"critical": 0, "high": 1, "medium": 2, "low": 3}


class SiteCrawler:

    def __init__(self, max_pages: int = 10, timeout: int = 20, use_cache: bool = True,
                 debug: bool = False,
                 analyze_js: bool = False, analyze_runtime: bool = False,
                 analyze_api: bool = False, analyze_ai_stack: bool = False,
                 analyze_auth: bool = False,
                 site_checks: bool = False, measure_vitals: bool = False):
        # Note: no *_config parameters here (js_config/runtime_config/
        # api_config/ai_stack_config/auth_config). AnalysisEngine itself
        # doesn't accept or forward per-stage config objects to
        # TechnologyDetector.detect() -- only the five on/off flags below --
        # so there is nothing for SiteCrawler to plumb through yet even in
        # single-page mode. Adding config passthrough would need
        # AnalysisEngine.__init__/.analyze() extended first; out of scope
        # for this fix, which is specifically about the boolean flags being
        # silently ignored.
        self.max_pages = max_pages
        self.crawler = WebCrawler(timeout=timeout)
        # AnalysisEngine.analyze() (called once per crawled page below) reads
        # these five flags off the engine instance and forwards them into
        # TechnologyDetector.detect(), exactly like single-page mode -- so
        # simply constructing the engine with them wired here is enough to
        # fix the bug where --crawl silently ignored --js-bundles/
        # --runtime-analysis/--api-discovery/--ai-detection/--auth-detection.
        # With all five False (the default), behaviour is unchanged from
        # before this fix -- same "byte-for-byte identical to Phase 1"
        # guarantee TechnologyDetector.detect() itself documents.
        self.engine = AnalysisEngine(
            timeout=timeout, use_cache=use_cache, debug=debug,
            analyze_js=analyze_js, analyze_runtime=analyze_runtime,
            analyze_api=analyze_api, analyze_ai_stack=analyze_ai_stack,
            analyze_auth=analyze_auth)
        self.parser = HTMLParser()
        self.timeout = timeout
        # Unlike the five Phase 2 flags above, site checks (robots.txt/
        # sitemap.xml/TLS) and Core Web Vitals are NOT per-page concerns in
        # AnalysisEngine -- `analyze_url()` (which reads self.site_checks)
        # is never called from crawl_site() below, since the crawler already
        # has the page's html/headers and calls the lower-level `analyze()`
        # directly. So both are implemented here instead, and deliberately
        # run ONCE for the whole crawl, not once per page:
        #   - site_checks: robots.txt/sitemap.xml/TLS are properties of the
        #     site, not of an individual page: running them per-page (up to
        #     max_pages times) would be redundant and wasteful. Off by
        #     default so existing callers/tests (which mock WebCrawler.crawl
        #     but not the live requests.get() calls inside
        #     modules/site_checks.py) keep working offline unchanged.
        #   - measure_vitals: launching a headless browser once per crawled
        #     page would multiply cost by up to max_pages (e.g. 300x for a
        #     large crawl) for a metric that's fundamentally about a single
        #     page's load experience. This measures Core Web Vitals for the
        #     start URL only, as the crawl's most representative page. Off
        #     by default (needs Playwright installed; degrades gracefully
        #     either way via modules.vitals.measure()).
        self.site_checks = site_checks
        self.measure_vitals = measure_vitals

    def crawl_site(self, start_url: str) -> dict:
        if not start_url.startswith(("http://", "https://")):
            start_url = "https://" + start_url
        base = self._host(start_url)

        seen: set = set()
        queue: list = [start_url]
        pages: list = []
        # Parallel, non-serialized structures used only to compute
        # site-wide analyses (duplicate clustering, internal-link graph).
        # Kept out of the per-page JSON record to avoid bloating reports
        # with raw shingle sets / full link lists per page.
        dup_input: list = []          # [{"url","shingles","word_count"}]
        link_graph: dict = {}         # normalized url -> set(normalized internal urls it links to)
        crawl_errors: list = []       # per-URL error detail (crawl-reliability report)

        while queue and len(pages) < self.max_pages:
            url = queue.pop(0)
            key = self._norm(url)
            if key in seen:
                continue
            seen.add(key)
            try:
                crawl = self.crawler.crawl(url)
            except Exception as exc:  # noqa: BLE001
                err = {"url": url, "status": f"error: {type(exc).__name__}",
                       "error_detail": str(exc)}
                pages.append(err)
                crawl_errors.append(err)
                continue

            if crawl.status_code and crawl.status_code >= 400:
                err = {"url": url, "status": f"http_{crawl.status_code}",
                       "error_detail": f"HTTP {crawl.status_code}"}
                pages.append(err)
                crawl_errors.append(err)
                continue

            result = self.engine.analyze(crawl.final_url, crawl.html,
                                         crawl.headers, crawl.cookies, crawl)
            parsed = result["parsed"]
            pages.append(self._page_summary(url, result, parsed))

            # -- duplicate-content clustering input (visible text shingles) --
            text = duplicate_detection.extract_text(crawl.html)
            dup_input.append({
                "url": url,
                "shingles": duplicate_detection.shingle_set(text),
                "word_count": len(text.split()),
            })

            # -- internal link graph (for orphan / weak-inbound-link analysis) --
            outbound = set()
            queued = {self._norm(q) for q in queue}
            for link in parsed.links:
                nxt = self._norm(urljoin(crawl.final_url, link))
                if not nxt.startswith(("http://", "https://")):
                    continue
                if self._host(nxt) != base:
                    continue
                outbound.add(nxt)
                if nxt not in seen and nxt not in queued:
                    if len(seen) + len(queue) < self.max_pages * 4:
                        queue.append(nxt)
                        queued.add(nxt)
            link_graph[key] = outbound

        site_check_result = None
        if self.site_checks:
            try:
                from modules.site_checks import run_all
                site_check_result = run_all(start_url)
            except Exception:  # noqa: BLE001 -- best-effort, never break the crawl
                site_check_result = {}

        vitals_result = None
        if self.measure_vitals:
            try:
                from modules.vitals import measure
                vitals_result = measure(start_url, self.timeout)
            except Exception:  # noqa: BLE001 -- best-effort, never break the crawl
                vitals_result = {"available": False, "reason": "vitals measurement failed"}

        return self._aggregate(start_url, pages, dup_input, link_graph, crawl_errors,
                               site_check_result, vitals_result)

    # ------------------------------------------------------------- helpers
    @staticmethod
    def _host(url: str) -> str:
        h = urlparse(url).netloc.split(":")[0].lower()
        return h[4:] if h.startswith("www.") else h

    @staticmethod
    def _norm(url: str) -> str:
        u = urldefrag(url)[0]
        # collapse a trailing slash so "/x/" and "/x" (and root) dedupe
        if u.endswith("/") and urlparse(u).path not in ("", "/"):
            u = u[:-1]
        elif urlparse(u).path in ("", "/"):
            u = u.split("#")[0].rstrip("/")
        return u

    def _page_summary(self, url, result, parsed) -> dict:
        o = result["overall"]
        seo = result["seo"]
        p = urlparse(url)
        return {
            "url": url, "status": "ok",
            "path": p.path or "/", "query": p.query,
            "overall": o["score"], "grade": o["grade"],
            "seo": o["parts"]["seo"], "security": o["parts"]["security"],
            "performance": o["parts"]["performance"],
            "accessibility": o["parts"]["accessibility"],
            "technologies": sorted({t.name for t in result["technology"].technologies}),
            "recommendations": result["recommendations"],
            # Raw per-page signals (retained so site-wide analyses -- dup
            # clustering, canonical/indexability, content-quality -- don't
            # have to re-crawl; see modules/indexability.py and
            # modules/duplicate_detection.py).
            "title": seo.get("title", ""),
            "meta_description": seo.get("meta_description", ""),
            "canonical": parsed.canonical or "",
            "noindex": bool(seo.get("noindex")),
            "word_count": seo.get("word_count", 0),
            "json_ld_count": seo.get("json_ld", 0),
            "forms_count": seo.get("forms", 0),
        }

    def _aggregate(self, start_url, pages, dup_input=None, link_graph=None,
                    crawl_errors=None, site_check_result=None, vitals_result=None) -> dict:
        dup_input = dup_input or []
        link_graph = link_graph or {}
        crawl_errors = crawl_errors or []
        ok = [p for p in pages if p.get("status") == "ok"]
        averages = {}
        for dim in _DIMENSIONS:
            vals = [p[dim] for p in ok]
            averages[dim] = round(sum(vals) / len(vals)) if vals else 0

        worst = {}
        for dim in _DIMENSIONS:
            ranked = sorted(ok, key=lambda p: p[dim])
            worst[dim] = {"url": ranked[0]["url"], "score": ranked[0][dim]} if ranked else None

        tech_union = sorted({t for p in ok for t in p["technologies"]})

        # recurring recommendations across pages -- bucketed by (severity,
        # area, issue's leading label before any embedded count) so e.g.
        # "1 form field(s) without a label" / "5 form field(s) without a
        # label" consolidate into one line with a distribution instead of
        # fragmenting into up to N near-duplicate rows.
        counter: Counter = Counter()
        detail: dict = {}
        counts_seen: dict = defaultdict(list)
        for p in ok:
            for r in p["recommendations"]:
                bucket_issue = _bucket_issue(r["issue"])
                k = (r["severity"], r["area"], bucket_issue)
                counter[k] += 1
                if k not in detail:
                    detail[k] = r
                n = _leading_count(r["issue"])
                if n is not None:
                    counts_seen[k].append(n)
        recs = []
        for (sev, area, issue), count in counter.items():
            r = dict(detail[(sev, area, issue)])
            r["issue"] = issue
            r["pages_affected"] = count
            if counts_seen.get((sev, area, issue)):
                vals = counts_seen[(sev, area, issue)]
                r["distribution"] = {"min": min(vals), "max": max(vals), "total": sum(vals)}
            recs.append(r)
        recs.sort(key=lambda r: (_SEVERITY.get(r["severity"], 9), -r["pages_affected"]))

        # -- P0: query-parameter URL homogenization + P1: canonical/indexability --
        idx = indexability.run(ok, start_url, link_graph)

        # -- P1: duplicate / near-duplicate content clustering --
        clusters = duplicate_detection.cluster_pages(dup_input) if len(dup_input) >= 2 else []
        dup_summary = duplicate_detection.summarize(clusters, len(dup_input))

        # -- crawl reliability (self-audit of the crawler itself) --
        reliability = {
            "attempted": len(pages),
            "successful": len(ok),
            "failed": len(crawl_errors),
            "errors": crawl_errors[:50],
        }

        site = {
            "start_url": start_url,
            "pages_crawled": len(pages),
            "pages_ok": len(ok),
            "pages": pages,
            "averages": averages,
            "worst": worst,
            "technologies": tech_union,
            "recommendations": recs,
            "crawl_reliability": reliability,
            "duplicate_content": {"clusters": clusters, "summary": dup_summary},
            "indexability": idx,
        }
        # Optional (None unless site_checks=True / measure_vitals=True was
        # passed to the constructor) -- see the __init__ comment for why
        # these run once for the whole crawl rather than once per page.
        if site_check_result is not None:
            site["site_checks"] = site_check_result
        if vitals_result is not None:
            site["vitals"] = vitals_result
        site["adsense_readiness"] = adsense_readiness.assess(site)
        return site


# Matches a leading count, optionally as a "N/M" ratio (e.g. "5/20 images
# missing alt text"), so both plain-count and ratio-style issue strings
# bucket correctly instead of fragmenting into one row per distinct number.
_COUNT_RE = re.compile(r"^(\d+)(?:/(\d+))?\b")


def _leading_count(issue: str):
    m = _COUNT_RE.match(issue.strip())
    return int(m.group(1)) if m else None


def _bucket_issue(issue: str) -> str:
    """Collapse 'N form field(s) without a label' / 'N/M images missing alt
    text' style issues (any N, any M) into one bucket key, so recurring-issue
    rollups don't fragment by embedded count."""
    m = _COUNT_RE.match(issue.strip())
    if not m:
        return issue
    rest = issue.strip()[m.end():].lstrip()
    # normalize a leading singular/plural noun so "1 image missing" and
    # "5 images missing" also collapse together
    return "N " + rest
