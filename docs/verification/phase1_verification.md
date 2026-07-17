# WebIntelPro — Phase 1 Detection Verification

**Status:** Validation framework (this document + `tests/benchmark_sites.json`)
**Scope of this deliverable:** documentation and benchmark dataset **only**.
**Explicitly out of scope:** the detection engine (`technology/detector.py`), the
fingerprint database (`technology/fingerprints.py`), and every other engine
module. None of them are modified by Phase 1 verification work.

---

## 1. Purpose

Phase 1 establishes a **stable, versioned ground truth** for the technology
detection engine so that its accuracy can be measured objectively and tracked
over time. Before this framework, "does detection work?" was answered by ad-hoc
manual spot checks (`validate_live.py`). Phase 1 replaces that with:

1. A curated benchmark of ~46 well-known websites (`tests/benchmark_sites.json`),
   each annotated with the technologies it is **expected** to expose.
2. A documented methodology (this file) for turning benchmark runs into
   precision / recall / accuracy numbers and a pass/fail verdict.

The benchmark is a **specification**. The engine is judged against it. The
benchmark is never edited to make a failing engine look like it passes.

---

## 2. What Phase 1 does and does not verify

| Verified | Not verified (later phases) |
| --- | --- |
| The engine correctly identifies the **primary** platform/framework of a known site | Version extraction accuracy |
| Detections match a canonical, stable name vocabulary | Exhaustive per-site technology inventory (every script/pixel) |
| No regressions: a technology that detects today still detects tomorrow | Performance / latency SLAs |
| Coverage gaps are explicit and tracked, not silent | Non-HTTP or authenticated targets |

---

## 3. The dataset — `tests/benchmark_sites.json`

### 3.1 Shape

```json
{
  "schema_version": "1.0",
  "sites": [
    { "url": "https://nextjs.org", "primary": "Next.js", "expected": ["Next.js", "Vercel"] }
  ]
}
```

Each site object contains:

- **`url`** — a live, public homepage over HTTPS.
- **`expected`** — ground-truth technologies the live page is known to ship
  (the required field from the task spec).
- **`primary`** — the single technology the site was chosen to exercise. This is
  a grouping/traceability aid for reporting; `expected` always includes it.

### 3.2 Naming authority

Every name in `expected` is **canonical**. Where a fingerprint already exists,
the name matches `technology/fingerprints.py` **exactly**. This is critical:
the verifier compares `expected` strings against `Technology.name` strings by
equality, so `"Vue"` vs `"Vue.js"` is the difference between pass and fail.

| Task list wrote | Canonical name used in dataset (matches the engine) |
| --- | --- |
| Vue | **Vue.js** |
| Nuxt | **Nuxt.js** |
| Tailwind | **Tailwind CSS** |
| GTM | **Google Tag Manager** |
| GA / Google Analytics | **Google Analytics 4** |
| Next.js / React / WordPress / Shopify | unchanged (already the engine's name) |

These mappings were verified by reconciling every `expected` string against the
live `{rule["name"] for rule in TECH_FINGERPRINTS}` set, not assumed.

### 3.3 Coverage

46 sites span all 30 required technology families. Multiple exemplars are
included for the highest-value platforms (WordPress ×5, Shopify ×4, Next.js ×5,
React ×4) so a single site going offline or changing stacks does not blind the
suite for that technology.

---

## 4. Ground truth vs. current engine coverage

This is the most important thing to understand when reading a benchmark run.

The benchmark encodes what each site **actually is**. The engine's fingerprint
database is the **`technology/fingerprints/` package** — a loader
(`fingerprints/__init__.py`) that aggregates ~30 per-category modules
(`javascript`, `cms`, `servers`, `css`, `analytics`, `cdn`, `frameworks`,
`hosting`, `security`, `ecommerce`, `payments`, `marketing`, …) into a single
`TECH_FINGERPRINTS` list. As of this writing that list contains **504
fingerprints**.

> Note on a stale file: a legacy `technology/fingerprints.py` module (5 rules)
> also exists in the tree, but Python resolves `from .fingerprints import …` to
> the **package**, so `fingerprints.py` is dead code and is *not* what the
> detector loads. Always read coverage from the imported `TECH_FINGERPRINTS`,
> never from that file. The benchmark runner does exactly this.

Of the 30 required technology families, **28 have a fingerprint** in the engine.
Exactly **2 do not** and are genuine, documented coverage gaps:

- **Hugo** (ground truth: `gohugo.io`)
- **Jekyll** (ground truth: `jekyllrb.com`)

These two remain in the dataset as truthful ground truth; the engine is simply
expected to miss them until fingerprints are added.

Therefore a benchmark miss falls into exactly one of two buckets, and the
verifier must classify every miss as one of them:

| Bucket | Meaning | Action |
| --- | --- | --- |
| **REGRESSION** | A technology *with* a fingerprint (one of the 28) failed on a site where it should have matched | Bug — investigate the engine immediately |
| **COVERAGE GAP** | A technology with *no* fingerprint (Hugo, Jekyll) was expectedly not detected | Roadmap item — feeds fingerprint backlog, not a failure of Phase 1 |

This separation is deliberate: it lets Phase 1 pass (the engine is correct for
what it claims to support) while making the roadmap to full coverage explicit
and measurable. The set of currently-fingerprinted technologies is the
authoritative divider and is **derived at runtime** from the imported
`TECH_FINGERPRINTS`, never hand-maintained here — so this document stays correct
even as fingerprints are added or removed.

---

## 5. Methodology

### 5.1 Data collection

For each site, the standard pipeline is exercised unchanged:

```
WebCrawler.crawl(url)  ->  TechnologyDetector.detect(final_url, html, headers, cookies)
```

`crawler.py` and `technology/detector.py` are used exactly as shipped. The
detector's own gate applies: a technology is reported only when its confidence
score `>= TechnologyDetector.MIN_CONFIDENCE` (currently **0.30**).

### 5.2 Per-site outcome

For a site with expected set `E` and detected name set `D`:

- **true positives** `TP = E ∩ D`
- **false negatives** `FN = E \ D` (each classified REGRESSION or COVERAGE GAP per §4)
- **extra detections** `X  = D \ E` — reported for review, **not** scored as
  false positives by default. The benchmark's `expected` is intentionally
  non-exhaustive (it lists the notable technologies, not every pixel), so a
  detection outside `E` is usually correct, not wrong. Extras are surfaced so a
  human can spot a genuinely spurious match.

A site **passes** when every technology in its `expected` set that has a
fingerprint is detected. Coverage-gap misses do not fail a site.

### 5.3 Aggregate metrics

Reported over the fingerprint-backed subset of expectations (the honest
denominator for the current engine):

- **Recall** = ΣTP / (ΣTP + Σ regression-FN) — should be **1.00** for a clean engine.
- **Coverage** = distinct fingerprinted technologies / 30 required — currently
  **28/30** (Hugo and Jekyll pending); tracks roadmap progress across phases.
- **Extra-detection rate** — watched for spurious-match drift.

### 5.4 Environmental caveats (a miss is not always an engine bug)

Live sites are a moving target. The following are expected, documented reasons a
site may under-detect, and are excluded from the REGRESSION bucket when
confirmed:

- **Bot / JS challenge pages** (e.g. Cloudflare "checking your browser",
  Drupal.org behind a challenge) return interstitial HTML with no real markers.
- **Consent / cookie gating** defers analytics and widget SDKs (GA, GTM,
  Segment, Intercom) until after opt-in, so they are absent from the initial
  server HTML.
- **Marketing homepages** frequently do **not** load the product's own SDK —
  e.g. `stripe.com` does not ship `stripe.js`; `vuejs.org` (VitePress SSR) may
  expose no live Vue runtime marker.
- **Stack migrations** — sites move platforms (e.g. brands leaving Shopify for
  headless). When a site's real stack changes, update the dataset's `expected`
  to the new truth; do not "fix" it by loosening the engine.

Because these are static-HTML limitations, they are logged as caveats, not
regressions. Confirming a caveat requires evidence (challenge page, missing
SDK in fetched HTML), not assumption.

---

## 6. How to run a verification pass

The runner is **`benchmark.py`** at the repo root. It reads the engine but does
not modify it.

```bash
python benchmark.py               # full dataset (~46 sites, live network, a few minutes)
python benchmark.py --limit 10    # first N sites only
python benchmark.py --offline     # no network: dataset-vs-engine coverage report
python benchmark.py -o reports/benchmark.json
```

Internally it:

1. Loads `tests/benchmark_sites.json`.
2. Derives the set of currently-fingerprinted technology names from the imported
   `TECH_FINGERPRINTS` (the REGRESSION vs COVERAGE-GAP divider — computed at
   runtime, so it self-corrects as fingerprints change).
3. For each site: crawl (`WebCrawler`), detect (`TechnologyDetector`), compute
   TP / FN / extras per §5.2.
4. Classifies every FN as REGRESSION or COVERAGE GAP.
5. Emits a JSON report plus a human summary: recall, coverage, the regression
   list (must be empty to pass), the coverage-gap list, and the extra-detection
   list. Process exit code is non-zero if any regression is found.

`--offline` is the fast, deterministic check: it needs no network and confirms
which required technologies the engine can currently fingerprint. `validate_live.py`
remains as an older, looser exploratory harness.

> Note: a full (online) pass makes live network requests to ~46 external sites
> and takes a few minutes. It is a QA/CI-nightly activity, not a unit test, and
> its results depend on the live web at run time.

---

## 7. Phase 1 exit criteria

Phase 1 is considered **verified** when:

- [x] `tests/benchmark_sites.json` exists, is valid JSON, and covers all 30
      required technology families with ~40–50 sites.
- [x] Every `expected` name is canonical and, where a fingerprint exists,
      matches the imported `TECH_FINGERPRINTS` exactly (verified by reconciliation;
      28/30 families are fingerprinted, Hugo and Jekyll are the two known gaps).
- [x] This methodology distinguishes REGRESSION from COVERAGE GAP so results are
      interpretable against the real (504-fingerprint) engine.
- [x] A runnable harness (`benchmark.py`) exists and its `--offline` mode confirms
      the coverage split without network access.
- [ ] A full (online) verification run shows **zero REGRESSIONS** across the
      fingerprint-backed expectations (recall = 1.00 on the supported subset),
      with all remaining misses classified as coverage gaps or documented caveats.

The final box is checked by executing an online run; it is intentionally left to
the verification harness so this document never asserts a live result it did not
observe.

---

## 8. Traceability — required technology → benchmark exemplar(s)

Column reflects the canonical name the dataset uses (which matches the engine).

| # | Technology (dataset name) | Fingerprint today? | Representative site(s) |
| --- | --- | --- | --- |
| 1 | WordPress | ✅ | techcrunch.com, wordpress.org, variety.com, rollingstone.com |
| 2 | Shopify | ✅ | allbirds.com, colourpop.com, ruggable.com, fashionnova.com |
| 3 | Wix | ✅ | wix.com |
| 4 | Squarespace | ✅ | squarespace.com |
| 5 | Ghost | ✅ | ghost.org |
| 6 | Drupal | ✅ | drupal.org, nasa.gov |
| 7 | Joomla | ✅ | joomla.org |
| 8 | Next.js | ✅ | nextjs.org, vercel.com, hulu.com, openai.com, supabase.com, notion.so, time.com |
| 9 | React | ✅ | react.dev, airbnb.com, gatsbyjs.com, discord.com, notion.so |
| 10 | Vue.js | ✅ | vuejs.org, about.gitlab.com, nuxt.com, storyblok.com |
| 11 | Angular | ✅ | angular.dev |
| 12 | Svelte | ✅ | svelte.dev |
| 13 | Nuxt.js | ✅ | nuxt.com, storyblok.com |
| 14 | Gatsby | ✅ | gatsbyjs.com |
| 15 | Hugo | ⬜ **gap** | gohugo.io |
| 16 | Jekyll | ⬜ **gap** | jekyllrb.com |
| 17 | Bootstrap | ✅ | getbootstrap.com |
| 18 | Tailwind CSS | ✅ | tailwindcss.com |
| 19 | Cloudflare | ✅ | cloudflare.com, discord.com |
| 20 | Vercel | ✅ | nextjs.org, vercel.com |
| 21 | Netlify | ✅ | netlify.com, smashingmagazine.com |
| 22 | Google Analytics 4 | ✅ | w3schools.com |
| 23 | Google Tag Manager | ✅ | hubspot.com, mailchimp.com |
| 24 | Stripe | ✅ | stripe.com |
| 25 | HubSpot | ✅ | hubspot.com |
| 26 | Segment | ✅ | segment.com |
| 27 | Contentful | ✅ | contentful.com |
| 28 | Sanity | ✅ | sanity.io |
| 29 | Storyblok | ✅ | storyblok.com |
| 30 | Webflow | ✅ | webflow.com |

`✅` = a fingerprint exists today (28/30), so these expectations are actively
regression-tested. `⬜ gap` = expected ground truth with no fingerprint yet
(Hugo, Jekyll); these drive the fingerprint roadmap and are reported as coverage
gaps, not failures.

---

## 9. Files delivered by Phase 1

```
docs/verification/phase1_verification.md   <- this document
tests/benchmark_sites.json                 <- the benchmark dataset (ground truth)
benchmark.py                               <- the runner (reads the engine, scores it)
```

No engine, fingerprint, or detection-logic files were created or modified.
`benchmark.py` only imports and reads `TechnologyDetector`, `WebCrawler`, and
`TECH_FINGERPRINTS`.
