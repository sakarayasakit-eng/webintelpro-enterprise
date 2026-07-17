"""
WebIntelPro Enterprise X
Phase 1 detection benchmark runner.

Drives the curated ground-truth dataset (tests/benchmark_sites.json) through the
shipped pipeline -- WebCrawler.crawl() -> TechnologyDetector.detect() -- and
scores the engine against it per docs/verification/phase1_verification.md.

It does NOT modify the detection engine, the fingerprint database, or the
dataset. It only reads them. Every missed expectation is classified as either:

  * REGRESSION   -- a technology that HAS a fingerprint failed on a site where it
                    should have matched. Must be zero for the engine to pass.
  * COVERAGE GAP -- a technology with no fingerprint yet was (expectedly) not
                    detected. Roadmap item, not a failure.

The REGRESSION vs COVERAGE-GAP divider is derived at runtime from
technology/fingerprints.py, never hand-maintained.

Usage:
    python benchmark.py                       # full dataset (~46 sites, hits network)
    python benchmark.py --limit 10            # first N sites only
    python benchmark.py --offline             # skip crawl; report coverage only
    python benchmark.py -o reports/benchmark.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

from crawler import WebCrawler
from technology.detector import TechnologyDetector
from technology.fingerprints import TECH_FINGERPRINTS

DATASET = os.path.join("tests", "benchmark_sites.json")


def load_dataset(path=DATASET):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data["sites"]


def fingerprinted_names():
    """Technologies that currently have a fingerprint -- the set whose misses
    count as REGRESSIONS rather than coverage gaps."""
    return {rule["name"] for rule in TECH_FINGERPRINTS}


def run(sites, supported, timeout=15):
    crawler = WebCrawler(timeout=timeout)
    detector = TechnologyDetector()
    results = []

    for i, site in enumerate(sites, 1):
        url = site["url"]
        expected = list(site.get("expected", []))
        # 'hard' = genuinely-present but not statically observable here; recorded
        # for documentation/bonus, never scored as a regression. See dataset
        # conventions.hard_semantics.
        hard = list(site.get("hard", []))
        row = {"url": url, "primary": site.get("primary"), "expected": expected,
               "hard": hard}
        print(f"[{i:>2}/{len(sites)}] {url:<38}", end="  ", flush=True)

        start = time.perf_counter()
        try:
            crawl = crawler.crawl(url)
        except Exception as exc:  # noqa: BLE001
            row["error"] = f"{type(exc).__name__}: {exc}"
            print(f"ERROR  {row['error']}")
            results.append(row)
            continue

        report = detector.detect(crawl.final_url, crawl.html, crawl.headers,
                                 crawl.cookies)
        elapsed = round(time.perf_counter() - start, 2)

        detected = {t.name for t in report.technologies}
        exp = set(expected)
        hard_set = set(hard)

        tp = sorted(exp & detected)
        misses = sorted(exp - detected)
        # 'hard' techs are never scored; any we happen to detect are bonus.
        extras = sorted(detected - exp - hard_set)
        hard_hits = sorted(hard_set & detected)

        regressions = [m for m in misses if m in supported]
        gaps = [m for m in misses if m not in supported]

        row.update({
            "status": crawl.status_code,
            "elapsed": elapsed,
            "detected": sorted(detected),
            "true_positives": tp,
            "hard_hits": hard_hits,
            "regressions": regressions,
            "coverage_gaps": gaps,
            "extras": extras,
            # A site passes when every SUPPORTED expectation was detected.
            "passed": len(regressions) == 0,
        })

        flag = ""
        if regressions:
            flag += f"  [REGRESSION: {', '.join(regressions)}]"
        if gaps:
            flag += f"  [gap: {', '.join(gaps)}]"
        print(f"{crawl.status_code}  {len(tp)}/{len(exp)} expected  "
              f"{elapsed:>5}s{flag}")
        results.append(row)

    return results


def summarize(results, sites, supported):
    ok = [r for r in results if "error" not in r]
    errored = [r for r in results if "error" in r]

    tp_total = sum(len(r["true_positives"]) for r in ok)
    hard_hit_total = sum(len(r.get("hard_hits", [])) for r in ok)
    hard_total = sum(len(r.get("hard", [])) for r in ok)
    reg_total = sum(len(r["regressions"]) for r in ok)
    gap_total = sum(len(r["coverage_gaps"]) for r in ok)
    extra_total = sum(len(r["extras"]) for r in ok)

    denom = tp_total + reg_total  # supported-subset expectations that were tested
    recall = (tp_total / denom) if denom else None

    # Coverage: distinct required technologies for which a fingerprint exists.
    required = set()
    for s in sites:
        required.update(s.get("expected", []))
    covered = required & supported

    print("\n" + "=" * 72)
    print("PHASE 1 BENCHMARK SUMMARY")
    print("=" * 72)
    print(f"Sites attempted        : {len(results)}")
    print(f"Fetched OK             : {len(ok)}")
    print(f"Fetch errors           : {len(errored)}")
    print(f"Fingerprinted techs    : {len(supported)}  ({', '.join(sorted(supported))})")
    print(f"Coverage (required)    : {len(covered)}/{len(required)} technologies fingerprinted")
    print(f"True positives         : {tp_total}")
    print(f"REGRESSIONS            : {reg_total}   (must be 0 to pass)")
    print(f"Coverage-gap misses    : {gap_total}   (roadmap, not failures)")
    print(f"Extra detections       : {extra_total}   (review only)")
    print(f"Hard (unscored) hits   : {hard_hit_total}/{hard_total}   (bonus: not-statically-observable techs still detected)")
    if recall is not None:
        print(f"Recall (supported set) : {recall:.2f}")

    regressed = [r for r in ok if r["regressions"]]
    if regressed:
        print("\n-- REGRESSIONS (fingerprinted tech missed -- investigate engine) --")
        for r in regressed:
            print(f"  {r['url']}: missed {r['regressions']} "
                  f"(detected {r['detected']})")

    if errored:
        print("\n-- fetch errors (may be bot-challenge / network, see caveats) --")
        for r in errored:
            print(f"  {r['url']}: {r['error']}")

    verdict = "PASS" if reg_total == 0 and not errored else \
              ("PASS (with fetch errors -- verify caveats)" if reg_total == 0 else "FAIL")
    print("\n" + "=" * 72)
    print(f"VERDICT: {verdict}")
    print("=" * 72)
    return reg_total == 0


def report_offline(sites, supported):
    """No network: just report the dataset's coverage against the engine."""
    required = set()
    for s in sites:
        required.update(s.get("expected", []))
    covered = sorted(required & supported)
    gaps = sorted(required - supported)
    print("=" * 72)
    print("OFFLINE COVERAGE REPORT (no network requests)")
    print("=" * 72)
    print(f"Dataset sites          : {len(sites)}")
    print(f"Required technologies  : {len(required)}")
    print(f"Fingerprinted now      : {len(covered)}  -> {covered}")
    print(f"Coverage gaps          : {len(gaps)}  -> {gaps}")


def main(argv=None):
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--limit", type=int, help="Only test the first N sites")
    p.add_argument("--offline", action="store_true",
                   help="Report coverage from the dataset without crawling")
    p.add_argument("-o", "--output", default="reports/benchmark.json",
                   help="Where to save the full JSON results")
    p.add_argument("-t", "--timeout", type=int, default=15)
    p.add_argument("-d", "--dataset", default=DATASET)
    args = p.parse_args(argv)

    sites = load_dataset(args.dataset)
    if args.limit:
        sites = sites[: args.limit]
    supported = fingerprinted_names()

    if args.offline:
        report_offline(sites, supported)
        return 0

    results = run(sites, supported, timeout=args.timeout)
    passed = summarize(results, sites, supported)

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump({
            "generated": datetime.now(timezone.utc).isoformat(),
            "dataset": args.dataset,
            "site_count": len(sites),
            "fingerprinted": sorted(supported),
            "results": results,
        }, f, indent=2)
    print(f"\n[saved] {args.output}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
