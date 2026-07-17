"""
WebIntelPro Enterprise X
AI Stack Detection (Phase 2D) - Detector (orchestrator)

The sub-system's single public entry point, used by
:class:`technology.detector.TechnologyDetector`:

    extract material (html / inline scripts / script+resource-hint URLs)
        -> match each of the fixed signature tables (providers, open-source
           models, local AI, frameworks, SDKs, vector databases, embedding
           services, infrastructure) against every unit, plus response
           header *names* -> score with the shared ConfidenceEngine ->
               emit Technology objects + an AIDetectionReport

Design commitments (mirroring :mod:`modules.api_discovery.discoverer`):

* **One scoring engine.** Every confidence in this package comes from
  :class:`technology.confidence.ConfidenceEngine` via the ``ai_evidence``
  (text-mined) and ``headers`` (response header name) source keys -- the
  latter is the project's existing "headers" weight, reused as-is because a
  matched header name *is* the same kind of evidence the core engine already
  scores that way.
* **One Technology model.** Detections are project-wide
  :class:`technology.models.Technology` objects, so they merge into the
  detector's map exactly like every other detection source.
* **Network-free, always.** Unlike API discovery this stage has no probing
  mode at all: nothing here ever performs I/O.
* **Never raises.** Per-unit and per-stage failures are logged and skipped; a
  total failure yields an empty analysis, never an exception to the caller.
* **Precision over recall.** Every signature pattern is a brand-, host- or
  package-specific token (see providers.py/frameworks.py/etc. module
  docstrings); nothing here infers a technology from a bare dictionary word.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from technology.confidence import ConfidenceEngine
from technology.models import Technology
from technology.rules import RuleEngine, RuleResult
from technology.version import VersionEngine

from .embeddings import AI_INFRASTRUCTURE, EMBEDDING_SERVICES
from .frameworks import FRAMEWORKS, SDKS
from .models import (
    AICategory,
    AIDetectionAnalysis,
    AIDetectionConfig,
    AIDetectionReport,
    AIFinding,
    Deadline,
    DiscoverySource,
    Signature,
)
from .providers import LOCAL_AI, OPEN_SOURCE_MODELS, PROVIDERS
from .utils import clamp, dedupe
from .vector_db import VECTOR_DATABASES

logger = logging.getLogger("webintelpro.ai_detection.detector")

# Source key for text-mined evidence (HTML/JS). Registered in
# ConfidenceEngine.WEIGHTS alongside Phase 2A/2B/2C's "js_bundle"/"js_runtime"/
# "api_evidence". Header-name evidence reuses the engine's existing "headers"
# key instead of a new one, since it is literally the same kind of signal.
AI_EVIDENCE_SOURCE = "ai_evidence"

ALL_SIGNATURES: Tuple[Signature, ...] = (
    PROVIDERS + OPEN_SOURCE_MODELS + LOCAL_AI
    + FRAMEWORKS + SDKS
    + VECTOR_DATABASES
    + EMBEDDING_SERVICES + AI_INFRASTRUCTURE
)


@dataclass(slots=True)
class _Observation:
    """Accumulated evidence for one named signature across every unit scanned."""

    signature: Signature
    text_evidence: List[str] = field(default_factory=list)
    text_contexts: List[str] = field(default_factory=list)
    header_evidence: List[str] = field(default_factory=list)
    sources: set = field(default_factory=set)


class AIStackDetector:
    """Detects AI providers, open-source models, local AI, frameworks, SDKs,
    vector databases, embedding services and AI infrastructure.

    Passive-only: reads material already present in the fetched HTML/JS plus
    response headers already fetched for the page. Reuses the caller's
    :class:`ConfidenceEngine` so AI-stack findings are scored on the same
    scale as every other detection source. Construction is cheap and
    network-free.
    """

    def __init__(self, confidence: ConfidenceEngine | None = None,
                 config: AIDetectionConfig | None = None):
        self.config = config or AIDetectionConfig()
        self.confidence = confidence or ConfidenceEngine()
        self.engine = RuleEngine()
        self.version = VersionEngine()

    # ------------------------------------------------------------------
    def analyze(self, parsed, base_url: str = "",
               headers: Dict[str, str] | None = None) -> AIDetectionAnalysis:
        """Detect ``parsed``'s AI stack and return detections + report.

        ``parsed`` is a :class:`technology.parser.ParsedHTML`; ``base_url`` is
        the page URL (carried for report identity only -- never fetched
        again); ``headers`` are the response headers already fetched for the
        page. Never raises.
        """
        report = AIDetectionReport(url=base_url)
        deadline = Deadline(self.config.time_budget_seconds)

        try:
            units, truncated = self._extract_units(parsed)
        except Exception as exc:  # noqa: BLE001 - extraction must never crash a scan
            logger.debug("ai detection extraction failed", exc_info=True)
            report.errors.append(f"extraction_failed:{type(exc).__name__}")
            return AIDetectionAnalysis(technologies=[], report=report)
        report.truncated = truncated

        observations: Dict[str, _Observation] = {}

        for text, location in units:
            if deadline.expired:
                report.truncated = True
                logger.debug("time budget exhausted after %ss", deadline.elapsed)
                break
            try:
                self._scan_unit(text, location, observations)
            except Exception:  # noqa: BLE001 - one bad unit must not sink the scan
                logger.debug("unit scan failed at %s", location, exc_info=True)
                report.errors.append(f"unit_failed:{location}")

        try:
            self._scan_headers(headers or {}, observations)
        except Exception:  # noqa: BLE001 - header scan must not sink the scan
            logger.debug("header scan failed", exc_info=True)
            report.errors.append("header_scan_failed")

        tech_by_name: Dict[str, Technology] = {}
        self._emit(observations, report, tech_by_name)

        report.findings.sort(key=lambda f: (f.category.value, -f.confidence, f.name))
        report.elapsed = deadline.elapsed
        logger.debug("ai detection: %d technology(s), %d finding(s) in %ss",
                     len(tech_by_name), len(report.findings), report.elapsed)
        return AIDetectionAnalysis(technologies=list(tech_by_name.values()), report=report)

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------
    def _extract_units(self, parsed) -> Tuple[List[Tuple[str, str]], bool]:
        """Return bounded ``(text, location)`` units to scan from ``parsed``.

        Reads only fields :class:`technology.parser.ParsedHTML` already
        exposes -- no re-parse, no I/O. Mirrors
        :meth:`modules.api_discovery.discoverer.ApiDiscoverer._extract_units`.
        """
        config = self.config
        units: List[Tuple[str, str]] = []
        truncated = False
        budget = config.max_total_scan_bytes

        scripts = list(getattr(parsed, "scripts", []) or [])
        hints = list(getattr(parsed, "resource_hints", []) or [])
        if scripts or hints:
            joined = clamp(" ".join(dedupe(scripts + hints)),
                           min(config.max_bytes_per_unit, budget))
            if joined:
                budget -= len(joined)
                units.append((joined, "script_urls"))

        inline = list(getattr(parsed, "inline_scripts", []) or [])[: config.max_inline_scripts]
        for index, body in enumerate(inline):
            if budget <= 0:
                truncated = True
                break
            if not body or not body.strip():
                continue
            text = clamp(body, min(config.max_bytes_per_unit, budget))
            if len(text) < len(body):
                truncated = True
            budget -= len(text)
            units.append((text, f"inline_script[{index}]"))

        html = clamp(getattr(parsed, "html", "") or "", config.max_html_bytes)
        if html and budget > 0:
            markup = clamp(html, budget)
            if len(markup) < len(html):
                truncated = True
            budget -= len(markup)
            units.append((markup, "html"))
        elif html:
            truncated = True

        return units, truncated

    # ------------------------------------------------------------------
    # Scanning
    # ------------------------------------------------------------------
    def _scan_unit(self, text: str, location: str, observations: Dict[str, _Observation]) -> None:
        """Match every signature's ``patterns`` against one unit of text."""
        if not text:
            return
        low = text.lower()
        source = self._source_for(location)
        for signature in ALL_SIGNATURES:
            if not signature.patterns:
                continue
            candidates = [p for p in signature.patterns if p.lower() in low]
            if not candidates:
                continue
            result: RuleResult = self.engine.match(candidates, low)
            if not result.matched:
                continue
            obs = observations.setdefault(signature.name, _Observation(signature=signature))
            for evidence in result.evidence:
                if evidence not in obs.text_evidence:
                    obs.text_evidence.append(evidence)
            obs.text_contexts.extend(result.contexts)
            obs.sources.add(source.value)

    def _scan_headers(self, headers: Dict[str, str], observations: Dict[str, _Observation]) -> None:
        """Match every signature's ``headers`` against response header *names*.

        Header values are never inspected -- only the names the server chose
        to send -- so this cannot leak credential-bearing header content.
        """
        if not headers:
            return
        names = list(headers.keys())
        low_names = [n.lower() for n in names]
        for signature in ALL_SIGNATURES:
            if not signature.headers:
                continue
            matched_names = [
                names[i] for i, low in enumerate(low_names)
                if any(hint in low for hint in signature.headers)
            ]
            if not matched_names:
                continue
            obs = observations.setdefault(signature.name, _Observation(signature=signature))
            for name in matched_names:
                if name not in obs.header_evidence:
                    obs.header_evidence.append(name)
            obs.sources.add(DiscoverySource.HEADER.value)

    @staticmethod
    def _source_for(location: str) -> DiscoverySource:
        if location == "html":
            return DiscoverySource.HTML_MARKUP
        if location == "script_urls":
            return DiscoverySource.SCRIPT_URL
        return DiscoverySource.INLINE_SCRIPT

    # ------------------------------------------------------------------
    # Emission
    # ------------------------------------------------------------------
    def _emit(self, observations: Dict[str, _Observation], report: AIDetectionReport,
             tech_by_name: Dict[str, Technology]) -> None:
        for obs in list(observations.values())[: self.config.max_findings_per_category
                                                  * len(AICategory)]:
            matches: Dict[str, RuleResult] = {}
            if obs.text_evidence:
                matches[AI_EVIDENCE_SOURCE] = RuleResult(matched=True, evidence=obs.text_evidence)
            if obs.header_evidence:
                matches["headers"] = RuleResult(matched=True, evidence=obs.header_evidence)
            if not matches:
                continue
            score = self.confidence.calculate(matches)
            if score < self.config.min_confidence:
                continue

            version = None
            for context in obs.text_contexts:
                version = self.version.extract(context)
                if version:
                    break

            evidence = obs.text_evidence + obs.header_evidence
            report.add(AIFinding(
                category=obs.signature.category, name=obs.signature.name,
                confidence=score, sources=sorted(obs.sources),
                evidence=evidence[: self.config.max_evidence_per_finding],
                version=version,
            ))
            tech_by_name[obs.signature.name] = Technology(
                name=obs.signature.name, category=f"ai_{obs.signature.category.value}",
                confidence=score, version=version,
                evidence=[f"{AI_EVIDENCE_SOURCE}:{e}" for e in evidence],
            )
