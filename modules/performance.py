"""WebIntelPro Enterprise X - Performance Analyzer"""

from __future__ import annotations

from .grading import grade, clamp
from technology.parser import resource_hosts


class PerformanceAnalyzer:

    def analyze(self, html: str, parsed, headers: dict, crawl=None, url: str = "") -> dict:
        headers = {k.lower(): v for k, v in headers.items()}
        r: dict = {}
        issues: list = []

        r["html_size"] = len(html.encode("utf-8"))
        r["scripts"] = len(parsed.scripts)
        r["stylesheets"] = len(parsed.stylesheets)
        r["images"] = len(parsed.images)
        r["links"] = len(parsed.links)
        r["inline_scripts"] = len(parsed.inline_scripts)
        r["resource_hints"] = len(parsed.resource_hints)
        r["iframes"] = len(parsed.iframes)

        encoding = headers.get("content-encoding", "").lower()
        r["gzip"] = "gzip" in encoding
        r["brotli"] = "br" in encoding
        r["cache_control"] = "cache-control" in headers

        # third-party resources
        third, total = resource_hosts(parsed, url) if url else (0, 0)
        r["third_party"] = third
        r["total_resources"] = total

        # network metadata (present only for live crawls)
        r["ttfb"] = round(getattr(crawl, "ttfb", 0.0), 3) if crawl else 0.0
        r["http_version"] = getattr(crawl, "http_version", "") if crawl else ""
        r["redirects"] = len(getattr(crawl, "redirect_chain", []) or []) if crawl else 0

        score = 100
        if r["html_size"] > 1_000_000:
            score -= 15; issues.append(f"Large HTML document ({r['html_size']:,} bytes)")
        if r["scripts"] > 40:
            score -= 15; issues.append(f"Many external scripts ({r['scripts']})")
        elif r["scripts"] > 20:
            score -= 7; issues.append(f"High script count ({r['scripts']})")
        if r["stylesheets"] > 15:
            score -= 8; issues.append(f"Many stylesheets ({r['stylesheets']})")
        if r["images"] > 50:
            score -= 8; issues.append(f"Many images ({r['images']})")
        if r["third_party"] > 20:
            score -= 10; issues.append(f"Many third-party resources ({r['third_party']})")
        elif r["third_party"] > 10:
            score -= 5; issues.append(f"High third-party resource count ({r['third_party']})")
        if not r["gzip"] and not r["brotli"]:
            score -= 18; issues.append("No gzip/brotli compression")
        if not r["cache_control"]:
            score -= 12; issues.append("No Cache-Control header")
        if r["redirects"] >= 2:
            score -= 6; issues.append(f"Redirect chain of {r['redirects']} hop(s)")
        if r["http_version"] in ("1.0", "1.1"):
            score -= 5; issues.append(f"Legacy HTTP/{r['http_version']} (no HTTP/2+)")
        if r["ttfb"] and r["ttfb"] > 1.2:
            score -= 10; issues.append(f"Slow TTFB ({r['ttfb']:.2f}s)")
        elif r["ttfb"] and r["ttfb"] > 0.6:
            score -= 5; issues.append(f"Elevated TTFB ({r['ttfb']:.2f}s)")

        r["score"] = clamp(score)
        r["grade"] = grade(r["score"])
        r["issues"] = issues
        return r
