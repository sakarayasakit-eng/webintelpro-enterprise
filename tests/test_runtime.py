"""
Offline tests for Phase 2B JavaScript Runtime Intelligence.

Everything here runs without a network and without a browser. The default
runtime path performs no I/O at all, which one test enforces directly by making
any HTTP call explode; the opt-in bundle path is exercised with a stubbed
fetcher.

Coverage follows the Phase 2B contract: runtime frameworks (React, Vue,
Angular, Next, Nuxt), state management (Redux, Apollo), API discovery (GraphQL,
WebSocket, SSE, REST, OpenAPI), runtime config and env vars, PWA, hydration
strategies and dynamic imports - plus the guarantees that matter more than any
single detection: the default detect() path is unchanged, limits are honoured,
and every failure is graceful.
"""

import pytest

from technology.detector import TechnologyDetector
from technology.runtime import (
    FindingKind,
    HydrationInference,
    HydrationStrategy,
    RuntimeAnalyzer,
    RuntimeConfig,
    RuntimeExtractor,
    RuntimeParser,
    RuntimeSignatureScanner,
    classify_endpoint,
    extract_object_literal,
)
from technology.parser import HTMLParser


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def analyze(html: str, config: RuntimeConfig | None = None, url="https://site.test"):
    """Run the runtime stage over raw HTML and return the RuntimeAnalysis."""
    parsed = HTMLParser().parse(html)
    return RuntimeAnalyzer(config=config).analyze(parsed, url)


def names(analysis, kind: FindingKind):
    """Reported names in one finding bucket."""
    return {f.name for f in analysis.report.by_kind(kind)}


def techs(analysis):
    return {t.name for t in analysis.technologies}


def page(body: str, head: str = "") -> str:
    return f"<html><head>{head}</head><body>{body}</body></html>"


# ---------------------------------------------------------------------------
# runtime frameworks
# ---------------------------------------------------------------------------

def test_detects_react_from_runtime_globals():
    html = page('<div id="root"></div>'
                '<script>window.__REACT_DEVTOOLS_GLOBAL_HOOK__;'
                'ReactDOM.createRoot(document.getElementById("root"));</script>')
    analysis = analyze(html)
    assert "React" in techs(analysis)
    assert "React" in names(analysis, FindingKind.FRAMEWORK)


def test_detects_vue_and_angular():
    vue = analyze(page('<script>window.__VUE_DEVTOOLS_GLOBAL_HOOK__;'
                       'Vue.createApp({}).mount("#app");</script>'))
    assert "Vue.js" in techs(vue)

    angular = analyze(page('<script>window.ngDevMode;'
                           'bootstrapApplication(AppComponent);</script>'))
    assert "Angular" in techs(angular)


def test_angularjs_is_distinct_from_angular():
    analysis = analyze(page('<script>window.angular.module("app",[]);</script>'))
    assert "AngularJS" in techs(analysis)


def test_detects_next_and_implies_react():
    html = page('<div id="__next"></div>'
                '<script>window.__NEXT_DATA__ = {"page":"/"};</script>')
    analysis = analyze(html)
    assert "Next.js" in techs(analysis)
    # React leaves no marker of its own in a Next bundle; it is entailed.
    assert "React" in techs(analysis)
    react = next(t for t in analysis.technologies if t.name == "React")
    assert react.evidence == ["implied:Next.js"]


def test_detects_nuxt_and_implies_vue():
    html = page('<script>window.__NUXT__ = {"serverRendered":true,"data":{}};</script>')
    analysis = analyze(html)
    assert {"Nuxt.js", "Vue.js"}.issubset(techs(analysis))


def test_short_globals_require_an_accessor():
    """`React`/`Vue` must not match bare prose - only window.React does."""
    analysis = analyze(page("<p>We react to Vue trends and angular shapes.</p>"))
    assert {"React", "Vue.js", "AngularJS"}.isdisjoint(techs(analysis))


# ---------------------------------------------------------------------------
# state management
# ---------------------------------------------------------------------------

def test_detects_redux_and_apollo_state():
    html = page('<script>window.__REDUX_STATE__={};window.__APOLLO_STATE__={};</script>')
    analysis = analyze(html)
    assert {"Redux", "Apollo"}.issubset(techs(analysis))
    assert {"Redux", "Apollo"}.issubset(names(analysis, FindingKind.STATE_MANAGEMENT))


def test_detects_pinia_and_implies_vue():
    analysis = analyze(page('<script>window.__PINIA__ = createPinia();</script>'))
    assert {"Pinia", "Vue.js"}.issubset(techs(analysis))


def test_generic_state_global_reports_without_naming_a_vendor():
    """__INITIAL_STATE__ proves rehydration, not any particular library."""
    analysis = analyze(page('<script>window.__INITIAL_STATE__ = {"a":1};</script>'))
    assert "window.__INITIAL_STATE__" in names(analysis, FindingKind.GLOBAL)
    assert techs(analysis) == set()


# ---------------------------------------------------------------------------
# API discovery
# ---------------------------------------------------------------------------

def test_discovers_endpoints_of_every_kind():
    html = page('<script>'
                'fetch("/api/v1/products");'
                'fetch("/graphql",{method:"POST"});'
                'fetch("/openapi.json");'
                'new WebSocket("wss://live.site.test/socket");'
                'new EventSource("/stream/events");'
                'fetch("/data/config.json");'
                '</script>')
    analysis = analyze(html)
    found = {f.name: f.details.get("kind")
             for f in analysis.report.by_kind(FindingKind.API)}
    assert found["/api/v1/products"] == "rest"
    assert found["/graphql"] == "graphql"
    assert found["/openapi.json"] == "openapi"
    assert found["wss://live.site.test/socket"] == "websocket"
    assert found["/stream/events"] == "sse"
    assert found["/data/config.json"] == "json"


def test_constructor_classification_beats_path_shape():
    """new EventSource("/api/x") is SSE even though the path looks REST."""
    analysis = analyze(page('<script>new EventSource("/api/x");</script>'))
    finding = next(f for f in analysis.report.by_kind(FindingKind.API))
    assert finding.details["kind"] == "sse"


def test_single_char_literal_does_not_desync_the_string_scan():
    """Regression: a 1-char literal must not swallow the next string.

    The scanner walks a script sequentially, so if `"/"` is skipped its closing
    quote is read as the *opening* quote of the following literal and every
    endpoint after it on the line disappears.
    """
    html = page('<script>var s={"page":"/"};fetch("/graphql");</script>')
    assert "/graphql" in names(analyze(html), FindingKind.API)


def test_endpoint_classification_rejects_non_endpoints():
    for value in ("application/json", "hello world", "/news", "/wsdl", "/", "text"):
        assert classify_endpoint(value) is None


def test_endpoints_are_discovered_inside_embedded_json():
    html = page('<script id="__NEXT_DATA__" type="application/json">'
                '{"props":{"apiUrl":"https://api.site.test/api/v2/cart"}}'
                '</script>')
    analysis = analyze(html)
    api = analysis.report.by_kind(FindingKind.API)
    assert "https://api.site.test/api/v2/cart" in {f.name for f in api}
    # Provenance points at the payload, not at a script body.
    assert api[0].location.startswith("embedded_json")


def test_markup_is_not_mined_for_endpoints():
    """Link hrefs are navigation, not runtime intent."""
    analysis = analyze(page('<a href="/api/not-a-runtime-call">docs</a>'))
    assert names(analysis, FindingKind.API) == set()


# ---------------------------------------------------------------------------
# runtime config + environment variables
# ---------------------------------------------------------------------------

def test_extracts_runtime_config_object_and_keys():
    html = page('<script>window.__ENV__ = {"API_URL":"https://a.test","DEBUG":false};</script>')
    analysis = analyze(html)
    finding = next(f for f in analysis.report.by_kind(FindingKind.RUNTIME_CONFIG)
                   if f.name == "__ENV__")
    assert finding.details["keys"] == ["API_URL", "DEBUG"]


def test_env_accessors_are_reported():
    html = page('<script>const u = process.env.NEXT_PUBLIC_API_URL;'
                'const m = import.meta.env.VITE_MODE;</script>')
    analysis = analyze(html)
    found = names(analysis, FindingKind.ENV_VAR)
    assert {"NEXT_PUBLIC_API_URL", "VITE_MODE"}.issubset(found)


def test_secret_looking_env_values_are_redacted():
    html = page('<script id="__NEXT_DATA__" type="application/json">'
                '{"runtimeConfig":{"NEXT_PUBLIC_API_URL":"https://a.test",'
                '"NEXT_PUBLIC_STRIPE_SECRET":"sk_live_leak"}}</script>')
    analysis = analyze(html)
    values = {f.name: f.value for f in analysis.report.by_kind(FindingKind.ENV_VAR)}
    assert values["NEXT_PUBLIC_STRIPE_SECRET"] == "<redacted>"
    # Non-secret values stay useful.
    assert values["NEXT_PUBLIC_API_URL"] == "https://a.test"
    # The name is still reported: a public-prefixed secret is worth knowing.
    assert "NEXT_PUBLIC_STRIPE_SECRET" in values


def test_redaction_can_be_disabled_for_trusted_runs():
    html = page('<script id="__NEXT_DATA__" type="application/json">'
                '{"env":{"NEXT_PUBLIC_TOKEN":"abc123"}}</script>')
    analysis = analyze(html, RuntimeConfig(redact_secrets=False))
    values = {f.name: f.value for f in analysis.report.by_kind(FindingKind.ENV_VAR)}
    assert values["NEXT_PUBLIC_TOKEN"] == "abc123"


# ---------------------------------------------------------------------------
# PWA
# ---------------------------------------------------------------------------

def test_detects_service_worker_workbox_and_push():
    html = page('<script>'
                'navigator.serviceWorker.register("/sw.js");'
                'importScripts("workbox-sw.js"); workbox.routing.registerRoute();'
                'registration.pushManager.subscribe();'
                'caches.open("v1");'
                '</script>', head='<link rel="manifest" href="/manifest.json">')
    analysis = analyze(html)
    assert {"Service Worker", "Workbox"}.issubset(techs(analysis))
    pwa = names(analysis, FindingKind.PWA)
    assert {"Push Notifications", "Offline Cache"}.issubset(pwa)


def test_pwa_capabilities_do_not_become_technologies():
    """"Push Notifications" is a browser capability, not a vendor's product."""
    analysis = analyze(page('<script>Notification.requestPermission();</script>'))
    assert "Push Notifications" in names(analysis, FindingKind.PWA)
    assert "Push Notifications" not in techs(analysis)


# ---------------------------------------------------------------------------
# hydration
# ---------------------------------------------------------------------------

def test_next_data_flags_drive_ssg_and_isr():
    html = page('<script id="__NEXT_DATA__" type="application/json">'
                '{"gsp":true,"isFallback":true,"props":{"__N_SSG":true}}</script>')
    analysis = analyze(html)
    assert HydrationStrategy.SSG.value in analysis.report.hydration_strategies
    assert HydrationStrategy.ISR.value in analysis.report.hydration_strategies


def test_next_gssp_is_ssr():
    html = page('<script id="__NEXT_DATA__" type="application/json">'
                '{"gssp":true}</script>')
    analysis = analyze(html)
    assert HydrationStrategy.SSR.value in analysis.report.hydration_strategies


def test_streaming_ssr_from_flight_chunks():
    analysis = analyze(page('<script>self.__next_f.push([1,"data"]);</script>'))
    assert HydrationStrategy.STREAMING.value in analysis.report.hydration_strategies


def test_astro_islands_are_partial_hydration():
    analysis = analyze(page('<astro-island client:visible></astro-island>'))
    assert HydrationStrategy.PARTIAL.value in analysis.report.hydration_strategies
    assert "Astro" in techs(analysis)


def test_qwik_is_resumability():
    analysis = analyze(page('<div q:container="paused" q:base="/build/">'
                            '<script>qwikloader</script></div>'))
    assert HydrationStrategy.RESUMABILITY.value in analysis.report.hydration_strategies
    assert "Qwik" in techs(analysis)


def test_nuxt_reports_its_own_rendering_mode():
    ssr = analyze(page('<script>window.__NUXT__={serverRendered:true};</script>'))
    assert HydrationStrategy.SSR.value in ssr.report.hydration_strategies

    csr = analyze(page('<script>window.__NUXT__={serverRendered:false};</script>'))
    assert HydrationStrategy.CSR.value in csr.report.hydration_strategies


def test_pure_client_render_is_csr():
    analysis = analyze(page('<div id="root"></div>'
                            '<script>ReactDOM.createRoot(el).render(app);</script>'))
    assert analysis.report.hydration_strategies == [HydrationStrategy.CSR.value]


def test_csr_is_suppressed_when_server_markup_is_proven():
    """Bundles ship both mount paths; server evidence wins over a CSR marker."""
    html = page('<script>ReactDOM.createRoot(el);hydrateRoot(el,app);</script>')
    analysis = analyze(html)
    strategies = analysis.report.hydration_strategies
    assert HydrationStrategy.SSR.value in strategies
    assert HydrationStrategy.CSR.value not in strategies


def test_reconcile_keeps_csr_when_alone():
    inference = HydrationInference()
    signals = inference.from_text("ReactDOM.createRoot(el)", "inline_script[0]")
    assert inference.reconcile(signals)[0].strategy is HydrationStrategy.CSR


# ---------------------------------------------------------------------------
# dynamic imports
# ---------------------------------------------------------------------------

def test_discovers_dynamic_imports_and_loaders():
    html = page('<script>'
                'import("./routes/home.js");'
                'const L = React.lazy(() => import("./Widget.js"));'
                '__webpack_require__.e(3).then(__webpack_require__.bind(null,42));'
                '</script>')
    analysis = analyze(html)
    found = names(analysis, FindingKind.DYNAMIC_IMPORT)
    assert "./routes/home.js" in found
    assert "./Widget.js" in found
    assert "lazy routes" in found
    # The mechanism is reported under its own name; the Technology it evidences
    # still lands in the detection list.
    assert "webpack chunk loader" in found
    assert "Webpack" in techs(analysis)
    loader = next(f for f in analysis.report.by_kind(FindingKind.DYNAMIC_IMPORT)
                  if f.name == "webpack chunk loader")
    assert loader.details["technology"] == "Webpack"


def test_loader_rows_do_not_shadow_their_framework():
    """"next chunk loader" and "Next.js" are separate findings, one Technology."""
    html = page('<script>window.__NEXT_P=[];</script>',
                head='<script src="/_next/static/chunks/main-abcdef12.js"></script>')
    analysis = analyze(html)
    assert "Next.js" in names(analysis, FindingKind.FRAMEWORK)
    assert "next chunk loader" in names(analysis, FindingKind.DYNAMIC_IMPORT)
    assert [t.name for t in analysis.technologies].count("Next.js") == 1


def test_preloaded_chunks_join_the_import_graph():
    html = page("", head='<link rel="modulepreload" href="/assets/index-a1b2c3d4.js">'
                         '<script src="/_next/static/chunks/framework-99887766.js"></script>')
    found = names(analyze(html), FindingKind.DYNAMIC_IMPORT)
    assert "/assets/index-a1b2c3d4.js" in found
    assert "/_next/static/chunks/framework-99887766.js" in found


def test_ordinary_scripts_are_not_import_graph_edges():
    """Every <script src> is JavaScript; only chunks belong in the graph."""
    html = page("", head='<script src="https://www.google-analytics.com/analytics.js"></script>')
    assert names(analyze(html), FindingKind.DYNAMIC_IMPORT) == set()


def test_web_app_manifest_is_pwa_evidence():
    html = page("", head='<link rel="manifest" href="/app.webmanifest">')
    analysis = analyze(html)
    finding = next(f for f in analysis.report.by_kind(FindingKind.PWA))
    assert finding.name == "Web App Manifest"
    assert finding.value == "/app.webmanifest"


def test_vite_preload_loader():
    analysis = analyze(page('<script>window.__vitePreload(() => import("/assets/x.js"));</script>'))
    assert "Vite" in techs(analysis)


# ---------------------------------------------------------------------------
# integration through TechnologyDetector
# ---------------------------------------------------------------------------

_RUNTIME_HTML = page(
    '<div id="__next"></div>'
    '<script>window.__NEXT_DATA__={"page":"/"};window.__REDUX_STATE__={};'
    'fetch("/graphql");</script>'
)


def test_default_detect_is_unchanged_without_the_flag():
    report = TechnologyDetector().detect("https://site.test", _RUNTIME_HTML)
    assert report.runtime is None
    assert "runtime" not in report.to_dict()


def test_runtime_flag_adds_technologies_and_report():
    report = TechnologyDetector().detect("https://site.test", _RUNTIME_HTML,
                                         analyze_runtime=True)
    assert "Redux" in {t.name for t in report.technologies}
    assert report.runtime is not None
    payload = report.to_dict()["runtime"]
    # Every bucket of the output contract is present, even when empty.
    for key in ("frameworks", "hydration", "api", "runtime_config", "env",
                "state_management", "dynamic_imports", "pwa", "globals"):
        assert key in payload
    assert any(f["name"] == "/graphql" for f in payload["api"])


def test_runtime_detection_merges_rather_than_duplicates():
    """A tech found statically and at runtime stays one Technology object."""
    html = page('<div id="__next"></div>'
                '<script src="/_next/static/chunks/main.js"></script>'
                '<script>window.__NEXT_DATA__={"page":"/"};</script>')
    report = TechnologyDetector().detect("https://site.test", html,
                                         analyze_runtime=True)
    assert [t.name for t in report.technologies].count("Next.js") == 1


def test_runtime_failure_is_graceful(monkeypatch):
    from technology.runtime import analyzer as analyzer_module

    def boom(self, parsed, base_url=""):
        raise RuntimeError("runtime exploded")

    monkeypatch.setattr(analyzer_module.RuntimeAnalyzer, "analyze", boom)
    report = TechnologyDetector().detect("https://site.test", _RUNTIME_HTML,
                                         analyze_runtime=True)
    # Detection still succeeds; the stage simply contributes nothing.
    assert isinstance(report.technologies, list)
    assert report.runtime is None


def test_unparseable_payload_yields_no_detection_not_a_crash():
    html = page('<script id="__NEXT_DATA__" type="application/json">'
                '{"broken": [1, 2,,, </script>'
                '<script>window.__NEXT_DATA__;</script>')
    analysis = analyze(html)
    assert "Next.js" in techs(analysis)  # the global still stands on its own
    assert analysis.report.errors == []


def test_empty_and_garbage_input_are_safe():
    for html in ("", "<html></html>", "<script>\x00\x01</script>", "not html at all"):
        analysis = analyze(html)
        assert analysis.technologies == [] or isinstance(analysis.technologies, list)


# ---------------------------------------------------------------------------
# bounds: network, memory, time, output
# ---------------------------------------------------------------------------

def test_default_runtime_analysis_makes_no_network_calls(monkeypatch):
    """The default path must be pure text analysis - no browser, no requests."""
    import requests

    def forbidden(*args, **kwargs):
        raise AssertionError("runtime analysis must not touch the network")

    monkeypatch.setattr(requests.Session, "get", forbidden)
    monkeypatch.setattr(requests, "get", forbidden)
    report = TechnologyDetector().detect("https://site.test", _RUNTIME_HTML,
                                         analyze_runtime=True)
    assert report.runtime is not None


def test_findings_per_kind_are_capped():
    calls = "".join(f'fetch("/api/v{i}/x");' for i in range(40))
    analysis = analyze(page(f"<script>{calls}</script>"),
                       RuntimeConfig(max_findings_per_kind=5))
    assert len(analysis.report.by_kind(FindingKind.API)) <= 5


def test_scan_bytes_are_capped_and_flagged():
    filler = "var x = 1;" * 20_000
    html = page(f'<script>{filler}window.__NEXT_DATA__={{}};</script>')
    analysis = analyze(html, RuntimeConfig(max_bytes_per_unit=500,
                                           max_total_scan_bytes=1000,
                                           max_html_bytes=1000))
    assert analysis.report.truncated is True


def test_total_scan_budget_is_never_exceeded():
    """Every unit draws from one budget - including the markup unit."""
    filler = "var x = 1;" * 5_000
    html = page("".join(f"<script>{filler}</script>" for _ in range(4)))
    config = RuntimeConfig(max_total_scan_bytes=20_000, max_bytes_per_unit=8_000)
    ctx = RuntimeExtractor(config).extract(HTMLParser().parse(html),
                                           "https://site.test")
    assert ctx.scanned_bytes <= config.max_total_scan_bytes
    assert ctx.truncated is True


def test_time_budget_is_respected():
    """An exhausted budget yields a truncated report, never a hang."""
    html = page("".join(f'<script>var a{i}=1;window.__NEXT_DATA__={{}};</script>'
                        for i in range(30)))
    analysis = analyze(html, RuntimeConfig(time_budget_seconds=0.0))
    assert analysis.report.truncated is True
    assert analysis.report.elapsed >= 0.0


def test_evidence_per_finding_is_capped():
    html = page('<script>window.__NEXT_DATA__={};self.__next_f=[];'
                '_next/static;next/dist;__next_router;</script>')
    analysis = analyze(html, RuntimeConfig(max_evidence_per_finding=2))
    for finding in analysis.report.findings:
        assert len(finding.evidence) <= 2


def test_long_values_are_truncated():
    long_url = "/api/" + "a" * 200
    analysis = analyze(page(f'<script>fetch("{long_url}");</script>'),
                       RuntimeConfig(max_value_length=50))
    finding = next(f for f in analysis.report.by_kind(FindingKind.API))
    assert len(finding.value) <= 50


def test_oversized_string_literals_are_not_endpoint_candidates():
    inlined_data = "/api/" + "a" * 400
    analysis = analyze(page(f'<script>var blob = "{inlined_data}";</script>'),
                       RuntimeConfig(max_string_literal_length=100))
    assert analysis.report.by_kind(FindingKind.API) == []


# ---------------------------------------------------------------------------
# opt-in bundle scanning (Phase 2A reuse, network stubbed)
# ---------------------------------------------------------------------------

def test_bundle_scanning_is_opt_in_and_reuses_the_phase2a_fetcher(monkeypatch):
    from technology.javascript import fetcher as fetcher_module
    from technology.javascript.models import JSBundle

    bundle = 'window.__REMIX_CONTEXT__ = {}; var x = "@remix-run/react";'

    def fake_fetch(self, url):
        return JSBundle(url=url, content=bundle, size=len(bundle), status=200)

    monkeypatch.setattr(fetcher_module.BundleFetcher, "fetch", fake_fetch)
    html = page("", head='<script src="/static/app.js"></script>')

    # Off by default: nothing is downloaded, so nothing is found.
    assert "Remix" not in techs(analyze(html))

    analysis = analyze(html, RuntimeConfig(analyze_bundles=True))
    assert "Remix" in techs(analysis)
    finding = next(f for f in analysis.report.by_kind(FindingKind.FRAMEWORK)
                   if f.name == "Remix")
    assert finding.location.startswith("bundle:")


def test_bundle_failure_does_not_break_analysis(monkeypatch):
    from technology.javascript import fetcher as fetcher_module

    def boom(self, url):
        raise RuntimeError("network down")

    monkeypatch.setattr(fetcher_module.BundleFetcher, "fetch", boom)
    html = page('<script>window.__NEXT_DATA__={};</script>',
                head='<script src="/static/app.js"></script>')
    analysis = analyze(html, RuntimeConfig(analyze_bundles=True))
    # Inline evidence is unaffected by the bundle failure.
    assert "Next.js" in techs(analysis)


# ---------------------------------------------------------------------------
# unit-level primitives
# ---------------------------------------------------------------------------

def test_global_matching_is_case_sensitive():
    parser = RuntimeParser()
    assert parser.find_global('window.__ENV__={}', "__ENV__") is not None
    # JS identifiers are case-sensitive: __env__ is a different global.
    assert parser.find_global('window.__ENV__={}', "__env__") is None


def test_global_accessor_forms():
    parser = RuntimeParser()
    for code in ('window.__NUXT__', 'self["__NUXT__"]', "globalThis.__NUXT__",
                 'window["__NUXT__"]'):
        assert parser.find_global(code, "__NUXT__") is not None


def test_object_literal_extraction_is_quote_and_brace_aware():
    assert extract_object_literal(' = {"a":{"b":"}"},"c":1}', 1000) == \
        '{"a":{"b":"}"},"c":1}'
    # Never closes -> no finding, no exception.
    assert extract_object_literal(" = {unclosed", 1000) == ""
    assert extract_object_literal("not an assignment", 1000) == ""


def test_scanner_returns_nothing_for_unrelated_text():
    assert RuntimeSignatureScanner().scan("const total = price * quantity;") == {}


def test_extractor_separates_json_payloads_from_code():
    html = page('<script id="__NEXT_DATA__" type="application/json">{"a":1}</script>'
                '<script>var x = 1;</script>')
    ctx = RuntimeExtractor().extract(HTMLParser().parse(html), "https://site.test")
    assert any(b.identifier == "__NEXT_DATA__" and b.data == {"a": 1}
               for b in ctx.json_blobs)
    assert any(u.text.strip() == "var x = 1;" for u in ctx.units)


def test_extractor_prioritises_signal_bearing_scripts_under_a_cap():
    noise = "".join(f"<script>var n{i}=1;</script>" for i in range(30))
    html = page(noise + '<script>window.__NEXT_DATA__ = {};</script>')
    ctx = RuntimeExtractor(RuntimeConfig(max_inline_scripts=3)).extract(
        HTMLParser().parse(html), "https://site.test")
    inline = [u.text for u in ctx.units if u.location.startswith("inline_script")]
    assert any("__NEXT_DATA__" in t for t in inline)


@pytest.mark.parametrize("value,expected", [
    ("/graphql", "graphql"),
    ("/api/users", "rest"),
    ("wss://x.test/ws", "websocket"),
    ("/swagger.json", "openapi"),
    ("/x.json", "json"),
])
def test_endpoint_classification_table(value, expected):
    assert classify_endpoint(value).value == expected
