"""
WebIntelPro Enterprise X
JavaScript Bundle Intelligence - Content Signatures & Scanner

Scans downloaded bundle *contents* for runtime markers that identify client
libraries, frameworks, build tools and packages. Unlike the HTML pipeline
(which only sees script URLs and inline code), this looks inside the bundle
body, so it can identify a technology whose HTML fingerprints were stripped by
minification/hashing.

Matching reuses the project's :class:`technology.rules.RuleEngine`, so bundle
signatures obey the exact same word-boundary / substring semantics as every
other fingerprint - no bespoke matching logic is introduced here.

Signature authoring notes
-------------------------
* Names MUST match the canonical technology names already used by the HTML
  fingerprint database so bundle findings merge with, rather than duplicate,
  existing detections (e.g. ``Vue.js`` not ``Vue``).
* Prefer markers that survive minification: internal runtime symbols
  (``__webpack_require__``), devtools hooks, scoped-attribute prefixes and
  package specifiers. Avoid generic English words.
"""

from __future__ import annotations

import logging
from typing import Dict, List

from ..rules import RuleEngine, RuleResult

logger = logging.getLogger("webintelpro.js.scanner")

# Each entry: name, category, patterns (content markers), and optional
# version_anchors (package tokens the version extractor keys off of).
BUNDLE_SIGNATURES: List[dict] = [
    # ---- UI / rendering frameworks -------------------------------------
    {"name": "React", "category": "framework",
     "patterns": ["react-dom", "reactcurrentdispatcher", "reactcurrentowner",
                  "__secret_internals_do_not_use", "minified react error"],
     "version_anchors": ["react-dom@", "react@"]},
    {"name": "Preact", "category": "framework",
     "patterns": ["__preact", "preact/hooks", "preactelement"],
     "version_anchors": ["preact@"]},
    {"name": "Vue.js", "category": "framework",
     "patterns": ["__vue__", "__vue_app__", "__vue_devtools_global_hook__",
                  "vue.esm-", "resolvecomponent"],
     "version_anchors": ["vue@", "@vue/runtime"]},
    {"name": "Angular", "category": "framework",
     "patterns": ["ngdevmode", "ɵɵdefinecomponent", "platformbrowserdynamic",
                  "@angular/", "ng.ɵcmp"],
     "version_anchors": ["@angular/core@"]},
    {"name": "Svelte", "category": "framework",
     "patterns": ["$$invalidate", "create_fragment", "svelte/internal", "$$self"]},
    {"name": "Solid.js", "category": "framework",
     "patterns": ["_$hydration", "solid-js", "_$dx"],
     "version_anchors": ["solid-js@"]},
    {"name": "Qwik", "category": "framework",
     "patterns": ["qwikloader", "q:container", "@builder.io/qwik", "_qrl"],
     "version_anchors": ["@builder.io/qwik@"]},
    {"name": "Ember.js", "category": "framework",
     "patterns": ["ember/-internals", "enifed(", "ember-source"]},

    # ---- Meta-frameworks -----------------------------------------------
    {"name": "Next.js", "category": "framework",
     "patterns": ["__next_data__", "next/dist", "self.__next_f", "__next_f",
                  "_next/static"],
     "version_anchors": ["next@"], "implies": ["React"]},
    {"name": "Nuxt.js", "category": "framework",
     "patterns": ["__nuxt__", "usenuxtapp", "/_nuxt/", "nuxt/dist"],
     "version_anchors": ["nuxt@"], "implies": ["Vue.js"]},
    {"name": "Gatsby", "category": "framework",
     "patterns": ["___gatsby", "___loader", "gatsby-link"],
     "version_anchors": ["gatsby@"], "implies": ["React"]},
    {"name": "Remix", "category": "framework",
     "patterns": ["__remixcontext", "__remixmanifest", "@remix-run"],
     "version_anchors": ["@remix-run/react@"], "implies": ["React"]},
    {"name": "Astro", "category": "framework",
     "patterns": ["astro-island", "astro/runtime", "data-astro-cid"]},
    {"name": "SvelteKit", "category": "framework",
     "patterns": ["__sveltekit", "/_app/immutable", "@sveltejs/kit"],
     "implies": ["Svelte"]},

    # ---- Build tools / bundlers ----------------------------------------
    {"name": "Webpack", "category": "build",
     "patterns": ["__webpack_require__", "webpackjsonp", "webpackchunk",
                  "__webpack_modules__", "__webpack_exports__"]},
    {"name": "Vite", "category": "build",
     "patterns": ["import.meta.hot", "/@vite/client", "__vite__",
                  "__vite_is_modern_browser", "vite/preload-helper"]},
    {"name": "Rollup", "category": "build",
     "patterns": ["commonjshelpers", "__rollup", "rollup:"]},
    {"name": "Parcel", "category": "build",
     "patterns": ["parcelrequire", "$parcel$", "@parcel/transformer"]},
    {"name": "esbuild", "category": "build",
     "patterns": ["__esm(", "__commonjs(", "__esdecorate", "esbuild"]},
    {"name": "Turbopack", "category": "build",
     "patterns": ["__turbopack", "turbopack/runtime"]},
    {"name": "Snowpack", "category": "build",
     "patterns": ["_snowpack/", "snowpack"]},
    {"name": "Rspack", "category": "build",
     "patterns": ["__rspack_require__", "rspackchunk", "@rspack/"]},

    # ---- CSS-in-JS / styling -------------------------------------------
    {"name": "Emotion", "category": "css",
     "patterns": ["@emotion/", "__emotion_", "data-emotion"]},
    {"name": "Styled Components", "category": "css",
     "patterns": ["styled-components", "sc-component-id", "data-styled",
                  "__sc_domshouldforwardprop"]},
    {"name": "Tailwind CSS", "category": "css",
     "patterns": ["tailwindcss", "--tw-ring", "--tw-translate"]},
    {"name": "Bootstrap", "category": "css",
     "patterns": ["data-bs-toggle", "bs.dropdown", "bs.modal", "bootstrap.min"]},

    # ---- Component libraries -------------------------------------------
    {"name": "Material UI", "category": "javascript",
     "patterns": ["@mui/", "@material-ui/", "muithemeprovider", "makestyles"],
     "version_anchors": ["@mui/material@"]},
    {"name": "Chakra UI", "category": "javascript",
     "patterns": ["@chakra-ui", "chakra-ui-", "usechakra"]},
    {"name": "Ant Design", "category": "javascript",
     "patterns": ["ant-design", "rc-util", "antd/es", "antd/lib"]},
    {"name": "Mantine", "category": "javascript",
     "patterns": ["@mantine/", "mantineprovider", "mantine-"]},

    # ---- State / data layer --------------------------------------------
    {"name": "Redux", "category": "javascript",
     "patterns": ["@@redux/init", "__redux_devtools_extension", "combinereducers"]},
    {"name": "React Query", "category": "javascript",
     "patterns": ["@tanstack/query", "react-query", "queryclientprovider",
                  "querycache"]},
    {"name": "Zustand", "category": "javascript",
     "patterns": ["zustand", "zustand/middleware"]},
    {"name": "MobX", "category": "javascript",
     "patterns": ["__mobxglobals", "makeautoobservable", "mobxadministration"]},
    {"name": "Apollo", "category": "javascript",
     "patterns": ["@apollo/client", "apolloclient", "__apollo_client__",
                  "apollolink"]},
    {"name": "Relay", "category": "javascript",
     "patterns": ["relay-runtime", "relaymodernrecord", "__relay_store"]},
    {"name": "RxJS", "category": "javascript",
     "patterns": ["rxjs/operators", "rxjscompat", "rxjs/internal"]},
]


class BundleScanner:
    """Scans bundle text for :data:`BUNDLE_SIGNATURES` matches.

    :meth:`scan` returns a mapping of technology name -> merged
    :class:`technology.rules.RuleResult` for a single bundle. Callers
    (the analyzer) merge these across bundles before scoring.
    """

    def __init__(self, signatures: List[dict] | None = None):
        self.signatures = signatures if signatures is not None else BUNDLE_SIGNATURES
        self.engine = RuleEngine()

    def scan(self, text: str) -> Dict[str, RuleResult]:
        """Return {tech_name: RuleResult} for every signature that matched."""
        results: Dict[str, RuleResult] = {}
        if not text:
            return results
        low = text.lower()
        for sig in self.signatures:
            result = self.engine.match(sig["patterns"], low)
            if result.matched:
                results[sig["name"]] = result
        if results:
            logger.debug("bundle scan matched: %s", ", ".join(sorted(results)))
        return results
