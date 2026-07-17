"""
WebIntelPro Enterprise X
Live technology-detection validation harness.

Runs the detector (with debug/evidence mode on) against a curated list of
real, live websites spanning CMSs, website builders, JS frameworks, e-commerce
platforms, and plain corporate/news sites. It is a manual QA tool, not a
pytest suite: it hits the network, takes a couple of minutes, and its job is
to surface things worth a human's attention -- sites that errored, sites with
zero detections, and low-confidence ("review") detections -- rather than to
assert pass/fail.

Usage:
    python validate_live.py                  # full site list
    python validate_live.py --limit 10        # first N sites only
    python validate_live.py -o reports/validation.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone

from crawler import WebCrawler
from technology.detector import TechnologyDetector

# (url, expected-technology-substring-or-None) -- the expectation is a loose
# sanity check (e.g. "wordpress.org" really should detect WordPress), not a
# strict spec; None means "just see what comes back".
SITES = [
    ("https://wordpress.org", "WordPress"),
    ("https://en.wikipedia.org", None),
    ("https://techcrunch.com", "WordPress"),
    ("https://www.theguardian.com", None),
    ("https://www.shopify.com", None),
    ("https://www.allbirds.com", "Shopify"),
    ("https://www.gymshark.com", None),  # migrated to a headless/custom stack
    ("https://www.bigcommerce.com", None),
    ("https://www.wix.com", None),
    ("https://www.squarespace.com", None),
    ("https://webflow.com", None),
    ("https://react.dev", None),
    ("https://vuejs.org", None),  # Vite/VitePress SSR often has no live Vue runtime markers
    ("https://nextjs.org", "Next.js"),
    ("https://svelte.dev", None),
    ("https://angular.dev", None),
    ("https://stripe.com", None),  # marketing homepage doesn't load stripe.js itself
    ("https://github.com", None),
    ("https://about.gitlab.com", None),
    ("https://www.cloudflare.com", "Cloudflare"),
    ("https://vercel.com", None),
    ("https://www.netlify.com", None),
    ("https://www.nytimes.com", None),
    ("https://www.bbc.com", None),
    ("https://developer.mozilla.org", None),
    ("https://docs.python.org", None),
    ("https://www.usa.gov", None),
    ("https://www.harvard.edu", None),
    ("https://www.hubspot.com", "HubSpot"),
    ("https://mailchimp.com", None),
    ("https://www.intercom.com", None),  # messenger widget likely consent-gated
    ("https://medium.com", None),
    ("https://www.reddit.com", None),
    ("https://www.joomla.org", None),
    ("https://www.drupal.org", None),  # served behind a JS bot-check challenge page
    ("https://ghost.org", None),
    ("https://www.gatsbyjs.com", None),
    ("https://www.mozilla.org", None),
    ("https://www.python.org", None),
    ("https://tailwindcss.com", None),
    ("https://laravel.com", None),
]

REVIEW_THRESHOLD = 0.50


def run(urls, timeout=15):
    crawler = WebCrawler(timeout=timeout)
    detector = TechnologyDetector()
    results = []

    for i, (url, expect) in enumerate(urls, 1):
        row = {"url": url, "expect": expect}
        print(f"[{i:>2}/{len(urls)}] {url:<40}", end="  ", flush=True)
        start = time.perf_counter()
        try:
            crawl = crawler.crawl(url)
        except Exception as exc:  # noqa: BLE001
            row["error"] = f"{type(exc).__name__}: {exc}"
            print(f"ERROR  {row['error']}")
            results.append(row)
            continue

        report = detector.detect(crawl.final_url, crawl.html, crawl.headers,
                                  crawl.cookies, debug=True)
        elapsed = round(time.perf_counter() - start, 2)

        techs = [{"name": t.name, "category": t.category,
                  "confidence": t.confidence, "version": t.version,
                  "evidence": t.evidence[:6]}
                 for t in report.technologies]
        review = [t for t in techs if t["confidence"] < REVIEW_THRESHOLD]

        row.update({
            "status": crawl.status_code,
            "elapsed": elapsed,
            "server": report.server,
            "cms": report.cms,
            "total_detected": report.total_detected,
            "technologies": techs,
            "review": review,
            "expect_hit": (expect is None) or any(t["name"] == expect for t in techs),
        })

        flag = ""
        if expect and not row["expect_hit"]:
            flag = "  [MISSED EXPECTED: %s]" % expect
        if report.total_detected == 0:
            flag += "  [ZERO DETECTED]"
        if review:
            flag += f"  [{len(review)} low-confidence]"

        print(f"{crawl.status_code}  {report.total_detected:>2} tech  "
              f"{elapsed:>5}s{flag}")
        results.append(row)

    return results


def summarize(results):
    ok = [r for r in results if "error" not in r]
    errored = [r for r in results if "error" in r]
    zero = [r for r in ok if r["total_detected"] == 0]
    missed = [r for r in ok if not r["expect_hit"]]
    all_review = [(r["url"], t) for r in ok for t in r["review"]]

    print("\n" + "=" * 72)
    print("VALIDATION SUMMARY")
    print("=" * 72)
    print(f"Sites attempted   : {len(results)}")
    print(f"Fetched OK        : {len(ok)}")
    print(f"Fetch errors      : {len(errored)}")
    print(f"Zero detections   : {len(zero)}")
    print(f"Missed expected   : {len(missed)}")
    print(f"Low-confidence hits (<{REVIEW_THRESHOLD}): {len(all_review)}")
    if ok:
        avg = sum(r["total_detected"] for r in ok) / len(ok)
        print(f"Avg techs/site    : {avg:.1f}")

    if errored:
        print("\n-- fetch errors --")
        for r in errored:
            print(f"  {r['url']}: {r['error']}")
    if zero:
        print("\n-- zero detections (investigate) --")
        for r in zero:
            print(f"  {r['url']}")
    if missed:
        print("\n-- missed an expected technology (investigate) --")
        for r in missed:
            print(f"  {r['url']}: expected {r['expect']!r}, "
                  f"got {[t['name'] for t in r['technologies']]}")
    if all_review:
        print("\n-- low-confidence detections worth a manual look --")
        for url, t in all_review:
            print(f"  {url}: {t['name']} ({t['confidence']}) via {t['evidence']}")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--limit", type=int, help="Only test the first N sites")
    p.add_argument("-o", "--output", default="reports/validation.json",
                  help="Where to save the full JSON results")
    p.add_argument("-t", "--timeout", type=int, default=15)
    args = p.parse_args(argv)

    urls = SITES[: args.limit] if args.limit else SITES
    results = run(urls, timeout=args.timeout)
    summarize(results)

    import os
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump({
            "generated": datetime.now(timezone.utc).isoformat(),
            "site_count": len(urls),
            "results": results,
        }, f, indent=2)
    print(f"\n[saved] {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
