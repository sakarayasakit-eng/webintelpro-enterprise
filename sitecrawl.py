"""
WebIntelPro Enterprise X
Multi-page Site Crawler

Follows same-domain internal links from a starting URL, analyzes each page,
and aggregates site-wide scores, the worst pages, the union of detected
technologies, and recommendations that recur across the site.
"""

from __future__ import annotations

from collections import Counter
from urllib.parse import urljoin, urlparse, urldefrag

from crawler import WebCrawler
from engine import AnalysisEngine
from technology.parser import HTMLParser

_DIMENSIONS = ["overall", "seo", "security", "performance", "accessibility"]
_SEVERITY = {"critical": 0, "high": 1, "medium": 2, "low": 3}


class SiteCrawler:

    def __init__(self, max_pages: int = 10, timeout: int = 20, use_cache: bool = True):
        self.max_pages = max_pages
        self.crawler = WebCrawler(timeout=timeout)
        self.engine = AnalysisEngine(timeout=timeout, use_cache=use_cache)
        self.parser = HTMLParser()

    def crawl_site(self, start_url: str) -> dict:
        if not start_url.startswith(("http://", "https://")):
            start_url = "https://" + start_url
        base = self._host(start_url)

        seen: set = set()
        queue: list = [start_url]
        pages: list = []

        while queue and len(pages) < self.max_pages:
            url = queue.pop(0)
            key = self._norm(url)
            if key in seen:
                continue
            seen.add(key)
            try:
                crawl = self.crawler.crawl(url)
            except Exception as exc:  # noqa: BLE001
                pages.append({"url": url, "status": f"error: {type(exc).__name__}"})
                continue

            result = self.engine.analyze(crawl.final_url, crawl.html,
                                         crawl.headers, crawl.cookies, crawl)
            pages.append(self._page_summary(url, result))

            parsed = self.parser.parse(crawl.html)
            queued = {self._norm(q) for q in queue}
            for link in parsed.links:
                nxt = self._norm(urljoin(crawl.final_url, link))
                if not nxt.startswith(("http://", "https://")):
                    continue
                if self._host(nxt) != base:
                    continue
                if nxt not in seen and nxt not in queued:
                    if len(seen) + len(queue) < self.max_pages * 4:
                        queue.append(nxt)
                        queued.add(nxt)

        return self._aggregate(start_url, pages)

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

    def _page_summary(self, url, result) -> dict:
        o = result["overall"]
        return {
            "url": url, "status": "ok",
            "overall": o["score"], "grade": o["grade"],
            "seo": o["parts"]["seo"], "security": o["parts"]["security"],
            "performance": o["parts"]["performance"],
            "accessibility": o["parts"]["accessibility"],
            "technologies": sorted({t.name for t in result["technology"].technologies}),
            "recommendations": result["recommendations"],
        }

    def _aggregate(self, start_url, pages) -> dict:
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

        # recurring recommendations across pages
        counter: Counter = Counter()
        detail: dict = {}
        for p in ok:
            for r in p["recommendations"]:
                k = (r["severity"], r["area"], r["issue"])
                counter[k] += 1
                detail[k] = r
        recs = []
        for (sev, area, issue), count in counter.items():
            r = dict(detail[(sev, area, issue)])
            r["pages_affected"] = count
            recs.append(r)
        recs.sort(key=lambda r: (_SEVERITY.get(r["severity"], 9), -r["pages_affected"]))

        return {
            "start_url": start_url,
            "pages_crawled": len(pages),
            "pages_ok": len(ok),
            "pages": pages,
            "averages": averages,
            "worst": worst,
            "technologies": tech_union,
            "recommendations": recs,
        }
