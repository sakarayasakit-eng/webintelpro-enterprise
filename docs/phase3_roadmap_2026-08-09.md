# WebIntelPro Phase 3 — Architectural Audit & Ranked Roadmap

Read-only audit. No files modified, no code written, nothing committed — per
instruction. Every claim below is grounded in the current source (file
references given); nothing is assumed from the README or prior session notes
without re-verification.

---

## 0. Two findings that affect Phase 3 planning directly

Before any new feature list: two architectural facts materially change what
"build on existing infrastructure" means for several of the areas you asked
about (D, E in particular). Both are read-only findings — nothing was changed.

### 0.1 Phase 2A–2E, Core Web Vitals, and site checks only run in single-page mode

`main.py::_run_single` (the only-URL, no-flags path) is the *sole* call site
that constructs `AnalysisEngine` with `site_checks=True` and forwards
`analyze_js/analyze_runtime/analyze_api/analyze_ai_stack/analyze_auth`, and
the only path that calls `modules.vitals.measure()`.

Three other entry points construct `AnalysisEngine` or `SiteCrawler` with
**only** `timeout`/`use_cache` — no Phase 2 flags, no `site_checks`, no vitals:

- `sitecrawl.py:30` — `SiteCrawler.__init__` doesn't even accept the five
  Phase 2 flags as parameters, so `--crawl` runs can't opt in no matter what
  CLI flags are passed.
- `compare.py:19` — same: `CompetitorComparison.__init__` only takes
  `timeout`/`use_cache`.
- `batch.py:21` — same: `BatchScanner.__init__` only takes `timeout`/`use_cache`.

Practical effect: a command like
`python main.py https://site.com --crawl 300 --js-bundles --runtime-analysis --api-discovery --ai-detection --auth-detection --vitals`
silently ignores all six flags. The base technology detector (505
fingerprints) still runs on every page — that part is real — but none of the
Phase 2A–2E enrichments, robots/sitemap/TLS checks, or Core Web Vitals ever
execute during a site-wide crawl, competitor comparison, or batch scan today.
This is very likely why a real production `--crawl 300 --ai-detection
--auth-detection ...` scan came back with a shallow technology list — the
deeper stages that could have found more were never invoked.

**Consequence for this roadmap**: Area E (Competitive Intelligence — AI
stack/API/auth comparison) and any per-page Phase 2 signal used in Area D
(Website Change Intelligence) are blocked on this being fixed first. It's
listed below as its own item (P0) rather than folded into a feature, because
it's a bug-fix/plumbing task, not a new capability.

### 0.2 Single-page JSON export drops Core Web Vitals and site checks

`reporter.py::to_json()` (`reporter.py:252-269`) builds an explicit `payload`
dict that includes `technology.to_dict()` (which *does* carry
runtime/api_discovery/ai_stack/authentication — that part is complete) but
never includes `result.get("vitals")` or `result.get("site")`
(robots/sitemap/TLS). Those two are console-only. Anyone consuming the JSON
report (which is what any future diff/comparison/executive-summary feature
would read) silently loses vitals and site-check data even on a correctly-run
single-page scan with `-f all`.

**Consequence**: Area D's scan-diff feature (recommended as Phase 3.1 below)
should read from the console-complete data path or this gap should be closed
first for full coverage; the diff feature itself doesn't strictly need it
(see feasibility note in that section) but any future "diff vitals over
time" idea does.

---

## 1. What already exists (grounding for "current capability" below)

Verified directly, not assumed:

- **Detection**: 505 fingerprints across 27 categories via a Noisy-OR
  confidence engine (`technology/confidence.py`), shared by Phase 1 (static
  HTML/header/cookie matching) and all five Phase 2 stages. Confirmed
  existing coverage relevant to your investigation areas:
  - **CDN** (`fingerprints/cdn.py`): Cloudflare, CloudFront, Fastly, Akamai.
  - **Hosting/deployment platform** (`fingerprints/hosting.py`): Vercel,
    Netlify, Cloudflare Pages, GitHub Pages, AWS, Azure, GCP, DigitalOcean,
    Heroku, Render.
  - **WAF / bot management** (`fingerprints/security.py`): reCAPTCHA,
    hCaptcha, Cloudflare Turnstile, Cloudflare Bot Management, Sucuri,
    Imperva Incapsula, Akamai Bot Manager, DataDome, PerimeterX, Wordfence.
  - **Chat/support** (`fingerprints/chat.py`): Intercom, Drift, Zendesk
    Chat, LiveChat, Tawk.to, Crisp, Tidio, Freshchat, Olark, Gorgias,
    HubSpot Chat.
  - **Marketing/advertising** (`fingerprints/marketing.py`): HubSpot,
    Marketo, Mailchimp, Klaviyo, Segment, Pardot, ActiveCampaign, Facebook
    Pixel, Google Ads, LinkedIn Insight, Twitter Pixel, Optimizely.
  - **Payments** (`fingerprints/payments.py`): Stripe, PayPal, Braintree,
    Square, Adyen, Klarna, Afterpay, Amazon Pay, Razorpay, Authorize.Net,
    Checkout.com, Mollie.
  - **Fonts** (`fingerprints/fonts.py`): Google Fonts, Adobe Fonts, Font
    Awesome, Fonts.com, Bunny Fonts, Material Icons, Ionicons.
  - **E-commerce** (`fingerprints/ecommerce.py`): WooCommerce, Magento,
    BigCommerce, PrestaShop, Squarespace Commerce, Wix Stores, Ecwid,
    Salesforce Commerce Cloud, OpenCart, Shopware, Snipcart.
  - **Consent/privacy platforms** (`fingerprints/misc.py`,
    `fingerprints/fp_widgets.py`): Cookiebot, OneTrust, Osano, TrustArc,
    Didomi, Quantcast Choice.
  - **Analytics** (`fingerprints/analytics.py` + `analytics_extra.py`):
    GA4, GTM, Hotjar, Mixpanel, Quantcast, more.
  - **Not present anywhere**: DNS resolution of any kind (no
    `socket.gethostbyname`, no DNS library import in the whole tree),
    reverse-proxy/load-balancer fingerprinting, resource-weight (byte-size)
    measurement, vulnerability/CVE data, EOL/lifecycle dates.
- **Analyzers**: technical SEO, security (headers/cookies/mixed-content),
  performance (counts + TTFB + compression, no byte-weight), accessibility
  (alt text/labels/landmarks/ARIA) — each 0-100 scored with issue lists.
- **Site-wide crawl** (`sitecrawl.py`, extended this session): per-page raw
  signals (title, canonical, word count, forms, JSON-LD count), duplicate/
  near-duplicate content clustering, canonical/query-variant indexability
  analysis, AdSense observable-risk report, crawl-reliability tracking — all
  new this session, all tested (290/290 passing), all subject to gap 0.1
  above for anything that would need Phase 2 signals per page.
- **Competitor comparison** (`compare.py`): overall/SEO/security/
  performance/accessibility ranking + technology gap (missing/unique sets)
  already exists for exactly two dimensions of what Area E asks for — score
  comparison and tech-gap. AI stack/API/auth comparison do not exist yet
  (partly because of gap 0.1).
- **Trend tracking** (`trends.py`): per-URL score history, last 100 entries,
  aggregate scores only (`tech_count` is an int, not a technology list) — so
  it cannot answer "what technology was added" today, only "did the score
  change."
- **Reporting**: console / JSON / HTML / Excel / PDF, all built from the
  same `result`/`site` dict, no templating engine (raw string building).
- **No LLM integration anywhere in the codebase** — relevant to Area F,
  since an "executive summary" would have to be a rule-based synthesizer
  over already-computed data, not a generated narrative, unless you want to
  add an LLM dependency (out of scope unless you say otherwise).

---

## 2. Proposed Phase 3 features by investigation area

Each feature includes the requested 12 fields. Priority uses P0 (must
build) / P1 (high value) / P2 (useful later) / P3 (avoid/defer), reasoned
against your 10 criteria holistically rather than scored individually per
criterion (with 20+ features, a literal 10-column score table would be noise
— the reasoning is in "Priority").

### A. Infrastructure Intelligence

**A1 — Infrastructure Intelligence Report (CDN/hosting/WAF synthesis)**
- Purpose: turn already-detected CDN/hosting/WAF/bot-management fingerprints into one coherent "how is this site deployed and protected" narrative, instead of leaving them as flat names in a technology list.
- User value: an enterprise buyer or auditor wants "this site sits behind Cloudflare (CDN+WAF), is hosted on Netlify, no separate bot-management layer detected" in one place, not scattered across a 505-item category dump.
- Current capability: CDN, hosting, and WAF/bot-mgmt fingerprints already exist and already populate `TechnologyReport.by_category()`.
- Missing capability: no module reads those categories and produces a structured "infrastructure" finding set (e.g., "edge protection: present/absent", "hosting platform confidence", "WAF detected: Y/N").
- Implementation complexity: Low — pure synthesis over `report.by_category()`, same pattern as `modules/adsense_readiness.py` built this session.
- Network cost: None — reads data already collected.
- Accuracy risk: Low-medium — inherits whatever false-positive rate the underlying fingerprints have (unverified in this audit; worth a benchmark pass, not a blocker).
- Testing complexity: Low — offline, deterministic, same style as this session's new module tests.
- Reporting complexity: Low — one new console/HTML/JSON section.
- Dependencies: None beyond existing `TechnologyReport`.
- Priority: **P1**

**A2 — DNS / edge architecture intelligence (new capability)**
- Purpose: resolve DNS records (A/AAAA/CNAME/NS/MX) to surface hosting IP ranges, CNAME chains to CDNs, and nameserver providers — genuinely new signal, not just re-packaging.
- User value: distinguishes "behind Cloudflare at the DNS layer" from "just detected a Cloudflare script tag," and can catch CDN/WAF usage the HTML-level fingerprints miss entirely.
- Current capability: none — zero DNS code anywhere in the repo today.
- Missing capability: a DNS resolution module (needs `dnspython` or stdlib `socket` for basic A/CNAME, a real resolver library for NS/MX/TXT), IP-range-to-provider mapping (needs a maintained ASN/IP-range dataset — either bundled and stale, or a live lookup).
- Implementation complexity: Medium-high — new dependency, new network call type (UDP/DNS, not HTTP), IP-to-provider mapping is itself a maintenance burden.
- Network cost: Low per-lookup, but a new *kind* of network call (may be blocked in restrictive sandboxes/CI, as this session's own environment demonstrated with HTTP).
- Accuracy risk: Medium — CNAME chains and IP ranges shift; stale provider tables produce confident-looking wrong answers exactly like the HTTP-version bug fixed this session. Would need the same `confidence: heuristic`/scope-limitation discipline established this session.
- Testing complexity: Medium — needs mocked resolvers for offline tests; live validation needs real DNS.
- Reporting complexity: Low-medium.
- Dependencies: `dnspython` (new dependency), an IP-range/provider dataset.
- Priority: **P2** — real value, but new dependency + new failure mode + maintenance burden for a dataset that goes stale. Land A1 first (it's free) before investing here.

### B. Third-Party Intelligence

**B1 — Third-Party Surface Report (dependency/tracker synthesis)**
- Purpose: aggregate analytics/marketing/chat/payment/font/consent fingerprints already detected into a single "who else is running code on this page" report, with counts and categories (matches your "dependency relationships" ask at a detection-reuse level, not a full software-supply-chain graph).
- User value: privacy/compliance reviewers and security teams want one list of every third party with page access, not a flat alphabetical technology dump.
- Current capability: all of analytics, marketing, chat, payments, fonts, consent-management are already fingerprinted (confirmed in section 1); `resource_hosts()` in `technology/parser.py` already classifies first-vs-third-party by host for scripts/styles/images (used today only for a performance *count*, `modules/performance.py:31`).
- Missing capability: no module groups the *technology* detections by "third-party service" vs. groups the *resource hosts* into a per-domain breakdown; these are two different views of "third party" that currently live in two disconnected places (technology names vs. raw hostnames) and nothing reconciles them.
- Implementation complexity: Low-medium — mostly synthesis, but reconciling technology-name detections with raw third-party hostnames (so "Stripe" the technology and `js.stripe.com` the resource host are recognized as the same thing) needs a small mapping.
- Network cost: None.
- Accuracy risk: Low — same inherited fingerprint accuracy as A1.
- Testing complexity: Low.
- Reporting complexity: Low-medium (one new section, works for both single-page and site-wide).
- Dependencies: None new.
- Priority: **P1**

**B2 — Dependency relationship graph (which third party loads which other third party)**
- Purpose: capture chains like "GTM loads Facebook Pixel" rather than a flat list.
- Current capability: none — the parser records script *sources* on the fetched HTML only; it does not follow or attribute scripts injected by other scripts (that's runtime behavior, not static HTML).
- Missing capability: this fundamentally needs either headless-browser network-request capture (Playwright's request log, similar machinery to `modules/vitals.py`) or heavy heuristics on tag-manager container contents.
- Implementation complexity: High.
- Network cost: High if done via headless browser (full page render).
- Accuracy risk: Medium-high — attribution ("X loaded Y") from static analysis alone is unreliable; doing it right needs the browser.
- Testing complexity: High.
- Reporting complexity: Medium.
- Dependencies: Playwright (already an optional dependency for vitals — could share that path).
- Priority: **P3** — genuinely useful but expensive and the existing vitals module is the only precedent for browser automation; don't build a second one until the first is proven reliable in the field.

### C. Supply-Chain Intelligence

**C1 — Technology lifecycle / EOL flagging**
- Purpose: flag detected technologies with *known, versioned* end-of-life dates (e.g., "jQuery 1.x — EOL", "PHP 7.4 — EOL") using a small curated static table, not a live vulnerability feed.
- User value: concrete, defensible risk signal ("this version stopped receiving security updates on date X") without making CVE claims WebIntelPro can't verify.
- Current capability: `VersionEngine` already extracts version numbers for many fingerprints (confirmed in `technology/version.py` usage across the detector); this is the missing half.
- Missing capability: a maintained lifecycle table (name + version-range → EOL date), and a rule that only fires when a version was actually extracted (not on category alone).
- Implementation complexity: Low-medium — mostly data curation, matching logic is simple.
- Network cost: None (static bundled table) — this is the deliberate choice; a live-lookup version (see C2) is a different, riskier feature.
- Accuracy risk: Low, *if* scoped strictly to "flag only when a specific version was extracted with confirmed evidence" and labeled `confidence: confirmed` only in that case. Stated as a hard requirement, not a nice-to-have — this is exactly the kind of claim that produced the HTTP/1.1 false positive this session.
- Testing complexity: Low — deterministic table lookups.
- Reporting complexity: Low.
- Dependencies: None new; requires ongoing manual curation (a real, recurring cost, not a one-time build).
- Priority: **P1**

**C2 — "Known vulnerable technology" / CVE flagging**
- Purpose: what you'd naturally want next after C1 — flag specific CVEs.
- Current capability: none.
- Missing capability: a live or periodically-synced CVE feed (NVD, OSV, or similar), version-range matching against CVE-affected-version data, and a policy for what "reliable detection" means here.
- Implementation complexity: High.
- Network cost: Medium (periodic feed sync) to none (if bundled and manually updated, but then it's stale by definition).
- Accuracy risk: **High** — this is explicitly the failure mode your mission brief (previous session) warned about: confident wrong security claims. Version extraction here is already probabilistic (confidence-scored, not certain); layering "this version has CVE-2024-XXXX" on top of a probabilistic version match compounds uncertainty into what reads as a hard security finding. Getting this wrong is reputationally worse than a missing feature.
- Testing complexity: High (needs a frozen CVE dataset snapshot for deterministic tests).
- Reporting complexity: Medium — needs very explicit confidence/scope framing to avoid overclaiming (mirroring the `confidence: heuristic` discipline from `modules/adsense_readiness.py`).
- Dependencies: External CVE data source, ongoing sync/maintenance.
- Priority: **P3 — avoid for now.** Your own mission brief last session explicitly said "known vulnerable technologies where **detection is reliable**." Given version extraction is already confidence-scored (not certain) and no CVE data source is integrated, this doesn't clear that bar today. Revisit only after C1 is live and version-extraction accuracy has been benchmarked.

### D. Website Change Intelligence

**D1 — Scan-to-scan diff (compare two saved reports)** — *recommended as Phase 3.1, see section 4*
- Purpose: given two previously-saved JSON reports (single-page or site-wide) for the same target, produce a structured diff: technologies added/removed, security headers changed, SEO/score deltas, recommendation deltas, and — where present — AI stack/API/auth changes.
- User value: exactly the workflow you're already doing by hand right now (comparing `fincalcyou_full.json` against `fincalcyou_v2.json`). This turns that manual diffing into a command.
- Current capability: both single-page and site-wide JSON reports already contain full structured technology lists (`to_dict()`), scores, and recommendations — everything a diff needs is already on disk once two scans exist. `trends.py` proves the "record and compare over time" pattern already works for aggregate scores.
- Missing capability: nothing reads two full report JSON files and diffs their structured content (`trends.py` only diffs five aggregate score numbers, not technology lists or recommendation sets).
- Implementation complexity: **Low** — pure data-structure diffing (set differences on technology names, dict comparisons on header/score fields), no new detection, no new network calls.
- Network cost: **None** — operates entirely on two already-saved JSON files.
- Accuracy risk: **Low** — this is structural diffing of data WebIntelPro already computed and already trusts (or has already flagged low-confidence); it's not introducing new inference.
- Testing complexity: **Low** — pure functions over two dict fixtures, easy to write exhaustive offline tests (added tech, removed tech, header flip, score delta, missing-field-on-one-side edge cases).
- Reporting complexity: Low-medium — one new report type (console + JSON + HTML), reuses existing rendering patterns from `reporter.py`.
- Dependencies: None new.
- Priority: **P0**

**D2 — Automatic re-scan-and-diff (schedule + compare against last recorded scan)**
- Purpose: extend D1 so you don't have to manually manage two file paths — `--diff-since-last` compares a fresh scan against the most recent entry `trends.py` already has.
- Current capability: `trends.py` already stores per-URL history; D1 (once built) provides the diff engine.
- Missing capability: `trends.json` currently stores only aggregate scores (`tech_count` as an int), not full technology/recommendation lists — so "diff since last" needs `trends.json`'s schema extended to optionally retain a pointer to (or a compact copy of) the full report, not just five numbers.
- Implementation complexity: Medium — schema change to `trends.json` needs to stay backward-compatible with existing history entries (graceful handling of old entries that lack the new field).
- Network cost: Whatever a normal scan costs (unchanged).
- Accuracy risk: Low.
- Testing complexity: Medium (schema migration path needs its own tests).
- Reporting complexity: Low (reuses D1's output format).
- Dependencies: D1 must exist first.
- Priority: **P1** — natural, low-risk follow-on to D1, sequenced after it.

### E. Competitive Intelligence

**E1 — Fix Phase 2 wiring in `CompetitorComparison` + add AI/API/auth dimensions**
- Purpose: close gap 0.1 for the comparison path specifically, then extend `compare.py`'s existing ranking/gap logic to AI stack, API surface, and auth architecture — completing what Area E asks for.
- User value: "does my competitor use a more modern AI stack / broader API surface / stronger auth architecture than I do" — currently impossible even with all CLI flags set, because of gap 0.1.
- Current capability: score ranking + technology gap for overall/SEO/security/performance/accessibility already fully built and working (`compare.py`).
- Missing capability: `CompetitorComparison.__init__` doesn't accept or forward the five Phase 2 flags (same bug as `SiteCrawler`); AI stack/API/auth have no gap-analysis logic analogous to `_tech_gap()` yet (those are structured findings, not flat name sets, so the existing set-difference approach needs adapting, not just re-running).
- Implementation complexity: Medium — the wiring fix itself is small (mirrors the constructor-parameter fix needed in section 0.1); the new dimensions need finding-level (not just name-level) comparison logic.
- Network cost: Whatever the opted-in Phase 2 flags already cost (unchanged, just actually applied now).
- Accuracy risk: Low — reuses already-shipped, already-tested Phase 2 detectors; the new risk surface is the comparison/gap logic itself, which is straightforward set/dict comparison.
- Testing complexity: Medium — needs comparison fixtures with AI/API/auth findings on both sides.
- Reporting complexity: Medium — three new comparison sections (console + HTML).
- Dependencies: None new (fixes/extends existing code).
- Priority: **P0** for the wiring fix specifically (it's a bug, and it silently breaks a documented CLI flag combination); **P1** for the new AI/API/auth comparison dimensions once wiring is fixed.

**E2 — Opportunity-gap scoring (single "where you're behind" number per dimension)**
- Purpose: turn the existing ranked comparison into an explicit gap-size metric per dimension (not just "who's ranked first"), e.g. "you're 23 points behind the leader on accessibility."
- Current capability: `compare.py::_rank()` already produces per-dimension rankings with raw scores — the gap number is a one-line subtraction away.
- Missing capability: the subtraction/labeling itself, and a "biggest gap" rollup across dimensions.
- Implementation complexity: Low.
- Network cost: None.
- Accuracy risk: Low.
- Testing complexity: Low.
- Reporting complexity: Low.
- Dependencies: None.
- Priority: **P2** — real but small value-add; sequence after E1 since it's cheap to bolt on once E1's data model is settled.

### F. Executive Intelligence

**F1 — Executive Summary section (rule-based synthesis over existing outputs)**
- Purpose: one top-of-report block — key findings, top risks, top opportunities, and (once D1 exists) what changed since last scan — assembled from data already computed elsewhere in the pipeline.
- User value: this is the single most-requested deliverable shape for any tool positioned as "enterprise," and directly serves the format your mission brief specified last session (20-section executive report, confidence-labeled).
- Current capability: every individual signal it would summarize already exists — scores, recommendations (severity-ranked), duplicate-content risk, indexability findings, AdSense observable risk, tech gap (if E1 lands). Nothing currently rolls them into one summary.
- Missing capability: the synthesis/selection logic (what counts as a "key finding" vs. noise) and a confidence-aware writing template — no LLM in this codebase today, so this has to be a rules engine (e.g., top 3 critical/high recs + biggest score outlier + any HIGH-risk duplicate cluster + any HIGH-severity AdSense factor), not generated prose.
- Implementation complexity: Medium — not technically hard, but the *selection rules* (what makes the cut) need real design thought to avoid either an empty summary or a wall of text; this is a judgment-heavy feature even though it's not code-heavy.
- Network cost: None.
- Accuracy risk: Medium — a synthesis layer that misrepresents severity (e.g., surfaces a `possible`-confidence finding as if it were `confirmed`) would undermine the confidence-labeling discipline built this session; needs an explicit rule that the summary inherits and displays the same confidence labels, never upgrades them.
- Testing complexity: Medium — "does this correctly pick the top N findings" is testable; "is the prose good" is not a unit-testable property, so expectations should be scoped to structured output (a list of {finding, confidence, why-it-matters}), not generated sentences.
- Reporting complexity: Medium — needs its own console/HTML section design.
- Dependencies: Benefits from D1 (change-since-last) and E1 (competitive gaps) existing first, but can ship a first version without them.
- Priority: **P1**

### G. Advanced Performance Intelligence

**G1 — Resource weight breakdown (bytes by type, first vs. third party)**
- Purpose: "your third-party scripts are 1.2MB of the 1.8MB this page loads" — the thing `modules/performance.py` counts today (script/style/image *counts*, third-party *count*) but doesn't weigh.
- Current capability: `resource_hosts()` already classifies first-vs-third-party by host (count only); `performance.py` has `html_size` for the document itself but nothing for sub-resources.
- Missing capability: fetching (or HEAD-requesting) every discovered script/stylesheet/image to get `Content-Length`, then aggregating by type and first/third-party.
- Implementation complexity: Medium.
- Network cost: **High relative to everything else in this list** — this is the one feature here that meaningfully multiplies request volume (potentially dozens of extra HTTP requests per page scanned); needs explicit bounds (max resources probed, timeout budget) the way `technology/javascript`'s `BundleConfig` already bounds bundle downloads.
- Accuracy risk: Medium — `Content-Length` isn't always present or accurate (chunked encoding, compression); would need to state that limitation rather than imply byte-exact totals.
- Testing complexity: Medium (needs mocked HEAD responses).
- Reporting complexity: Low-medium.
- Dependencies: None new, but reuses the bounded-download discipline established in `technology/javascript/models.py::BundleConfig` as precedent.
- Priority: **P2** — real value, but the network-cost jump is a genuine trade-off worth deciding deliberately (opt-in flag, same pattern as `--js-bundles`), not a default-on feature.

**G2 — TTFB attribution / request concentration**
- Purpose: distinguish "slow because of your server" from "slow because of a third-party render-blocking script," and flag pages where too many resources come from too few hosts (concentration risk) or vice versa (fragmentation).
- Current capability: single-page TTFB exists (`crawler.py`'s `ttfb` field); no attribution, no concentration metric.
- Missing capability: attribution needs render-blocking-vs-async classification of scripts (partially inferable statically from `<script>` attributes already parsed — `async`/`defer` aren't currently captured in `ParsedHTML`, that's a small parser addition) and a per-host resource-count histogram (cheap, reuses existing parsed data).
- Implementation complexity: Low-medium for concentration (reuses existing data); medium for TTFB attribution (needs the new async/defer parser field plus interpretation logic, and "TTFB attribution" without a browser is inherently a heuristic, not a measurement).
- Network cost: None (static analysis of already-fetched HTML).
- Accuracy risk: Medium — true TTFB attribution really needs a browser/waterfall (like Core Web Vitals does); a static-only version should be framed as "render-blocking resource count" (a real, defensible signal) rather than claiming actual TTFB causality it can't measure.
- Testing complexity: Low-medium.
- Reporting complexity: Low.
- Dependencies: Small parser extension (`async`/`defer` capture).
- Priority: **P2**

### H. Privacy Intelligence

**H1 — Privacy/Tracking Risk Report (synthesis)**
- Purpose: combine already-detected trackers (analytics/marketing categories), already-computed cookie-flag issues (`security.py`'s `insecure_cookies`), and already-detected consent-management platform presence/absence into one privacy-focused view.
- User value: "this page loads 6 tracking scripts, has 3 cookies without SameSite, and has no consent-management platform detected" as one coherent finding set instead of three unrelated sections a reader has to mentally combine.
- Current capability: all three inputs already exist and are already computed (confirmed in section 1); this is the same "pure synthesis" pattern as A1, B1, and this session's `adsense_readiness.py`.
- Missing capability: the module that reads all three and produces the combined view; also a per-tracker-category count breakdown (analytics vs. marketing vs. chat) that doesn't exist as a grouped view today.
- Implementation complexity: Low.
- Network cost: None.
- Accuracy risk: Low — same inherited fingerprint/cookie-flag accuracy as the modules it reads from; genuinely low-risk to add "no compliance claim" framing (mirroring the AdSense module's explicit disclaimer discipline) since "privacy risk" language can imply legal conclusions this tool shouldn't make.
- Testing complexity: Low.
- Reporting complexity: Low.
- Dependencies: None new.
- Priority: **P1** — and should explicitly *not* claim GDPR/CCPA/compliance status, only observable signals (tracker count, cookie flags, consent-platform presence), mirroring the AdSense disclaimer pattern from this session (`modules/adsense_readiness.py`'s "not a prediction" framing).

---

## 3. Ranked summary

**P0 — must build**
- Fix Phase 2A-2E / site-checks / vitals wiring in `SiteCrawler` and `CompetitorComparison` (section 0.1) — not a new feature, a correctness fix; several P1 items depend on it.
- D1 — Scan-to-scan diff (Website Change Intelligence core)

**P1 — high value**
- A1 — Infrastructure Intelligence Report (synthesis)
- B1 — Third-Party Surface Report (synthesis)
- C1 — Technology lifecycle / EOL flagging (static table, confidence-gated)
- D2 — Automatic diff-since-last-scan
- E1 (dimension extension half) — AI/API/auth competitive comparison
- F1 — Executive Summary section
- H1 — Privacy/Tracking Risk Report (synthesis, no compliance claims)

**P2 — useful later**
- A2 — DNS/edge architecture intelligence (new dependency, new failure mode)
- E2 — Opportunity-gap scoring
- G1 — Resource weight breakdown (real network-cost trade-off)
- G2 — TTFB attribution / request concentration

**P3 — avoid/defer**
- B2 — Dependency relationship graph (needs headless-browser network capture; expensive, unproven precedent)
- C2 — CVE/vulnerability flagging (accuracy risk too high without a real CVE data source and better version-extraction confidence than currently exists)

---

## 4. PHASE 3.1 RECOMMENDATION

**D1 — Scan-to-scan diff (compare two saved JSON reports).**

### RATIONALE

Every other P1/P0 candidate either depends on new detection accuracy that
hasn't been benchmarked (A2, C1's table needs curation), a bug fix that
touches shared plumbing (the wiring fix — necessary, but "fix a bug" isn't
really a Phase 3 *feature*), or a synthesis layer whose output quality is
hard to verify without first having something concrete to synthesize (F1
genuinely gets better once D1 exists, since "what changed" is a natural
input to an executive summary).

D1 is the one item that is simultaneously: zero network cost, zero new
detection risk (it diffs data WebIntelPro already computed and already
labeled with confidence), trivially testable (pure functions over two JSON
fixtures), fully reuses the existing report schema with no format changes
needed, and — concretely — is the exact task you are already doing by hand
right now with `fincalcyou_full.json` and `fincalcyou_v2.json` sitting in
`reports/`. Shipping it turns a manual comparison you'd otherwise repeat by
eye every time you re-scan into a repeatable, testable command, and gives
every later Phase 3 feature (F1's "what changed" input, E's future
"competitor moved" tracking, D2's automatic diffing) a foundation to build
on rather than each reinventing diff logic independently.

### EXPECTED OUTPUT

A new `diff.py` module (or a method on `ReportGenerator`) that:
- Accepts two saved report JSON files (or two `result`/`site` dicts directly).
- Diffs: technologies added/removed (set difference on names, with category
  and confidence shown for each side), score deltas per dimension
  (overall/SEO/security/performance/accessibility), security-header changes
  (each header's present/absent flip), recommendation deltas (new
  critical/high findings, resolved findings), and — where both sides have
  it — AI stack/API/auth/runtime deltas via the same set/dict-diff approach.
- A new CLI mode: `python main.py --diff report_a.json report_b.json -f
  console|json|html`, following the existing `_run_compare`/`_run_site`
  pattern in `main.py`.
- Output rendered via the existing `reporter.py` conventions (a
  `diff_console_str()`/`save_diff_html()`/`save_diff_json()` trio, mirroring
  `comparison_console()`/`save_comparison_html()`/`save_comparison_json()`
  already in the file).

### FILES LIKELY TO CHANGE

- New: `diff.py` (or `modules/scan_diff.py`) — the diffing logic.
- `main.py` — new `--diff` CLI argument and `_run_diff()` handler.
- `reporter.py` — three new render methods (console/HTML/JSON), following
  the existing comparison-report pattern.
- New: `tests/test_scan_diff.py` — fixtures with two synthetic report dicts
  covering added/removed tech, score deltas, header flips, and
  missing-field-on-one-side edge cases (e.g., diffing a report that has
  `ai_stack` against one that doesn't, since that field is `None` unless
  `--ai-detection` was used).
- Documentation: `README.md` usage section, following the existing pattern
  for `--vs`/`--crawl`.

### TEST STRATEGY

Entirely offline, no network — this is the easiest Phase 3 candidate to test
well:
- Unit tests on the diff function itself with hand-built dict fixtures (not
  live scans): technology added, technology removed, technology confidence
  changed but name unchanged (should this count as a "change"? — decide and
  test the decision), score improved/regressed per dimension, a security
  header that flipped from present to absent, a recommendation that
  disappeared (resolved) vs. one that's new.
- Edge cases: diffing two reports for *different* URLs (should probably warn,
  not silently diff unrelated sites), diffing a report against itself
  (expect an empty diff), diffing when one side is missing an optional field
  entirely (`ai_stack`/`runtime`/`authentication`/`api_discovery` are all
  `Optional` and `None` unless the corresponding Phase 2 flag was used —
  the diff must handle "field absent on both", "field absent on one side
  only", and "field present on both" as three distinct, tested cases).
- Regression: full `pytest -q` run after the change (currently 290 passing)
  to confirm nothing existing breaks.
- Manual/live verification (on your machine, not this sandbox): once built,
  run it against the two real files already sitting in `reports/` —
  `fincalcyou_full.json` vs. a same-format single-page or site-wide rescan —
  as the first real-world validation.

### RISKS

- **Report-shape drift**: if `TechnologyReport.to_dict()` or the site-crawl
  dict shape changes later (it already changed this session — `engine.py`
  now includes `"parsed"` internally, though that's stripped before JSON
  serialization), the diff function needs to degrade gracefully on unknown/
  missing keys rather than throwing, the same defensive pattern used
  throughout `sitecrawl.py` and `modules/indexability.py` this session.
- **Comparing incompatible scan types**: diffing a single-page report
  against a site-wide report (different top-level shape entirely) needs an
  explicit, clear rejection rather than a confusing partial diff.
- **Confidence-label handling**: if a technology's confidence crossed the
  `MIN_CONFIDENCE` (0.30) threshold between scans — present-but-low before,
  absent now, or vice versa — that's a real edge case worth a specific test
  rather than silently treating it as "added"/"removed" without nuance.
- **Scope creep**: it would be easy to let this grow into "diff N scans over
  time" (a trend-line feature) instead of "diff 2 scans" (the P0 core). Keep
  D1 strictly to two-report diffing; D2 (already scoped separately above) is
  where the "since last scan" convenience layer belongs.
