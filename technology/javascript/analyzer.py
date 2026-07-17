"""
WebIntelPro Enterprise X
JavaScript Bundle Intelligence - Analyzer (orchestrator)

Ties the sub-system together and is the single public entry point used by
:class:`technology.detector.TechnologyDetector`:

    discover bundle URLs  ->  download (budgeted)  ->  scan contents
        ->  aggregate evidence per technology  ->  score with the shared
            ConfidenceEngine  ->  emit Technology objects

The analyzer performs no network work of its own beyond delegating to
:class:`BundleFetcher`, holds no global state between calls, and never raises:
a failure to fetch or scan simply yields fewer detections.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from ..confidence import ConfidenceEngine
from ..models import Technology
from ..rules import RuleResult
from .detector import BundleScanner
from .extractor import VersionExtractor
from .fetcher import BundleFetcher
from .models import BundleConfig
from .parser import BundleDiscovery

logger = logging.getLogger("webintelpro.js.analyzer")

# Source key under which bundle evidence is weighed. Registered in
# ConfidenceEngine.WEIGHTS; a bundle's *contents* are strong, direct evidence
# (comparable to a script URL), hence a weight in the same band as "scripts".
BUNDLE_SOURCE = "js_bundle"

# Minimum confidence for a bundle-only detection to be emitted, mirroring
# TechnologyDetector.MIN_CONFIDENCE so both stages share one bar.
MIN_CONFIDENCE = 0.30


class JSBundleAnalyzer:
    """Discovers, downloads and analyses JavaScript bundles for a page.

    Reuses the caller's :class:`ConfidenceEngine` so bundle detections are
    scored on the same scale as HTML/header/cookie detections. Construction is
    cheap and network-free; all I/O happens inside :meth:`analyze`.
    """

    def __init__(self, confidence: ConfidenceEngine | None = None,
                 config: BundleConfig | None = None):
        self.config = config or BundleConfig()
        self.confidence = confidence or ConfidenceEngine()
        self.discovery = BundleDiscovery(self.config)
        self.scanner = BundleScanner()
        self.versions = VersionExtractor()
        self.fetcher = BundleFetcher(self.config)
        self._sig_by_name = {s["name"]: s for s in self.scanner.signatures}

    def analyze(self, parsed, base_url: str) -> List[Technology]:
        """Return technologies detected from ``parsed``'s JavaScript bundles.

        ``parsed`` is a :class:`technology.parser.ParsedHTML`; ``base_url`` is
        the page URL used to resolve relative bundle references.
        """
        urls = self.discovery.discover(parsed, base_url)
        if not urls:
            logger.debug("no bundle URLs to analyse for %s", base_url)
            return []

        self.fetcher.reset_budget()

        # name -> merged RuleResult across all bundles, plus the text we saw
        # it in first (used for version extraction).
        aggregated: Dict[str, RuleResult] = {}
        version_text: Dict[str, str] = {}

        scanned = 0
        for url in urls:
            bundle = self.fetcher.fetch(url)
            if not bundle.ok:
                logger.debug("skip %s (%s)", url, bundle.error or "empty")
                continue
            scanned += 1
            for name, result in self.scanner.scan(bundle.content).items():
                if name in aggregated:
                    aggregated[name].merge(result)
                else:
                    aggregated[name] = result
                    version_text[name] = bundle.content

        logger.debug("analysed %d/%d bundle(s), %d candidate tech(s)",
                     scanned, len(urls), len(aggregated))

        return self._build(aggregated, version_text)

    # ------------------------------------------------------------------
    def _build(self, aggregated: Dict[str, RuleResult],
               version_text: Dict[str, str]) -> List[Technology]:
        detections: Dict[str, Technology] = {}
        implications: Dict[str, tuple] = {}

        for name, result in aggregated.items():
            score = self.confidence.calculate({BUNDLE_SOURCE: result})
            if score < MIN_CONFIDENCE:
                continue

            sig = self._sig_by_name.get(name, {})
            tech = Technology(
                name=name,
                category=sig.get("category", "javascript"),
                confidence=score,
                version=self._version(name, sig, version_text.get(name, "")),
                evidence=[f"{BUNDLE_SOURCE}:{e}" for e in sorted(set(result.evidence))],
            )
            detections[name] = tech

            for implied in sig.get("implies", []):
                prev = implications.get(implied)
                if prev is None or score > prev[0]:
                    implications[implied] = (score, name)

        # A bundle detection can entail another tech that leaves no direct
        # marker (Next.js -> React). Mirror the detector's derived-confidence
        # rule so implied techs are consistent regardless of stage.
        for imp_name, (src_conf, src_name) in implications.items():
            if imp_name in detections:
                continue
            derived = max(round(min(src_conf, 0.95) * 0.95, 3), MIN_CONFIDENCE)
            sig = self._sig_by_name.get(imp_name, {})
            detections[imp_name] = Technology(
                name=imp_name,
                category=sig.get("category", "javascript"),
                confidence=derived,
                version=None,
                evidence=[f"implied:{src_name}"],
            )

        return list(detections.values())

    def _version(self, name: str, sig: dict, text: str) -> Optional[str]:
        version = self.versions.extract(sig.get("version_anchors", []), text)
        if version:
            return version
        return self.versions.banner_version(name, text)
