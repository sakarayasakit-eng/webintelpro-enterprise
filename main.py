"""
WebIntelPro Enterprise X - command-line entry point.

Single site:
    python main.py https://example.com
    python main.py example.com -f all -o reports/example
Batch:
    python main.py a.com b.com c.com -f html
    python main.py --input urls.txt -f json
Compare:
    python main.py mysite.com --vs rival1.com rival2.com
    python main.py mysite.com --vs rival.com -f html -o reports/compare
Cache:
    python main.py example.com --cache
    python main.py --clear-cache
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

from engine import AnalysisEngine
from reporter import ReportGenerator

_EXT = {"json": "json", "html": "html", "excel": "xlsx", "pdf": "pdf"}
_FILE_FORMATS = ("json", "html", "excel", "pdf")


def banner() -> None:
    print("=" * 64)
    print("        WebIntelPro Enterprise X")
    print("        Enterprise Website Intelligence")
    print("=" * 64)


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="webintelpro",
        description="Analyze website technology, SEO, security, performance "
                    "and accessibility.")
    p.add_argument("urls", nargs="*", help="One or more website URLs")
    p.add_argument("--vs", nargs="+", metavar="URL",
                   help="Competitor URLs to compare against the primary URL")
    p.add_argument("--crawl", type=int, metavar="N",
                   help="Crawl up to N same-domain pages (site-wide analysis)")
    p.add_argument("--history", action="store_true",
                   help="Show score history/trend for the URL and exit")
    p.add_argument("--vitals", action="store_true",
                   help="Measure Core Web Vitals (needs a headless browser)")
    p.add_argument("-f", "--format", default="console",
                   choices=["console", "json", "html", "excel", "pdf", "all"],
                   help="Output format (default: console)")
    p.add_argument("-o", "--output", help="Output file, or directory/basename")
    p.add_argument("-t", "--timeout", type=int, default=20, help="Crawl timeout (s)")
    p.add_argument("--input", help="File with one URL per line (batch mode)")
    p.add_argument("--cache", action="store_true", help="Use the on-disk crawl cache")
    p.add_argument("--clear-cache", action="store_true", help="Clear the cache and exit")
    p.add_argument("-q", "--quiet", action="store_true", help="Suppress the banner")
    p.add_argument("-d", "--debug", action="store_true",
                   help="Show per-technology detection evidence (matched "
                        "source, patterns, confidence weight)")
    p.add_argument("--js-bundles", action="store_true",
                   help="Also download and inspect JavaScript bundles "
                        "(Phase 2A JS bundle intelligence; adds network cost)")
    p.add_argument("--runtime-analysis", action="store_true",
                   help="Also analyze the JavaScript runtime surface -- "
                        "globals, hydration, API endpoints, runtime config, "
                        "state management, PWA (Phase 2B; no browser, no "
                        "extra requests)")
    p.add_argument("--api-discovery", action="store_true",
                   help="Also discover the page's API surface -- REST/JSON "
                        "endpoints, GraphQL, Swagger/OpenAPI, RPC (JSON-RPC/"
                        "XML-RPC/tRPC/gRPC-Web), WebSocket, SSE (Phase 2C; "
                        "reads HTML/JS only, no extra requests unless "
                        "reachability probing is separately configured)")
    p.add_argument("--ai-detection", action="store_true",
                   help="Also identify the page's AI stack -- providers "
                        "(OpenAI, Anthropic, Gemini, ...), open-source "
                        "models, local AI (Ollama, ...), frameworks "
                        "(LangChain, ...), SDKs, vector databases, embedding "
                        "services, infrastructure (Phase 2D; reads HTML/JS/"
                        "headers only, no extra requests)")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    if args.clear_cache:
        from core.cache import CrawlCache
        print(f"Cleared {CrawlCache().clear()} cached crawl(s).")
        return 0

    urls = list(args.urls)
    if args.input:
        from batch import BatchScanner
        urls += BatchScanner.load_urls(args.input)
    if not urls:
        print("error: provide at least one URL or --input FILE", file=sys.stderr)
        return 2

    if not args.quiet:
        banner()

    if args.history:
        return _run_history(urls[0])
    if args.crawl and args.crawl > 1:
        return _run_site(urls[0], args)
    if args.vs:
        if len(urls) != 1:
            print("error: --vs needs exactly one primary URL", file=sys.stderr)
            return 2
        return _run_compare(urls[0], args)
    if len(urls) > 1:
        return _run_batch(urls, args)
    return _run_single(urls[0], args)


def _run_single(url, args) -> int:
    if not args.quiet:
        print(f"\nTarget: {url}\n")
    engine = AnalysisEngine(timeout=args.timeout, use_cache=args.cache,
                            site_checks=True, debug=args.debug,
                            analyze_js=args.js_bundles,
                            analyze_runtime=args.runtime_analysis,
                            analyze_api=args.api_discovery,
                            analyze_ai_stack=args.ai_detection)
    reporter = ReportGenerator()
    try:
        result = engine.analyze_url(url)
    except Exception as exc:  # noqa: BLE001
        print("ERROR\n" + "-" * 64 + f"\n{type(exc).__name__}: {exc}")
        return 1

    if args.vitals:
        from modules.vitals import measure
        result["vitals"] = measure(url, args.timeout)
    from trends import TrendTracker
    TrendTracker().record(result)
    if args.format in ("console", "all"):
        reporter.console(result)
    for f in _FILE_FORMATS:
        if args.format in (f, "all"):
            path = _resolve(args.output, f, url)
            getattr(reporter, f"save_{f}")(result, path)
            print(f"[saved] {f.upper()} report -> {path}")
    return 0


def _run_batch(urls, args) -> int:
    from batch import BatchScanner
    formats = ["json", "html"] if args.format in ("console", "all") else [args.format]
    out_dir = args.output or "reports/batch"
    print(f"\nBatch scanning {len(urls)} sites -> {out_dir}\n")
    res = BatchScanner(timeout=args.timeout, use_cache=args.cache).scan(
        urls, out_dir=out_dir, formats=formats)
    print(f"{'URL':40} {'SCORE':>6} {'GRADE':>6}  STATUS")
    print("-" * 70)
    for row in res["summary"]:
        if row.get("status") == "ok":
            print(f"{row['url'][:40]:40} {row['score']:>6} {row['grade']:>6}  ok")
        else:
            print(f"{row['url'][:40]:40} {'-':>6} {'-':>6}  {row.get('status')}")
    print("-" * 70)
    print(f"[saved] summary -> {out_dir}/summary.json  and  summary.csv")
    return 0


def _run_compare(primary, args) -> int:
    from compare import CompetitorComparison
    if not args.quiet:
        print(f"\nComparing {primary} vs {', '.join(args.vs)}\n")
    cmp = CompetitorComparison(timeout=args.timeout,
                               use_cache=args.cache).compare(primary, args.vs)
    reporter = ReportGenerator()
    if args.format in ("console", "all", "excel", "pdf"):
        reporter.comparison_console(cmp)
    if args.format in ("html", "all"):
        path = _resolve(args.output, "html", primary, prefix="compare")
        reporter.save_comparison_html(cmp, path)
        print(f"[saved] comparison HTML -> {path}")
    if args.format in ("json", "all"):
        path = _resolve(args.output, "json", primary, prefix="compare")
        reporter.save_comparison_json(cmp, path)
        print(f"[saved] comparison JSON -> {path}")
    return 0


def _run_site(url, args) -> int:
    from sitecrawl import SiteCrawler
    if not args.quiet:
        print(f"\nSite crawl: {url} (up to {args.crawl} pages)\n")
    site = SiteCrawler(max_pages=args.crawl, timeout=args.timeout,
                       use_cache=args.cache).crawl_site(url)
    from trends import TrendTracker
    TrendTracker().record_site(site)
    reporter = ReportGenerator()
    if args.format in ("console", "all", "excel", "pdf"):
        reporter.site_console(site)
    if args.format in ("html", "all"):
        path = _resolve(args.output, "html", url, prefix="site")
        reporter.save_site_html(site, path); print(f"[saved] site HTML -> {path}")
    if args.format in ("json", "all"):
        path = _resolve(args.output, "json", url, prefix="site")
        reporter.save_site_json(site, path); print(f"[saved] site JSON -> {path}")
    return 0


def _run_history(url) -> int:
    from trends import TrendTracker
    print(TrendTracker().format_history(url))
    return 0


def _resolve(output, fmt, url, prefix="report") -> str:
    ext = _EXT[fmt]
    if output:
        base, has_ext = os.path.splitext(output)
        if has_ext and output.lower().endswith(tuple("." + e for e in _EXT.values())):
            return output
        path = f"{base}.{ext}"
    else:
        os.makedirs("reports", exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join("reports", f"{prefix}_{stamp}.{ext}")
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    return path


if __name__ == "__main__":
    sys.exit(main())
