"""
WebIntelPro Enterprise X
JavaScript Runtime Intelligence (Phase 2B) - Analyzer (orchestrator)

The sub-system's single public entry point, used by
:class:`technology.detector.TechnologyDetector`:

    extract material  ->  scan units for signatures / hydration / endpoints /
        env / config / imports  ->  merge evidence  ->  score with the shared
            ConfidenceEngine  ->  emit Technology objects + a RuntimeReport

Design commitments
------------------
* **One scoring engine.** Every confidence in this package - technologies and
  findings alike - comes from :class:`technology.confidence.ConfidenceEngine`
  via the ``js_runtime`` source key. There is no second scorer.
* **One Technology model.** Detections are project-wide
  :class:`technology.models.Technology` objects, so they merge into the
  detector's map exactly like HTML/header/cookie detections.
* **Bounded.** Work stops at the config's byte, count and time budgets; a
  truncated run reports what it has and flags ``truncated``.
* **Never raises.** Per-unit failures are logged and skipped; a total failure
  yields an empty analysis, never an exception to the caller.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Tuple

from ..confidence import ConfidenceEngine
from ..models import Technology
from ..rules import RuleResult
from .detector import (
    CONFIG_GLOBALS,
    GENERIC_STATE_GLOBALS,
    HydrationInference,
    HydrationSignal,
    RuntimeSignatureScanner,
)
from .extractor import RuntimeExtractor
from .models import (
    Deadline,
    FindingKind,
    RawSignal,
    RuntimeAnalysis,
    RuntimeConfig,
    RuntimeFinding,
    RuntimeReport,
    RuntimeSource,
)
from .parser import RuntimeParser, present
from .utils import dedupe, looks_like_chunk, truncate

logger = logging.getLogger("webintelpro.runtime.analyzer")

# Source key under which runtime evidence is weighed. Registered in
# ConfidenceEngine.WEIGHTS alongside Phase 2A's "js_bundle". A runtime marker
# (an explicit `window.__NEXT_DATA__`, a `hydrateRoot(` call) is strong, direct
# evidence - the page is telling us what it runs - hence a weight in the same
# band as "scripts" and "js_bundle".
RUNTIME_SOURCE = "js_runtime"

# Findings mined from text, rather than asserted by a named global, are graded
# through the existing (weaker) "inline" weight: a URL-shaped string literal is
# real evidence, but it is an inference about intent, not a declaration.
RUNTIME_WEAK_SOURCE = "inline"

# Multiplier applied when a detected technology entails another (Next.js ->
# React). Mirrors TechnologyDetector's implication rule so a derived confidence
# means the same thing regardless of which stage produced it.
_IMPLICATION_FACTOR = 0.95


@dataclass(slots=True)
class _Observation:
    """A parser signal plus the provenance of where it was seen."""

    signal: RawSignal
    location: str
    source: RuntimeSource


class RuntimeAnalyzer:
    """Extracts runtime intelligence from a page without executing JavaScript.

    Reuses the caller's :class:`ConfidenceEngine` so runtime detections are
    scored on the same scale as every other source. Construction is cheap and
    network-free; with the default config :meth:`analyze` performs no I/O at
    all, reading only material already present in the fetched HTML.
    """

    def __init__(self, confidence: ConfidenceEngine | None = None,
                 config: RuntimeConfig | None = None):
        self.config = config or RuntimeConfig()
        self.confidence = confidence or ConfidenceEngine()
        self.extractor = RuntimeExtractor(self.config)
        self.scanner = RuntimeSignatureScanner(self.config)
        self.parser = RuntimeParser(self.config)
        self.hydration = HydrationInference(self.config)

    # ------------------------------------------------------------------
    def analyze(self, parsed, base_url: str = "") -> RuntimeAnalysis:
        """Analyse ``parsed``'s runtime surface and return detections + report.

        ``parsed`` is a :class:`technology.parser.ParsedHTML`; ``base_url`` is
        the page URL. Never raises.
        """
        report = RuntimeReport(url=base_url)
        deadline = Deadline(self.config.time_budget_seconds)
        try:
            ctx = self.extractor.extract(parsed, base_url)
        except Exception as exc:  # noqa: BLE001 - extraction must never crash a scan
            logger.debug("runtime extraction failed", exc_info=True)
            report.errors.append(f"extraction_failed:{type(exc).__name__}")
            return RuntimeAnalysis(technologies=[], report=report)

        report.truncated = ctx.truncated

        sig_results: Dict[str, RuleResult] = {}
        sig_meta: Dict[str, Tuple[str, RuntimeSource]] = {}
        globals_seen: Dict[str, _Observation] = {}
        hydration_signals: List[HydrationSignal] = []
        endpoints: Dict[str, _Observation] = {}
        env_vars: Dict[str, _Observation] = {}
        configs: Dict[str, _Observation] = {}
        imports: Dict[str, _Observation] = {}

        for unit in ctx.units:
            if deadline.expired:
                report.truncated = True
                logger.debug("time budget exhausted after %ss", deadline.elapsed)
                break
            try:
                self._scan_unit(unit, sig_results, sig_meta, globals_seen,
                                hydration_signals)
                # Endpoint/env/config/import mining is skipped for the markup
                # unit: page copy and link hrefs are not runtime intent, and
                # the same code is scanned anyway via the inline units.
                if unit.source is not RuntimeSource.HTML_MARKUP:
                    self._mine_unit(unit, endpoints, env_vars, configs, imports)
            except Exception:  # noqa: BLE001 - one bad unit must not sink the scan
                logger.debug("unit scan failed at %s", unit.location, exc_info=True)
                report.errors.append(f"unit_failed:{unit.location}")

        self._scan_json(ctx, endpoints, env_vars, hydration_signals, report)

        # ---- emit ------------------------------------------------------
        technologies = self._build_technologies(sig_results, sig_meta, report)
        self._emit_globals(globals_seen, report)
        self._emit_hydration(hydration_signals, report)
        self._emit_observations(endpoints, FindingKind.API, report, weak=True)
        self._emit_observations(env_vars, FindingKind.ENV_VAR, report, weak=True)
        self._emit_observations(configs, FindingKind.RUNTIME_CONFIG, report)
        self._emit_observations(imports, FindingKind.DYNAMIC_IMPORT, report,
                                weak=True)
        self._emit_module_graph(ctx, report)
        self._emit_manifest(ctx, report)

        # Deterministic order: strongest first within each bucket, ties broken
        # by name so repeated runs of the same page produce identical reports.
        report.findings.sort(key=lambda f: (f.kind.value, -f.confidence, f.name))
        report.elapsed = deadline.elapsed
        logger.debug("runtime analysis: %d technology(s), %d finding(s) in %ss",
                     len(technologies), len(report.findings), report.elapsed)
        return RuntimeAnalysis(technologies=technologies, report=report)

    # ------------------------------------------------------------------
    # Scanning
    # ------------------------------------------------------------------
    def _scan_unit(self, unit, sig_results, sig_meta, globals_seen,
                   hydration_signals) -> None:
        """Match signatures, globals and hydration markers in one unit."""
        for name, result in self.scanner.scan(unit.text).items():
            existing = sig_results.get(name)
            if existing is None:
                sig_results[name] = result
                sig_meta[name] = (unit.location, unit.source)
            else:
                existing.merge(result)
            sig = self.scanner.signature_for(name)
            for evidence in result.evidence:
                if evidence.startswith("window."):
                    self._note_global(globals_seen, evidence[len("window."):],
                                      unit, sig.technology if sig else "")

        # Payload globals that name no vendor: real hydration evidence, but the
        # honest reading is "a store is being rehydrated", not a product name.
        low = unit.text.lower()
        for name in GENERIC_STATE_GLOBALS:
            if not present(name, low):
                continue
            if self.parser.find_global(unit.text, name, allow_bare=True):
                self._note_global(globals_seen, name, unit, "")

        hydration_signals.extend(
            self.hydration.from_text(unit.text, unit.location, unit.source)
        )
        # Nuxt states its rendering mode inside a payload assigned in an
        # ordinary inline script, not in a JSON tag - so it is read here rather
        # than with the other embedded payloads.
        if unit.source is RuntimeSource.INLINE_SCRIPT:
            hydration_signals.extend(
                self.hydration.from_nuxt_payload(unit.text, unit.location,
                                                 unit.source)
            )

    @staticmethod
    def _note_global(globals_seen: Dict[str, _Observation], name: str, unit,
                     technology: str) -> None:
        """Record a global reference, keeping the first location it was seen."""
        if name in globals_seen:
            return
        globals_seen[name] = _Observation(
            signal=RawSignal(name=f"window.{name}",
                             evidence=[f"window.{name}"],
                             details={"technology": technology} if technology else {}),
            location=unit.location,
            source=unit.source,
        )

    def _mine_unit(self, unit, endpoints, env_vars, configs, imports) -> None:
        """Extract endpoints, env vars, config objects and imports from a unit."""
        for signal in self.parser.find_endpoints(unit.text):
            self._merge(endpoints, signal, unit)
        for signal in self.parser.find_env_vars(unit.text):
            self._merge(env_vars, signal, unit)
        for signal in self.parser.find_dynamic_imports(unit.text):
            self._merge(imports, signal, unit)
        low = unit.text.lower()
        for name, allow_bare in CONFIG_GLOBALS:
            if not present(name, low):
                continue
            signal = self.parser.find_config_object(unit.text, name, allow_bare)
            if signal is not None:
                self._merge(configs, signal, unit)

    def _scan_json(self, ctx, endpoints, env_vars, hydration_signals,
                   report: RuntimeReport) -> None:
        """Mine parsed embedded JSON payloads for endpoints, env and hydration.

        Framework payloads are authoritative about rendering mode, so they are
        consulted directly rather than inferred from markers.
        """
        for blob in ctx.json_blobs:
            try:
                if blob.data is not None:
                    for signal in self.parser.find_endpoints_in_json(blob.data):
                        self._merge_blob(endpoints, signal, blob)
                    for signal in self.parser.find_env_in_json(blob.data):
                        self._merge_blob(env_vars, signal, blob)
                    if "__NEXT_DATA__" in blob.identifier or "next" in blob.identifier.lower():
                        hydration_signals.extend(
                            self.hydration.from_next_data(blob.data, blob.location)
                        )
                hydration_signals.extend(
                    self.hydration.from_nuxt_payload(
                        blob.text, blob.location, RuntimeSource.EMBEDDED_JSON)
                )
            except Exception:  # noqa: BLE001 - a bad payload is not a failure
                logger.debug("json scan failed at %s", blob.location, exc_info=True)
                report.errors.append(f"json_failed:{blob.location}")

    @staticmethod
    def _merge(store: Dict[str, _Observation], signal: RawSignal, unit) -> None:
        existing = store.get(signal.name)
        if existing is None:
            store[signal.name] = _Observation(signal=signal, location=unit.location,
                                              source=unit.source)
            return
        for evidence in signal.evidence:
            if evidence not in existing.signal.evidence:
                existing.signal.evidence.append(evidence)
        if existing.signal.value is None and signal.value is not None:
            existing.signal.value = signal.value

    @staticmethod
    def _merge_blob(store: Dict[str, _Observation], signal: RawSignal, blob) -> None:
        existing = store.get(signal.name)
        if existing is None:
            store[signal.name] = _Observation(signal=signal, location=blob.location,
                                              source=RuntimeSource.EMBEDDED_JSON)
            return
        for evidence in signal.evidence:
            if evidence not in existing.signal.evidence:
                existing.signal.evidence.append(evidence)
        if existing.signal.value is None and signal.value is not None:
            existing.signal.value = signal.value

    # ------------------------------------------------------------------
    # Emission
    # ------------------------------------------------------------------
    def _score(self, result: RuleResult, weak: bool = False) -> float:
        """Score merged evidence through the shared ConfidenceEngine."""
        source = RUNTIME_WEAK_SOURCE if weak else RUNTIME_SOURCE
        return self.confidence.calculate({source: result})

    def _build_technologies(self, sig_results, sig_meta,
                            report: RuntimeReport) -> List[Technology]:
        """Turn matched signatures into Technology objects and findings.

        Capability signatures (no ``technology``) produce a finding only. Every
        technology row additionally produces a finding in its own bucket, so the
        structured report explains what the flat technology list asserts.
        """
        detections: Dict[str, Technology] = {}
        implications: Dict[str, Tuple[float, str]] = {}

        for name, result in sig_results.items():
            sig = self.scanner.signature_for(name)
            if sig is None:
                continue
            score = self._score(result)
            if score < self.config.min_confidence:
                continue
            location, source = sig_meta.get(name, ("", RuntimeSource.INLINE_SCRIPT))
            evidence = self._top_evidence(result)

            if sig.technology:
                details = {"category": sig.category}
                # Loader/mechanism rows: name the technology they evidence, so
                # "next chunk loader" is traceable back to Next.js.
                if sig.name != sig.technology:
                    details["technology"] = sig.technology
            else:
                details = {"capability": True}

            report.add(RuntimeFinding(
                kind=sig.kind, name=sig.name, confidence=score, source=source,
                location=location, evidence=evidence, details=details,
            ))

            if not sig.technology:
                continue

            existing = detections.get(sig.technology)
            if existing is None or score > existing.confidence:
                detections[sig.technology] = Technology(
                    name=sig.technology,
                    category=sig.category,
                    confidence=score,
                    version=None,
                    evidence=[f"{RUNTIME_SOURCE}:{e}" for e in evidence],
                )
            for implied in sig.implies:
                prev = implications.get(implied)
                if prev is None or score > prev[0]:
                    implications[implied] = (score, sig.technology)

        # A runtime detection can entail a technology that leaves no marker of
        # its own (Next.js bundles and hashes React's runtime away).
        for imp_name, (src_conf, src_name) in implications.items():
            if imp_name in detections:
                continue
            derived = max(
                round(min(src_conf, 0.95) * _IMPLICATION_FACTOR, 3),
                self.config.min_confidence,
            )
            sig = self.scanner.signature_for(imp_name)
            detections[imp_name] = Technology(
                name=imp_name,
                category=sig.category if sig else "javascript",
                confidence=derived,
                version=None,
                evidence=[f"implied:{src_name}"],
            )
        return list(detections.values())

    def _emit_globals(self, globals_seen: Dict[str, _Observation],
                      report: RuntimeReport) -> None:
        for obs in list(globals_seen.values())[: self.config.max_findings_per_kind]:
            result = RuleResult(matched=True, evidence=list(obs.signal.evidence))
            report.add(RuntimeFinding(
                kind=FindingKind.GLOBAL,
                name=obs.signal.name,
                confidence=self._score(result),
                source=obs.source,
                location=obs.location,
                evidence=obs.signal.evidence[: self.config.max_evidence_per_finding],
                details=dict(obs.signal.details),
            ))

    def _emit_hydration(self, signals: List[HydrationSignal],
                        report: RuntimeReport) -> None:
        """Reconcile hydration signals and emit one finding per strategy.

        Signals for the same strategy are merged (several markers agreeing is
        one conclusion with more evidence, not several conclusions).
        """
        merged: Dict[str, HydrationSignal] = {}
        for signal in self.hydration.reconcile(signals):
            key = f"{signal.strategy.value}:{signal.technology}"
            existing = merged.get(key)
            if existing is None:
                merged[key] = signal
                continue
            for evidence in signal.evidence:
                if evidence not in existing.evidence:
                    existing.evidence.append(evidence)

        strategies: List[str] = []
        for signal in list(merged.values())[: self.config.max_findings_per_kind]:
            result = RuleResult(matched=True, evidence=list(signal.evidence))
            score = self._score(result)
            if score < self.config.min_confidence:
                continue
            report.add(RuntimeFinding(
                kind=FindingKind.HYDRATION,
                name=signal.strategy.value,
                confidence=score,
                source=signal.source,
                location=signal.location,
                evidence=signal.evidence[: self.config.max_evidence_per_finding],
                details={"technology": signal.technology, "note": signal.note},
            ))
            if signal.strategy.value not in strategies:
                strategies.append(signal.strategy.value)
        report.hydration_strategies = strategies

    def _emit_module_graph(self, ctx, report: RuntimeReport) -> None:
        """Report preloaded and linked code-split chunks as import-graph edges.

        ``<link rel=modulepreload>`` hints and hashed ``<script src>`` chunks are
        the statically visible half of a bundler's import graph - the half that
        ``import()`` call sites in inline code cannot show, because the chunks
        they pull are named only inside the bundle.
        """
        budget = self.config.max_findings_per_kind
        for ref in dedupe(list(ctx.resource_hints) + list(ctx.script_urls)):
            if budget <= 0:
                break
            if not looks_like_chunk(ref):
                continue
            result = RuleResult(matched=True, evidence=[truncate(ref, 80)])
            score = self._score(result, weak=True)
            if score < self.config.min_confidence:
                continue
            budget -= 1
            report.add(RuntimeFinding(
                kind=FindingKind.DYNAMIC_IMPORT,
                name=truncate(ref, self.config.max_value_length),
                confidence=score,
                source=RuntimeSource.SCRIPT_URL,
                location="html",
                evidence=[truncate(ref, 80)],
                value=truncate(ref, self.config.max_value_length),
                details={"form": "preloaded-chunk"},
            ))

    def _emit_manifest(self, ctx, report: RuntimeReport) -> None:
        """Report a linked web app manifest as PWA runtime evidence."""
        if not ctx.manifest:
            return
        evidence = [f'rel="manifest" href="{truncate(ctx.manifest, 80)}"']
        report.add(RuntimeFinding(
            kind=FindingKind.PWA,
            name="Web App Manifest",
            confidence=self._score(RuleResult(matched=True, evidence=evidence)),
            source=RuntimeSource.HTML_MARKUP,
            location="html",
            evidence=evidence,
            value=truncate(ctx.manifest, self.config.max_value_length),
        ))

    def _emit_observations(self, store: Dict[str, _Observation],
                           kind: FindingKind, report: RuntimeReport,
                           weak: bool = False) -> None:
        """Emit mined observations (endpoints, env, config, imports) as findings."""
        for obs in list(store.values())[: self.config.max_findings_per_kind]:
            result = RuleResult(matched=True, evidence=list(obs.signal.evidence))
            score = self._score(result, weak=weak)
            if score < self.config.min_confidence:
                continue
            report.add(RuntimeFinding(
                kind=kind,
                name=obs.signal.name,
                confidence=score,
                source=obs.source,
                location=obs.location,
                evidence=obs.signal.evidence[: self.config.max_evidence_per_finding],
                value=obs.signal.value,
                details=dict(obs.signal.details),
            ))

    def _top_evidence(self, result: RuleResult) -> List[str]:
        """Distinct evidence for a finding, capped by config."""
        return sorted(set(result.evidence))[: self.config.max_evidence_per_finding]
