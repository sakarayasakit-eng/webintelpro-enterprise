"""
WebIntelPro Enterprise X
Technology Detection Engine v5
"""

from __future__ import annotations

import logging
import time
from typing import Dict

from .confidence import ConfidenceEngine
from .fingerprints import TECH_FINGERPRINTS
from .matcher import FingerprintMatcher
from .models import Technology, TechnologyReport
from .parser import HTMLParser
from .utils import normalize_headers
from .version import VersionEngine

logger = logging.getLogger("webintelpro.detector")

# Categories that map to a single "primary" field on the report.
_PRIMARY = {"server": "server", "cms": "cms"}


class TechnologyDetector:

    MIN_CONFIDENCE = 0.30

    def __init__(self):
        self.parser = HTMLParser()
        self.matcher = FingerprintMatcher()
        self.confidence = ConfidenceEngine()
        self.version = VersionEngine()
        # Lazily-built JavaScript bundle analyzer (Phase 2A). Stays None on the
        # default, network-free path so existing callers (and benchmark.py) are
        # completely unaffected; only detect(analyze_js=True) constructs it.
        self._js_analyzer = None
        # Lazily-built JavaScript runtime analyzer (Phase 2B). Same contract as
        # the bundle analyzer above: stays None unless detect(analyze_runtime=
        # True) asks for it, so the default path is untouched.
        self._runtime_analyzer = None
        # Lazily-built API discovery orchestrator (Phase 2C). Same contract
        # again: stays None unless detect(analyze_api=True) asks for it.
        self._api_discoverer = None
        # Lazily-built AI stack detector (Phase 2D). Same contract again:
        # stays None unless detect(analyze_ai_stack=True) asks for it.
        self._ai_stack_detector = None
        # Category lookup so an *implied* technology (one that has no direct
        # signal on the page but is entailed by another detected tech, e.g.
        # Next.js -> React) can be materialised with the right category.
        self._category_by_name = {
            rule["name"]: rule["category"] for rule in TECH_FINGERPRINTS
        }

    def detect(self, url: str, html: str = "",
               headers: Dict[str, str] | None = None,
               cookies: Dict[str, str] | None = None,
               debug: bool = False,
               analyze_js: bool = False,
               js_config=None,
               analyze_runtime: bool = False,
               runtime_config=None,
               analyze_api: bool = False,
               api_config=None,
               analyze_ai_stack: bool = False,
               ai_stack_config=None) -> TechnologyReport:
        """Detect the technologies behind ``url``.

        The static pipeline (headers/cookies/HTML/DOM) always runs. Four
        opt-in stages may then *add* to it, and are skipped entirely when off:

        * ``analyze_js``      - Phase 2A: download and scan JS bundle contents.
        * ``analyze_runtime`` - Phase 2B: read the page's runtime surface
          (globals, hydration payloads, embedded JSON) without a browser, and
          attach structured findings to ``report.runtime``.
        * ``analyze_api``     - Phase 2C: discover the page's API surface
          (REST/JSON endpoints, GraphQL, Swagger/OpenAPI, RPC, WebSocket, SSE)
          from HTML/JS, and attach structured findings to
          ``report.api_discovery``. Network-free unless ``api_config`` opts
          into reachability probing.
        * ``analyze_ai_stack`` - Phase 2D: identify the page's AI stack
          (providers, open-source models, local AI, frameworks, SDKs, vector
          databases, embedding services, infrastructure) from HTML/JS/headers,
          and attach structured findings to ``report.ai_stack``. Network-free,
          always.

        With all four flags False, detection is byte-for-byte identical to
        Phase 1.
        """
        start = time.perf_counter()
        headers = normalize_headers(headers or {})
        cookies = cookies or {}

        report = TechnologyReport(url=url)
        report.headers = headers
        report.cookies = cookies

        parsed = self.parser.parse(html)
        report.meta = parsed.meta

        detected: Dict[str, Technology] = {}
        # implied_name -> (best source confidence, source tech name)
        implications: Dict[str, tuple] = {}

        for rule in TECH_FINGERPRINTS:
            matches = self.matcher.evaluate(rule, parsed, headers, cookies)
            score = self.confidence.calculate(matches)
            if score < self.MIN_CONFIDENCE:
                continue

            # FP guard for heuristic rules (e.g. utility-class CSS frameworks):
            # require at least N distinct matched signals so a single generic
            # token can't trigger a detection on its own.
            min_ev = rule.get("min_evidence")
            if min_ev:
                distinct = sum(
                    len(set(r.evidence)) for r in matches.values() if r.matched
                )
                if distinct < min_ev:
                    continue

            # This rule fired, so anything it entails is now supported.
            for implied in rule.get("implies", []):
                prev = implications.get(implied)
                if prev is None or score > prev[0]:
                    implications[implied] = (score, rule["name"])

            tech = Technology(
                name=rule["name"],
                category=rule["category"],
                confidence=score,
                version=self._extract_version(matches),
                evidence=self._collect_evidence(matches),
                debug=self.confidence.breakdown(matches) if debug else None,
            )

            existing = detected.get(tech.name)

            if existing is None:

                detected[tech.name] = tech

            else:

                # Keep highest confidence

                if tech.confidence > existing.confidence:
                    existing.confidence = tech.confidence

                # Keep first valid version

                if existing.version is None and tech.version:
                    existing.version = tech.version

                # Merge evidence

                existing.evidence.extend(tech.evidence)
                existing.evidence = sorted(set(existing.evidence))

                # Merge debug breakdowns (rule name is the same technology
                # matched via more than one fingerprint entry)

                if debug:
                    existing.debug = {**(existing.debug or {}), **tech.debug}

            # ----------------------------------------------------------
            # Primary technology selection
            # Always keep the highest-confidence CMS / Server
            # ----------------------------------------------------------

            field = _PRIMARY.get(rule["category"])

            if field:

                current = getattr(report, field)

                if current is None:

                     setattr(report, field, tech.name)

                else:

                    current_obj = detected.get(current)

                    if (
                        current_obj is None
                        or tech.confidence > current_obj.confidence
                     ):
                        setattr(report, field, tech.name)

        # ----------------------------------------------------------
        # Implication pass: a detected technology can entail another that
        # leaves no direct fingerprint of its own (meta-frameworks bundle
        # and hash their runtime, so React/Vue markers vanish in prod).
        # A directly-detected tech always keeps its own, stronger evidence.
        # ----------------------------------------------------------
        for imp_name, (src_conf, src_name) in implications.items():
            existing = detected.get(imp_name)
            if existing is not None:
                continue
            derived = round(min(src_conf, 0.95) * 0.95, 3)
            derived = max(derived, self.MIN_CONFIDENCE)
            detected[imp_name] = Technology(
                name=imp_name,
                category=self._category_by_name.get(imp_name, "javascript"),
                confidence=derived,
                version=None,
                evidence=[f"implied:{src_name}"],
            )

        # ----------------------------------------------------------
        # JavaScript bundle intelligence (Phase 2A) -- opt-in stage.
        # Runs after headers/cookies/HTML/DOM so it only *adds* to, or
        # reinforces, what the static pipeline already found. Disabled by
        # default: with analyze_js=False this block is skipped entirely and
        # detection is byte-for-byte identical to Phase 1.
        # ----------------------------------------------------------
        if analyze_js:
            self._apply_js_bundles(parsed, url, detected, js_config)

        # ----------------------------------------------------------
        # JavaScript runtime intelligence (Phase 2B) -- opt-in stage.
        # Browser-free: reads globals, hydration payloads and embedded JSON
        # already present in the fetched HTML. Like the bundle stage it only
        # adds to what came before, and with analyze_runtime=False it is
        # skipped entirely, leaving Phase 1 behaviour byte-for-byte intact.
        # ----------------------------------------------------------
        if analyze_runtime:
            self._apply_runtime(parsed, url, detected, report, runtime_config)

        # ----------------------------------------------------------
        # API discovery (Phase 2C) -- opt-in stage.
        # Reads HTML/JS already present on the page for REST/GraphQL/
        # Swagger/RPC/WebSocket/SSE surface, independently of the runtime
        # stage above. Like the other opt-in stages it only adds to what
        # came before, and with analyze_api=False it is skipped entirely,
        # leaving Phase 1 behaviour byte-for-byte intact.
        # ----------------------------------------------------------
        if analyze_api:
            self._apply_api_discovery(parsed, url, headers, detected, report, api_config)

        # ----------------------------------------------------------
        # AI stack detection (Phase 2D) -- opt-in stage.
        # Reads HTML/JS/headers already present on the page for AI providers,
        # open-source models, local AI, frameworks, SDKs, vector databases,
        # embedding services and infrastructure, independently of the other
        # opt-in stages. Like them it only adds to what came before, and with
        # analyze_ai_stack=False it is skipped entirely, leaving Phase 1
        # behaviour byte-for-byte intact.
        # ----------------------------------------------------------
        if analyze_ai_stack:
            self._apply_ai_detection(parsed, url, headers, detected, report, ai_stack_config)

        for tech in detected.values():
             tech.evidence = sorted(set(tech.evidence))

        report.technologies = sorted(
            detected.values(),
            key=lambda t: (
                -t.confidence,
                t.category,
                t.name,
            ),
        )
        report.total_detected = len(report.technologies)
        report.elapsed = round(time.perf_counter() - start, 3)
        return report

    def _apply_js_bundles(self, parsed, url, detected, js_config):
        """Merge JavaScript-bundle detections into ``detected`` in place.

        Discovers, downloads and scans the page's JS bundles via
        :class:`technology.javascript.JSBundleAnalyzer`, then folds each
        result into the running detection map using the same "keep highest
        confidence, merge evidence, keep first version" rules the static
        pipeline uses. Never raises: any failure leaves ``detected`` untouched.
        """
        try:
            if self._js_analyzer is None:
                # Imported here so the dependency (and its requests.Session)
                # is only pulled in when the feature is actually used.
                from .javascript import JSBundleAnalyzer
                self._js_analyzer = JSBundleAnalyzer(
                    confidence=self.confidence, config=js_config)
            bundle_techs = self._js_analyzer.analyze(parsed, url)
        except Exception:  # noqa: BLE001  -- bundle intel must fail gracefully
            # Degrade gracefully but never silently: without this the whole
            # stage can fail permanently while every health signal (exit code,
            # tests, benchmark recall) stays green.
            logger.warning("JS bundle analysis failed for %s; continuing "
                           "without bundle intelligence", url, exc_info=True)
            return

        for tech in bundle_techs:
            self._merge_detection(detected, tech)

    def _apply_runtime(self, parsed, url, detected, report, runtime_config):
        """Merge runtime detections into ``detected`` and attach the report.

        Runs :class:`technology.runtime.RuntimeAnalyzer` over the page's
        runtime surface, folds any technologies it identifies into the running
        detection map with the same merge rules the other stages use, and
        stores the structured findings (hydration, API discovery, runtime
        config, env vars, state management, dynamic imports, PWA) on
        ``report.runtime``. Never raises: any failure leaves both the detection
        map and the report untouched.
        """
        try:
            if self._runtime_analyzer is None:
                # Imported here so the sub-system is only loaded when used.
                from .runtime import RuntimeAnalyzer
                self._runtime_analyzer = RuntimeAnalyzer(
                    confidence=self.confidence, config=runtime_config)
            analysis = self._runtime_analyzer.analyze(parsed, url)
        except Exception:  # noqa: BLE001 -- runtime intel must fail gracefully
            # See _apply_js_bundles: degrade gracefully, but leave a trace so a
            # permanently broken stage is distinguishable from a clean no-op.
            logger.warning("Runtime analysis failed for %s; continuing without "
                           "runtime intelligence", url, exc_info=True)
            return

        for tech in analysis.technologies:
            self._merge_detection(detected, tech)
        report.runtime = analysis.report.to_dict()

    def _apply_api_discovery(self, parsed, url, headers, detected, report, api_config):
        """Merge API discovery detections into ``detected`` and attach the report.

        Runs :class:`modules.api_discovery.ApiDiscoverer` over the page's
        HTML/JS surface, folds any technologies it identifies into the
        running detection map with the same merge rules the other stages
        use, and stores the structured findings (REST/JSON endpoints,
        GraphQL, Swagger/OpenAPI, RPC, WebSocket, SSE, plus reachability when
        probing was enabled) on ``report.api_discovery``. Never raises: any
        failure leaves both the detection map and the report untouched.
        """
        try:
            if self._api_discoverer is None:
                # Imported here so the sub-system is only loaded when used.
                from modules.api_discovery import ApiDiscoverer
                self._api_discoverer = ApiDiscoverer(
                    confidence=self.confidence, config=api_config)
            analysis = self._api_discoverer.analyze(parsed, url, headers)
        except Exception:  # noqa: BLE001 -- API discovery must fail gracefully
            # See _apply_js_bundles: degrade gracefully, but leave a trace so a
            # permanently broken stage is distinguishable from a clean no-op.
            logger.warning("API discovery failed for %s; continuing without "
                           "API discovery intelligence", url, exc_info=True)
            return

        for tech in analysis.technologies:
            self._merge_detection(detected, tech)
        report.api_discovery = analysis.report.to_dict()

    def _apply_ai_detection(self, parsed, url, headers, detected, report, ai_stack_config):
        """Merge AI-stack detections into ``detected`` and attach the report.

        Runs :class:`modules.ai_detection.AIStackDetector` over the page's
        HTML/JS/header surface, folds any technologies it identifies into the
        running detection map with the same merge rules the other stages
        use, and stores the structured findings (providers, open-source
        models, local AI, frameworks, SDKs, vector databases, embedding
        services, infrastructure) on ``report.ai_stack``. Never raises: any
        failure leaves both the detection map and the report untouched.
        """
        try:
            if self._ai_stack_detector is None:
                # Imported here so the sub-system is only loaded when used.
                from modules.ai_detection import AIStackDetector
                self._ai_stack_detector = AIStackDetector(
                    confidence=self.confidence, config=ai_stack_config)
            analysis = self._ai_stack_detector.analyze(parsed, url, headers)
        except Exception:  # noqa: BLE001 -- AI stack detection must fail gracefully
            # See _apply_js_bundles: degrade gracefully, but leave a trace so a
            # permanently broken stage is distinguishable from a clean no-op.
            logger.warning("AI stack detection failed for %s; continuing "
                           "without AI stack intelligence", url, exc_info=True)
            return

        for tech in analysis.technologies:
            self._merge_detection(detected, tech)
        report.ai_stack = analysis.report.to_dict()

    @staticmethod
    def _merge_detection(detected, tech):
        """Fold one technology into ``detected``: keep the highest confidence,
        the first known version, and the union of evidence.

        Shared by the opt-in stages so a detection means the same thing no
        matter which stage produced it.
        """
        existing = detected.get(tech.name)
        if existing is None:
            detected[tech.name] = tech
            return
        if tech.confidence > existing.confidence:
            existing.confidence = tech.confidence
        if existing.version is None and tech.version:
            existing.version = tech.version
        existing.evidence.extend(tech.evidence)
        existing.evidence = sorted(set(existing.evidence))

    def _collect_evidence(self, matches):
        evidence = []
        for source, result in matches.items():
            if result.matched:
                evidence.extend(f"{source}:{e}" for e in result.evidence)
        return evidence

    def _extract_version(self, matches):
        for result in matches.values():
            if not result.matched:
                continue
            for context in result.contexts:
                version = self.version.extract(context)
                if version:
                    return version
        return None
