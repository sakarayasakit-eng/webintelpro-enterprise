# WebIntelPro Enterprise X

A website intelligence tool. Give it a URL and it crawls the page, detects the
technology stack, and analyzes SEO, security, performance, and accessibility —
then produces a report (console, JSON, HTML, Excel, or PDF) with a blended
score and a prioritized, severity-ranked list of recommendations.

## Highlights

- **Technology detection** — 512 fingerprints across 27 categories: frameworks,
  JS libraries, build tools, CMS, servers, CDNs, hosting, analytics,
  security/WAF, e-commerce, payments, marketing, chat, fonts, PWA, privacy,
  media, and more.
- **Noisy-OR confidence engine** — a single strong, specific signal (a response
  header, script URL, or cookie) can identify a technology; multiple signals,
  or multiple distinct matched patterns within one signal, reinforce each
  other (with diminishing returns). Includes proximity-aware version
  extraction and a `--debug` mode that shows the per-source evidence and
  confidence weight behind every detection.
- **Four deep analyzers** (SEO, security, performance, accessibility) with graded
  scores (A-F) and issue lists — Open Graph/robots/canonical/hreflang, cookie
  flags/CSP quality/mixed content, third-party & TTFB/HTTP-version/redirects,
  form labels/landmarks/ARIA — plus live robots.txt, sitemap and TLS checks.
- **Intelligence layer** — aggregates findings into prioritized recommendations
  (critical / high / medium / low) with concrete remediation guidance.
- **Reports** in console, JSON, standalone HTML dashboard, Excel, and PDF.
- **Batch scanning** of many URLs with an aggregate CSV/JSON summary, plus an
  on-disk crawl cache.
- **Competitor comparison** — score your site head-to-head against rivals,
  rank every dimension, and see the technology gap (console + HTML).
- **Site-wide crawling** — follow same-domain links, score every page, and
  surface averages, the weakest pages, and recurring issues.
- **Trend tracking** — each scan is recorded so you can see scores move over time.
- **Core Web Vitals** — optional headless-browser LCP/CLS/FCP/TTFB measurement.

## Requirements

- Python 3.10+
- Dependencies in `requirements.txt`

## Installation

```bash
python -m venv venv
# Windows:  venv\Scripts\activate      macOS/Linux:  source venv/bin/activate
pip install -r requirements.txt
```

## Usage

Single site:

```bash
python main.py https://example.com                 # console report
python main.py example.com -f html -o report.html  # HTML dashboard
python main.py example.com -f pdf  -o report.pdf   # PDF
python main.py example.com -f excel -o report.xlsx # Excel workbook
python main.py example.com -f all  -o reports/site # console + all files
```

Batch (multiple URLs or a file, one URL per line):

```bash
python main.py a.com b.com c.com -f html
python main.py --input urls.txt -f json -o reports/run
```

Compare against competitors:

```bash
python main.py mysite.com --vs rival1.com rival2.com
python main.py mysite.com --vs rival.com -f html -o reports/compare
```

Site-wide crawl, trend history, and Core Web Vitals:

```bash
python main.py example.com --crawl 25 -f html   # crawl up to 25 same-domain pages
python main.py example.com --history            # show score trend over time
python main.py example.com --vitals             # LCP/CLS/FCP/TTFB (needs a browser)
```

Cache:

```bash
python main.py example.com --cache      # reuse cached crawl within TTL
python main.py --clear-cache            # empty the cache
```

Options: `-f/--format {console,json,html,excel,pdf,all}`, `-o/--output`,
`-t/--timeout`, `--vs`, `--crawl N`, `--history`, `--vitals`, `--input`,
`--cache`, `--clear-cache`, `-q/--quiet`, `-d/--debug`.

Debug/evidence mode (per-technology matched source, patterns and confidence
weight, for auditing why something was or wasn't detected):

```bash
python main.py example.com --debug
```

Offline demo (no network) that writes sample reports in every format:

```bash
python demo_offline.py   # reports/sample_report.{json,html,xlsx,pdf}
```

Live validation harness (manual QA tool, not part of `pytest`) that runs the
detector against ~40 real websites and reports fetch errors, zero-detection
sites, missed expectations, and low-confidence matches worth a manual look:

```bash
python validate_live.py                # full curated site list
python validate_live.py --limit 10     # first N sites only
```

## Project layout

```
main.py              CLI (single + batch modes)
engine.py            AnalysisEngine - crawl + analysis + scoring + recommendations
crawler.py           WebCrawler - HTML, headers, cookies
batch.py             BatchScanner - multi-URL scans + aggregate summary
compare.py           CompetitorComparison - head-to-head benchmarking
sitecrawl.py         SiteCrawler - multi-page site-wide analysis
trends.py            TrendTracker - score history over time
reporter.py          Console / JSON / HTML / Excel / PDF output
config.yaml          Crawler / report / cache settings

technology/          Technology detection subsystem
  detector.py  parser.py  matcher.py  rules.py
  confidence.py (noisy-OR)  version.py  models.py
  fingerprints/      fingerprint database (one module per category)

modules/             Analyzers + intelligence
  technical_seo.py  security.py  performance.py  accessibility.py
  intelligence.py (recommendations)  grading.py (A-F helper)
  site_checks.py (robots/sitemap/TLS)  vitals.py (Core Web Vitals)

core/                config.py  logger.py  cache.py (crawl cache)
tests/               pytest suite (detector, analyzers, reporter,
                     intelligence, exporters, cache)
```

## Fingerprint database

Fingerprints live in `technology/fingerprints/`, one module per category, each
exporting a `FINGERPRINTS` list; `fingerprints/__init__.py` aggregates them into
`TECH_FINGERPRINTS`. Each entry is a dict; `headers`, `meta`, `scripts`,
`inline`, `dom` are required, and `cookies`, `stylesheets`, `json_ld`,
`favicon`, `canonical` are optional. Values are case-insensitive substrings
matched against the corresponding page source.

To add a technology, append a dict to the relevant module (or add a module and
register it in `fingerprints/__init__.py`).

## Testing

```bash
pytest -q
```

## Roadmap

- Parallel/async crawling and scheduled scans.
- Structured-data (JSON-LD) schema validation.
- Historical charts in the HTML dashboard.
