"""
WebIntelPro Enterprise X
JavaScript Runtime Intelligence (Phase 2B) - Signatures & Inference

The semantic layer: what a runtime marker *means*. :mod:`parser` finds syntax,
this module decides which technology, capability or rendering strategy that
syntax implies, and :mod:`analyzer` scores and reports the result.

Three databases live here, and extending the stage almost always means adding a
row to one of them rather than writing code:

* :data:`RUNTIME_SIGNATURES` - runtime frameworks, state managers and PWA
  capabilities, keyed on globals and content markers
* :data:`CONFIG_GLOBALS`     - globals that hold a runtime configuration object
* :data:`HYDRATION_RULES`    - markers that reveal a rendering/hydration strategy

Authoring rules
---------------
* ``technology`` MUST use the canonical name already in the fingerprint
  database (``Vue.js``, not ``Vue``) so runtime findings merge with, rather
  than duplicate, existing detections. An empty ``technology`` means the
  signature reports a capability only and emits no Technology object.
* Put short, English-like globals (``React``, ``Vue``, ``angular``) in
  ``strict_globals``: they are only matched via an explicit accessor
  (``window.React``). Dunder payload names go in ``globals``, where a bare match
  is also allowed because they appear in markup (``id="__NEXT_DATA__"``).
* Prefer markers that survive minification and mean one thing only. A generic
  word costs recall nothing and costs precision everything.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from ..rules import RuleEngine, RuleResult
from .models import FindingKind, HydrationStrategy, RuntimeConfig, RuntimeSource
from .parser import RuntimeParser, present

logger = logging.getLogger("webintelpro.runtime.detector")


@dataclass(frozen=True, slots=True)
class RuntimeSignature:
    """One technology's or capability's runtime evidence definition.

    ``globals``/``strict_globals`` are matched as JavaScript global references;
    ``patterns`` are free-text markers matched through the shared
    :class:`technology.rules.RuleEngine`, so they obey exactly the same
    word-boundary semantics as every other fingerprint in the project.
    """

    technology: str
    category: str
    kind: FindingKind
    globals: Tuple[str, ...] = ()
    strict_globals: Tuple[str, ...] = ()
    patterns: Tuple[str, ...] = ()
    implies: Tuple[str, ...] = ()
    # What the *finding* is called, when that differs from the technology it
    # evidences. A capability row ("Push Notifications") has only a label; a
    # loader row ("next chunk loader") has both, because the finding describes a
    # mechanism while the Technology it proves is the framework behind it.
    label: str = ""

    @property
    def name(self) -> str:
        """The name this signature's finding is reported under.

        Distinct from :attr:`technology`, which is what gets emitted into the
        detection list. Keeping them separate lets several rows evidence one
        technology under their own names ("Next.js" the framework, "next chunk
        loader" the import-graph mechanism) instead of shadowing each other.
        """
        return self.label or self.technology


# ---------------------------------------------------------------------------
# Runtime frameworks
# ---------------------------------------------------------------------------
_FRAMEWORKS: List[RuntimeSignature] = [
    RuntimeSignature(
        technology="React", category="framework", kind=FindingKind.FRAMEWORK,
        globals=("__REACT_DEVTOOLS_GLOBAL_HOOK__", "__reactContainer",
                 "__REACT_ROOT__"),
        strict_globals=("React", "ReactDOM"),
        patterns=("react-dom", "reactcurrentdispatcher", "hydrateroot",
                  "reactdom.createroot", "react.createelement",
                  "__secret_internals_do_not_use", "data-reactroot"),
    ),
    RuntimeSignature(
        technology="Preact", category="framework", kind=FindingKind.FRAMEWORK,
        globals=("__PREACT_DEVTOOLS__", "__preact"),
        patterns=("preact/hooks", "preact/compat", "preactelement"),
    ),
    RuntimeSignature(
        technology="Inferno", category="javascript", kind=FindingKind.FRAMEWORK,
        globals=("__INFERNO_DEVTOOLS_GLOBAL_HOOK__",),
        patterns=("inferno-create-element", "infernoprops", "inferno/dist"),
    ),
    RuntimeSignature(
        technology="Vue.js", category="framework", kind=FindingKind.FRAMEWORK,
        globals=("__VUE__", "__VUE_APP__", "__VUE_DEVTOOLS_GLOBAL_HOOK__",
                 "__VUE_HMR_RUNTIME__"),
        strict_globals=("Vue",),
        patterns=("createssrapp", "vue.createapp", "__vue_app__",
                  "data-v-app", "vue.esm-"),
    ),
    RuntimeSignature(
        technology="Angular", category="framework", kind=FindingKind.FRAMEWORK,
        globals=("ngDevMode", "getAllAngularRootElements"),
        # "ng" is accessor-only: a bare two-letter token appears in unrelated
        # identifiers and prose constantly.
        strict_globals=("ng",),
        patterns=("bootstrapapplication", "platformbrowserdynamic",
                  "@angular/core", "ng-version", "ngzone", "ɵɵdefinecomponent"),
    ),
    RuntimeSignature(
        technology="AngularJS", category="framework", kind=FindingKind.FRAMEWORK,
        strict_globals=("angular",),
        patterns=("angular.module", "ng-app", "ng-controller", "angular.bootstrap"),
    ),
    RuntimeSignature(
        technology="Svelte", category="framework", kind=FindingKind.FRAMEWORK,
        globals=("__svelte", "__SVELTE_DEVTOOLS_GLOBAL_HOOK__"),
        patterns=("svelte/internal", "$$invalidate", "create_fragment"),
    ),
    RuntimeSignature(
        technology="SvelteKit", category="framework", kind=FindingKind.FRAMEWORK,
        globals=("__SVELTEKIT_DATA__", "__sveltekit", "__SVELTEKIT_PAYLOAD__"),
        patterns=("@sveltejs/kit", "/_app/immutable", "data-sveltekit",
                  "kit.start("),
        implies=("Svelte",),
    ),
    RuntimeSignature(
        technology="Solid.js", category="framework", kind=FindingKind.FRAMEWORK,
        globals=("_$HY", "__SOLID_DEVTOOLS__"),
        patterns=("solid-js", "_$hydration", "hydrationscript"),
    ),
    RuntimeSignature(
        technology="SolidStart", category="framework", kind=FindingKind.FRAMEWORK,
        globals=("_$HY",),
        patterns=("solid-start", "@solidjs/start"),
        implies=("Solid.js",),
    ),
    RuntimeSignature(
        technology="Qwik", category="framework", kind=FindingKind.FRAMEWORK,
        globals=("__QWIK__", "qwikevents"),
        patterns=("qwikloader", "q:container", "q:base", "q:render",
                  "@builder.io/qwik", "q:instance"),
    ),
    RuntimeSignature(
        technology="Astro", category="framework", kind=FindingKind.FRAMEWORK,
        globals=("__ASTRO__",),
        patterns=("astro-island", "data-astro-cid", "astro/runtime",
                  "client:load", "client:visible", "client:idle"),
    ),
    RuntimeSignature(
        technology="Next.js", category="framework", kind=FindingKind.FRAMEWORK,
        globals=("__NEXT_DATA__", "__NEXT_F", "__next_f", "__NEXT_LOADED_PAGES__",
                 "__BUILD_MANIFEST", "__NEXT_P"),
        patterns=("_next/static", "next/dist", "__next_router",
                  "next-route-announcer"),
        implies=("React",),
    ),
    RuntimeSignature(
        technology="Nuxt.js", category="framework", kind=FindingKind.FRAMEWORK,
        globals=("__NUXT__", "__NUXT_DATA__", "$nuxt", "__NUXT_PAYLOAD__"),
        patterns=("usenuxtapp", "/_nuxt/", "nuxt-link", "nuxt/dist"),
        implies=("Vue.js",),
    ),
    RuntimeSignature(
        technology="Remix", category="framework", kind=FindingKind.FRAMEWORK,
        globals=("__remixContext", "__remixManifest", "__remixRouteModules"),
        patterns=("@remix-run", "remix:manifest"),
        implies=("React",),
    ),
    RuntimeSignature(
        technology="Gatsby", category="framework", kind=FindingKind.FRAMEWORK,
        globals=("___gatsby", "__GATSBY", "___chunkMapping"),
        patterns=("gatsby-link", "page-data.json", "gatsby-browser"),
        implies=("React",),
    ),
]

# ---------------------------------------------------------------------------
# State management / data layer
# ---------------------------------------------------------------------------
_STATE: List[RuntimeSignature] = [
    RuntimeSignature(
        technology="Redux", category="javascript", kind=FindingKind.STATE_MANAGEMENT,
        globals=("__REDUX_STATE__", "__REDUX_DEVTOOLS_EXTENSION__",
                 "__REDUX_DEVTOOLS_EXTENSION_COMPOSE__", "__PRELOADED_STATE__"),
        patterns=("@@redux/init", "combinereducers", "createstore(",
                  "react-redux"),
    ),
    RuntimeSignature(
        technology="Redux Toolkit", category="javascript",
        kind=FindingKind.STATE_MANAGEMENT,
        patterns=("@reduxjs/toolkit", "configurestore(", "createslice(",
                  "createasyncthunk("),
        implies=("Redux",),
    ),
    RuntimeSignature(
        technology="MobX", category="javascript", kind=FindingKind.STATE_MANAGEMENT,
        globals=("__mobxGlobals", "__MOBX_DEVTOOLS_GLOBAL_HOOK__",
                 "__mobxInstanceCount"),
        patterns=("makeautoobservable", "mobxadministration", "mobx-react"),
    ),
    RuntimeSignature(
        technology="Zustand", category="javascript", kind=FindingKind.STATE_MANAGEMENT,
        patterns=("zustand/middleware", "zustand/vanilla", "zustand"),
    ),
    RuntimeSignature(
        technology="Pinia", category="javascript", kind=FindingKind.STATE_MANAGEMENT,
        globals=("__PINIA__", "__pinia"),
        patterns=("definestore(", "createpinia(", "pinia/dist"),
        implies=("Vue.js",),
    ),
    RuntimeSignature(
        technology="Vuex", category="javascript", kind=FindingKind.STATE_MANAGEMENT,
        globals=("__VUEX__",),
        strict_globals=("Vuex",),
        patterns=("vuex/dist", "new vuex.store", "createstore({state"),
        implies=("Vue.js",),
    ),
    RuntimeSignature(
        technology="Apollo", category="javascript", kind=FindingKind.STATE_MANAGEMENT,
        globals=("__APOLLO_STATE__", "__APOLLO_CLIENT__"),
        patterns=("@apollo/client", "apolloclient", "apollolink",
                  "inmemorycache"),
    ),
    RuntimeSignature(
        technology="Relay", category="javascript", kind=FindingKind.STATE_MANAGEMENT,
        globals=("__RELAY_STORE__", "__RELAY_BOOTSTRAP_DATA__"),
        patterns=("relay-runtime", "relaymodernrecord", "relayenvironment"),
    ),
    RuntimeSignature(
        technology="React Query", category="javascript",
        kind=FindingKind.STATE_MANAGEMENT,
        globals=("__REACT_QUERY_STATE__", "__TANSTACK_QUERY_STATE__"),
        patterns=("@tanstack/query", "@tanstack/react-query", "react-query",
                  "queryclientprovider", "querycache"),
    ),
    RuntimeSignature(
        technology="SWR", category="javascript", kind=FindingKind.STATE_MANAGEMENT,
        globals=("__SWR_CACHE__",),
        patterns=("swr/_internal", "useswrconfig", "swrconfig"),
    ),
]

# ---------------------------------------------------------------------------
# PWA runtime
#
# Capability rows (empty ``technology``) report what the page *does* -
# registering a worker, subscribing to push - and emit no Technology object,
# because "Push Notifications" is a browser capability, not a vendor's product.
# ---------------------------------------------------------------------------
_PWA: List[RuntimeSignature] = [
    RuntimeSignature(
        technology="Service Worker", category="pwa", kind=FindingKind.PWA,
        patterns=("navigator.serviceworker.register", "serviceworker.register",
                  "navigator.serviceworker"),
    ),
    RuntimeSignature(
        technology="Workbox", category="pwa", kind=FindingKind.PWA,
        globals=("__WB_MANIFEST",),
        strict_globals=("workbox",),
        patterns=("workbox-sw", "workbox-window", "workbox-precaching",
                  "workbox.routing", "self.__wb_manifest"),
        implies=("Service Worker",),
    ),
    RuntimeSignature(
        technology="", label="Push Notifications", category="pwa",
        kind=FindingKind.PWA,
        patterns=("pushmanager.subscribe", "pushmanager", "push-subscription",
                  "notification.requestpermission"),
    ),
    RuntimeSignature(
        technology="", label="Offline Cache", category="pwa", kind=FindingKind.PWA,
        patterns=("caches.open(", "cachestorage", "cache.addall(",
                  "skipwaiting()", "clients.claim()"),
    ),
    RuntimeSignature(
        technology="", label="Background Sync", category="pwa", kind=FindingKind.PWA,
        patterns=("syncmanager", "registration.sync.register", "periodicsync"),
    ),
]

# ---------------------------------------------------------------------------
# Dynamic import graph
# ---------------------------------------------------------------------------
_LOADERS: List[RuntimeSignature] = [
    RuntimeSignature(
        technology="Webpack", category="build", kind=FindingKind.DYNAMIC_IMPORT,
        globals=("webpackChunk", "webpackJsonp", "__webpack_require__"),
        patterns=("__webpack_require__.e(", "__webpack_require__.u(",
                  "webpackchunkname", "webpack_public_path"),
        label="webpack chunk loader",
    ),
    RuntimeSignature(
        technology="Vite", category="build", kind=FindingKind.DYNAMIC_IMPORT,
        globals=("__vitePreload", "__VITE_PRELOAD__"),
        patterns=("vite/preload-helper", "/@vite/client", "__vite_is_modern_browser"),
        label="vite preload",
    ),
    RuntimeSignature(
        technology="Next.js", category="framework", kind=FindingKind.DYNAMIC_IMPORT,
        globals=("__NEXT_LOADED_PAGES__", "__NEXT_P"),
        patterns=("_next/static/chunks", "next/dynamic"),
        label="next chunk loader",
    ),
    RuntimeSignature(
        technology="Nuxt.js", category="framework", kind=FindingKind.DYNAMIC_IMPORT,
        patterns=("/_nuxt/", "nuxt-chunk", "definenuxtcomponent"),
        label="nuxt chunks",
    ),
    RuntimeSignature(
        technology="", label="lazy routes", category="javascript",
        kind=FindingKind.DYNAMIC_IMPORT,
        patterns=("react.lazy(", "defineasynccomponent(", "loadable(",
                  "loadcomponent(", "lazy(() =>", "import(/* webpackchunkname"),
    ),
    RuntimeSignature(
        technology="Turbopack", category="build", kind=FindingKind.DYNAMIC_IMPORT,
        globals=("__turbopack_load__", "TURBOPACK"),
        patterns=("turbopack/runtime", "__turbopack_require__"),
        label="turbopack chunk loader",
    ),
]

RUNTIME_SIGNATURES: List[RuntimeSignature] = _FRAMEWORKS + _STATE + _PWA + _LOADERS

# Globals whose value is a runtime configuration object. The parser extracts the
# assigned literal; the analyzer reports its keys.
CONFIG_GLOBALS: Tuple[Tuple[str, bool], ...] = (
    # (global name, bare match allowed)
    ("__ENV__", True),
    ("__env__", True),
    ("__CONFIG__", True),
    ("__RUNTIME_CONFIG__", True),
    ("__APP_CONFIG__", True),
    ("__NEXT_DATA__", True),
    ("__NUXT__", True),
    ("ENV", False),
    ("env", False),
    ("config", False),
    ("APP_CONFIG", False),
    ("runtimeConfig", False),
    ("publicRuntimeConfig", False),
)

# Payload globals that carry hydration state but name no specific vendor. They
# are reported as globals (and feed hydration inference) without implying a
# technology - "some store is being rehydrated" is the honest reading.
GENERIC_STATE_GLOBALS: Tuple[str, ...] = (
    "__INITIAL_STATE__",
    "__initialState__",
    "__PRELOADED_STATE__",
    "__STATE__",
    "__INITIAL_DATA__",
    "__SERVER_DATA__",
    "__HYDRATION_DATA__",
)


@dataclass(frozen=True, slots=True)
class HydrationRule:
    """A marker set that reveals one rendering/hydration strategy."""

    strategy: HydrationStrategy
    patterns: Tuple[str, ...] = ()
    globals: Tuple[str, ...] = ()
    technology: str = ""
    note: str = ""


HYDRATION_RULES: List[HydrationRule] = [
    HydrationRule(
        strategy=HydrationStrategy.SSR, technology="React",
        patterns=("hydrateroot(", "reactdom.hydrate(", "data-reactroot"),
        note="client hydrates server-rendered React markup",
    ),
    HydrationRule(
        strategy=HydrationStrategy.SSR, technology="Vue.js",
        patterns=("createssrapp(", "data-server-rendered"),
        note="Vue SSR app created on the client",
    ),
    HydrationRule(
        strategy=HydrationStrategy.SSR, technology="Remix",
        globals=("__remixContext",),
        note="Remix server context embedded for hydration",
    ),
    HydrationRule(
        strategy=HydrationStrategy.SSR, technology="SvelteKit",
        globals=("__SVELTEKIT_DATA__",), patterns=("data-sveltekit-hydrate",),
        note="SvelteKit server payload embedded for hydration",
    ),
    HydrationRule(
        strategy=HydrationStrategy.SSR, technology="Solid.js",
        globals=("_$HY",), patterns=("hydrationscript",),
        note="Solid hydration payload present",
    ),
    HydrationRule(
        strategy=HydrationStrategy.SSR, technology="Angular",
        patterns=("ngh=", "@angular/ssr", "ng-server-context"),
        note="Angular SSR/hydration markers present",
    ),
    HydrationRule(
        strategy=HydrationStrategy.STREAMING, technology="Next.js",
        globals=("__next_f", "__NEXT_F"),
        patterns=("rendertopipeablestream", "rendertoreadablestream"),
        note="React Server Components streamed in flight chunks",
    ),
    HydrationRule(
        strategy=HydrationStrategy.PARTIAL, technology="Astro",
        patterns=("astro-island", "client:load", "client:visible", "client:idle",
                  "client:media"),
        note="Astro islands hydrate selected components only",
    ),
    HydrationRule(
        strategy=HydrationStrategy.RESUMABILITY, technology="Qwik",
        patterns=("q:container", "qwikloader", "q:base", "q:func"),
        note="Qwik resumes serialized server state without hydration",
    ),
    HydrationRule(
        strategy=HydrationStrategy.CSR, technology="React",
        patterns=("reactdom.createroot(", "reactdom.render("),
        note="React mounts client-side into an empty container",
    ),
    HydrationRule(
        strategy=HydrationStrategy.CSR, technology="Vue.js",
        patterns=("vue.createapp(", "new vue(",),
        note="Vue mounts client-side",
    ),
    HydrationRule(
        strategy=HydrationStrategy.CSR, technology="Angular",
        patterns=("bootstrapapplication(", "bootstrapmodule("),
        note="Angular bootstraps client-side",
    ),
    HydrationRule(
        strategy=HydrationStrategy.SSG, technology="Gatsby",
        patterns=("page-data.json", "___gatsby"),
        note="Gatsby serves prebuilt static pages with page-data payloads",
    ),
]

# Server-rendering strategies. Their presence means a page was NOT purely
# client-rendered, so a CSR reading is suppressed (see HydrationInference).
_SERVER_STRATEGIES = frozenset({
    HydrationStrategy.SSR, HydrationStrategy.SSG, HydrationStrategy.ISR,
    HydrationStrategy.STREAMING, HydrationStrategy.PARTIAL,
    HydrationStrategy.RESUMABILITY,
})


class RuntimeSignatureScanner:
    """Matches :data:`RUNTIME_SIGNATURES` against one unit of text.

    Global references are matched via :class:`RuntimeParser` (accessor-aware);
    content markers via the shared :class:`technology.rules.RuleEngine`. Both
    contribute to a single :class:`technology.rules.RuleResult` per signature,
    which the analyzer merges across units and scores once.
    """

    def __init__(self, config: RuntimeConfig | None = None,
                 signatures: List[RuntimeSignature] | None = None):
        self.config = config or RuntimeConfig()
        self.signatures = signatures if signatures is not None else RUNTIME_SIGNATURES
        self.parser = RuntimeParser(self.config)
        self.engine = RuleEngine()
        # Name -> signature index. Several rows can report the same name (a
        # framework and its chunk loader, say); the first wins, matching the
        # order the databases are declared in.
        self._by_name: Dict[str, RuntimeSignature] = {}
        for sig in self.signatures:
            self._by_name.setdefault(sig.name, sig)

    def scan(self, text: str) -> Dict[str, RuleResult]:
        """Return ``{signature name: RuleResult}`` for everything that matched.

        Keyed by :attr:`RuntimeSignature.name` (the technology, or the label for
        capability rows), so the analyzer can look the signature back up.

        Every candidate is gated behind :func:`present` first. Without that,
        this method runs one regex pass per global per signature over the whole
        unit - hundreds of full scans of text that, almost always, does not
        contain the token at all.
        """
        results: Dict[str, RuleResult] = {}
        if not text:
            return results
        low = text.lower()
        for sig in self.signatures:
            result = RuleResult()

            for name in sig.globals:
                if not present(name, low):
                    continue
                snippet = self.parser.find_global(text, name, allow_bare=True)
                if snippet:
                    result.matched = True
                    result.evidence.append(f"window.{name}")
                    result.contexts.append(snippet)
            for name in sig.strict_globals:
                if not present(name, low):
                    continue
                snippet = self.parser.find_global(text, name, allow_bare=False)
                if snippet:
                    result.matched = True
                    result.evidence.append(f"window.{name}")
                    result.contexts.append(snippet)

            candidates = [p for p in sig.patterns if present(p, low)]
            if candidates:
                result.merge(self.engine.match(candidates, low))

            if result.matched:
                existing = results.get(sig.name)
                if existing is None:
                    results[sig.name] = result
                else:
                    existing.merge(result)
        return results

    def signature_for(self, name: str) -> RuntimeSignature | None:
        """Look a signature up by its reported name."""
        return self._by_name.get(name)


@dataclass(slots=True)
class HydrationSignal:
    """One matched hydration marker, before strategies are reconciled."""

    strategy: HydrationStrategy
    technology: str
    evidence: List[str] = field(default_factory=list)
    note: str = ""
    location: str = ""
    source: RuntimeSource = RuntimeSource.INLINE_SCRIPT


class HydrationInference:
    """Infers rendering strategies (SSR / CSR / SSG / ISR / ...) from markers.

    Two inputs are combined:

    * :data:`HYDRATION_RULES` matched against code and markup, and
    * framework payloads (``__NEXT_DATA__``, ``__NUXT__``), which state the
      answer outright - Next.js records ``gsp``/``gssp`` flags and Nuxt records
      ``serverRendered`` - and are therefore trusted over marker heuristics.
    """

    def __init__(self, config: RuntimeConfig | None = None):
        self.config = config or RuntimeConfig()
        self.parser = RuntimeParser(self.config)
        self.engine = RuleEngine()

    def from_text(self, text: str, location: str,
                  source: RuntimeSource = RuntimeSource.INLINE_SCRIPT
                  ) -> List[HydrationSignal]:
        """Match the hydration rules against one unit of text."""
        signals: List[HydrationSignal] = []
        if not text:
            return signals
        low = text.lower()
        for rule in HYDRATION_RULES:
            evidence: List[str] = []
            for name in rule.globals:
                if not present(name, low):
                    continue
                if self.parser.find_global(text, name, allow_bare=True):
                    evidence.append(f"window.{name}")
            candidates = [p for p in rule.patterns if present(p, low)]
            if candidates:
                result = self.engine.match(candidates, low)
                if result.matched:
                    evidence.extend(result.evidence)
            if evidence:
                signals.append(HydrationSignal(
                    strategy=rule.strategy, technology=rule.technology,
                    evidence=evidence, note=rule.note, location=location,
                    source=source))
        return signals

    def from_next_data(self, data, location: str) -> List[HydrationSignal]:
        """Read Next.js rendering flags out of a parsed ``__NEXT_DATA__``.

        Next records how the page was produced: ``gsp`` for getStaticProps
        (SSG), ``gssp`` for getServerSideProps (SSR), and a ``revalidate`` hint
        for incremental regeneration (ISR). This is authoritative, not inferred.
        """
        signals: List[HydrationSignal] = []
        if not isinstance(data, dict):
            return signals
        json_source = RuntimeSource.EMBEDDED_JSON
        if data.get("gssp"):
            signals.append(HydrationSignal(
                HydrationStrategy.SSR, "Next.js", ["__NEXT_DATA__.gssp"],
                "getServerSideProps: rendered per request", location, json_source))
        if data.get("gsp"):
            signals.append(HydrationSignal(
                HydrationStrategy.SSG, "Next.js", ["__NEXT_DATA__.gsp"],
                "getStaticProps: prerendered at build time", location, json_source))
        if data.get("isFallback"):
            signals.append(HydrationSignal(
                HydrationStrategy.ISR, "Next.js", ["__NEXT_DATA__.isFallback"],
                "fallback page: generated on demand", location, json_source))
        props = data.get("props")
        if isinstance(props, dict) and "__N_SSG" in props:
            signals.append(HydrationSignal(
                HydrationStrategy.SSG, "Next.js", ["props.__N_SSG"],
                "static generation flag", location, json_source))
        if isinstance(props, dict) and "__N_SSP" in props:
            signals.append(HydrationSignal(
                HydrationStrategy.SSR, "Next.js", ["props.__N_SSP"],
                "server-side props flag", location, json_source))
        return signals

    def from_nuxt_payload(self, text: str, location: str,
                          source: RuntimeSource = RuntimeSource.INLINE_SCRIPT
                          ) -> List[HydrationSignal]:
        """Read Nuxt's ``serverRendered`` flag from its payload assignment.

        The payload is a JavaScript literal rather than strict JSON, so the flag
        is read textually; both quoted and bare key forms are accepted.
        """
        if not text:
            return []
        low = text.lower()
        for needle, rendered in (('"serverrendered":true', True),
                                 ("serverrendered:true", True),
                                 ('"serverrendered":false', False),
                                 ("serverrendered:false", False)):
            if needle in low:
                if rendered:
                    return [HydrationSignal(
                        HydrationStrategy.SSR, "Nuxt.js",
                        ["__NUXT__.serverRendered=true"],
                        "Nuxt payload reports server rendering", location, source)]
                return [HydrationSignal(
                    HydrationStrategy.CSR, "Nuxt.js",
                    ["__NUXT__.serverRendered=false"],
                    "Nuxt payload reports client-side rendering", location, source)]
        return []

    @staticmethod
    def reconcile(signals: List[HydrationSignal]) -> List[HydrationSignal]:
        """Drop contradicted readings, keeping the defensible ones.

        A single bundle commonly contains both mount paths (``createRoot`` and
        ``hydrateRoot``), so a CSR marker alone proves little. When any
        server-rendering strategy is also present, the CSR reading is dropped:
        the page demonstrably arrived with server markup.
        """
        if not signals:
            return []
        strategies = {s.strategy for s in signals}
        if strategies & _SERVER_STRATEGIES:
            return [s for s in signals if s.strategy is not HydrationStrategy.CSR]
        return signals
