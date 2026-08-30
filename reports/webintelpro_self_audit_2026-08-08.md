# WebIntelPro Self-Audit — 2026-08-08

Scope: this pass fixed the highest-priority items from the audit mission against
the FincalcYou baseline scan (`reports/fincalcyou_full.json`, not modified).
Every claim below is grounded in code (file:line) or test output — nothing here
is asserted from memory.

## 1. Verified false positive: "Legacy HTTP/1.1" (was on all 296/296 pages)

Root cause: `requests`/urllib3, via Python's stdlib `http.client`, cannot observe
ALPN-negotiated HTTP/2 or HTTP/3 — `response.raw.version` is structurally limited
to 10/11 regardless of what the server actually serves. So the old "Legacy
HTTP/1.1" finding on every page of every scan this tool has ever run was a
guaranteed false positive, not a real observation about FincalcYou (or Netlify,
which serves HTTP/2 by default).

Fix: `crawler.py` now carries `http_version_reliable: bool = False` (honestly
always False with this transport). `modules/performance.py` and
`modules/intelligence.py` only score/flag "Legacy HTTP" when that flag is True.
Confirmed via a standalone script: `http_version: 1.1 | reliable: False | issue
present: False`.

**Action for you**: the 296-page "Legacy HTTP/1.1 (LOW)" line in the baseline
report should be disregarded — it does not indicate anything wrong with
FincalcYou's actual HTTP protocol support.

## 2. Confidence labeling added to recommendations

Every recommendation now carries `confidence: confirmed | likely | possible`.
`possible` = heuristic with legitimate alternative explanations (e.g. thin
content). `confirmed` = directly observed in headers/DOM. `likely` = strong
indirect evidence.

## 3. Investigated your core question: are the 296 pages real, unique pages?

Direct inspection of `reports/fincalcyou_full.json` (not assumed):
- 0 exact duplicate URLs across 300 rows.
- Only **one** path (`/`) has multiple query-string variants — 25 of them
  (`?cur=AED&tab=emi&amount=...` etc.).
- The "truncated slugs" visible in your pasted console output were a
  copy/paste artifact — the real paths in the JSON are intact
  (`/pages/home-loan-calculator`, `/pages/car-loan-calculator`, etc.).
- 276 unique normalized paths vs 300 URL rows.

So the 296-page number is **not** mostly duplicate/parameter noise — that fear
is not supported by the data. The one real, narrower issue is the 25
query-string variants on `/`, which the baseline report has no way to evaluate
(it discarded canonical/content data per page). That's fixed below.

## 4. New capability: duplicate/near-duplicate content clustering

`modules/duplicate_detection.py` — k-shingle (k=4) Jaccard similarity on
visible body text (script/style/template stripped), union-find clustering,
risk-rated HIGH/MEDIUM/LOW, labeled `confidence: "heuristic"` (stated
explicitly, not overclaimed). 5 tests, all passing.

## 5. New capability: canonical / indexability analysis

`modules/indexability.py`:
- Query-parameter variant groups per normalized path, with an explicit
  check of whether variants converge on one canonical URL (fine) or don't
  (indexation-dilution risk, `confidence: likely` when no canonical exists,
  `confirmed` when canonicals actively conflict).
- Self-canonical / cross-canonical reciprocation, **scoped explicitly to the
  crawled set** — the report says so, rather than implying site-wide
  certainty it can't back up.
- Internal-link "weakly linked" pages (≤1 inbound link within the crawl),
  explicitly labeled as scoped to the crawl (a link-following crawler
  structurally cannot discover true zero-inbound-link orphans — that
  limitation is stated in the output, not hidden).
7 tests, all passing.

## 6. New capability: AdSense/monetization risk report

`modules/adsense_readiness.py` — assembles observable risk factors (duplicate
clusters, unconverged query variants, thin content, security/accessibility
posture). Every response carries this disclaimer verbatim:

> "This is an OBSERVABLE risk-factor report, not an approval prediction. It
> does not know Google's current review criteria or enforcement thresholds."

5 tests, all passing. Does not predict approval odds or ranking — per your
explicit instruction not to.

## 7. Fixed report fragmentation

`sitecrawl.py._aggregate()` used to key recurring issues on exact issue text,
so "1 form field(s) without a label" / "2 form field(s)..." / up to "5 form
field(s)..." fragmented into up to 5 near-duplicate lines — this was visible
in your actual baseline report. Now buckets by issue shape (numbers stripped)
and reports one line with a `distribution: {min, max, total}`. Same fix
applied to ratio-style issues ("N/M images missing alt text"). 3 dedicated
regression tests confirm consolidation.

## 8. Crawl reliability self-audit

`sitecrawl.py` now tracks and reports `crawl_reliability: {attempted,
successful, failed, errors[]}` with per-URL error detail (exception type +
message, or HTTP status for 4xx/5xx), instead of silently dropping failed
pages from view.

## 9. Raw per-page signals retained

Per-page records now keep `title, meta_description, canonical, noindex,
word_count, json_ld_count, forms_count, path, query` — this is the plumbing
that made items 4–6 possible without re-crawling.

## Wired into every output format

Console, HTML, and JSON site reports all show duplicate clusters, query-variant
groups, canonical findings, crawl reliability, and AdSense risk factors.
Verified end-to-end with a synthetic 3-page mock site (script run, not just
unit tests) — console output, HTML file, and JSON file all produced without
error and contain the new sections.

## Test suite

**290/290 passing** (267 pre-existing + 23 new, 0 broken). All new modules
have dedicated offline tests (no network) covering both the "finds the
problem" and "doesn't false-positive on clean input" cases.

## What this pass did NOT do (explicitly, not silently)

- **No live re-crawl of FincalcYou.** My sandbox has no outbound network
  access — I verified this directly (`requests.get()` → `403 Forbidden` at
  the proxy). Everything above is verified against your existing baseline
  JSON and synthetic mock sites, not a fresh live scan. **You need to run
  the re-scan yourself** (command below) to see the new analyses on the real
  site — the current `reports/fincalcyou_full.json` predates this work and
  has no canonical/text data for the new modules to analyze.
- **Not yet built**: structured-data (JSON-LD schema-type) correctness
  analysis, content-quality/YMYL scoring beyond word-count thin-content
  heuristics, competitor gap analysis, deep verification of the JS-bundle /
  API-discovery / AI-stack / auth-detection modules your Cursor work added
  in Phase 2A–2E, and a full 20-section executive report generator. These
  remain open — flagging them rather than claiming completion.
- **Technology detection ("Google Fonts, HSTS, Netlify" only)** was not
  re-investigated this pass — that's a real open question from your mission
  (whether the fingerprint DB is under-detecting FincalcYou's actual stack)
  and needs its own pass against live response data.

## Re-run this yourself (PowerShell)

```powershell
cd C:\Users\HP\WebIntelPro
python -m pytest -q
python main.py https://fincalcyou.com --crawl 300 --vitals --js-bundles --runtime-analysis --api-discovery --ai-detection --auth-detection -f all -o .\reports\fincalcyou\_v2
```

Do not overwrite the existing baseline — the `_v2` suffix keeps
`fincalcyou_full.json`/`.html` intact for before/after comparison. Diff the
two: pages_ok count, technologies list, and the new `duplicate_content` /
`indexability` / `adsense_readiness` sections will only be populated in `_v2`.
