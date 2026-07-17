"""
WebIntelPro Enterprise X
API Discovery (Phase 2C) - Discoverer (orchestrator)

The sub-system's single public entry point, used by
:class:`technology.detector.TechnologyDetector`:

    extract material  ->  mine candidate endpoint strings + client-library
        signatures  ->  (optional) probe a small fixed set of well-known
            paths for reachability  ->  score with the shared
                ConfidenceEngine  ->  emit Technology objects + an
                    ApiDiscoveryReport

Design commitments
-------------------
* **One scoring engine.** Every confidence in this package comes from
  :class:`technology.confidence.ConfidenceEngine` via the ``api_evidence``
  (text-mined) and ``api_probe`` (live-confirmed) source keys. Text evidence
  and a live probe for the same endpoint are combined in a single
  ``calculate()`` call, so corroboration compounds exactly the way it does
  for every other multi-source detection in the project.
* **One Technology model.** Detections are project-wide
  :class:`technology.models.Technology` objects, so they merge into the
  detector's map exactly like HTML/header/cookie/runtime detections.
* **Network-free by default.** ``ApiDiscoveryConfig.probe_reachability`` is
  off unless the caller explicitly asks for it; the passive path performs no
  I/O at all.
* **Conservative when probing.** A small, fixed candidate list -- never a
  wordlist, never brute force -- one HEAD/GET per URL, robots.txt-gated,
  bounded by count and wall-clock budgets.
* **Never raises.** Per-unit and per-stage failures are logged and skipped; a
  total failure yields an empty analysis, never an exception to the caller.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from technology.confidence import ConfidenceEngine
from technology.models import Technology
from technology.rules import RuleEngine, RuleResult

from . import endpoints, graphql, swagger
from . import websocket as ws
from .models import (
    ApiDiscoveryAnalysis,
    ApiDiscoveryConfig,
    ApiDiscoveryReport,
    ApiFinding,
    ApiKind,
    Candidate,
    Deadline,
    DiscoverySource,
    ProbeResult,
    RawSignal,
)
from .utils import ReachabilityProber, clamp, dedupe, resolve_candidates, truncate

logger = logging.getLogger("webintelpro.api_discovery.discoverer")

# Source key for text-mined evidence (JS/HTML). Registered in
# ConfidenceEngine.WEIGHTS alongside Phase 2A/2B's "js_bundle"/"js_runtime".
API_EVIDENCE_SOURCE = "api_evidence"

# Source key for live-confirmed reachability. Weighed higher than text
# evidence: a 2xx/401/403 response (or a validated Swagger/OpenAPI document
# shape) is direct proof the resource exists, not an inference about intent.
API_PROBE_SOURCE = "api_probe"

_KIND_TECHNOLOGY_NAMES: Dict[ApiKind, str] = {
    ApiKind.REST: "REST API",
    ApiKind.GRAPHQL: "GraphQL API",
    ApiKind.OPENAPI: "Swagger / OpenAPI",
    ApiKind.WEBSOCKET: "WebSocket API",
    ApiKind.SSE: "Server-Sent Events",
    ApiKind.JSON: "JSON API",
    ApiKind.JSONRPC: "JSON-RPC",
    ApiKind.XMLRPC: "XML-RPC",
    ApiKind.TRPC: "tRPC",
    ApiKind.GRPC_WEB: "gRPC-Web",
}


@dataclass(slots=True)
class _Observation:
    """A signal plus the provenance of where it was seen, and any probe result."""

    signal: RawSignal
    location: str
    source: DiscoverySource
    probe: Optional[ProbeResult] = None


def _resolve_same_origin(base_url: str, value: str) -> Optional[str]:
    """Resolve ``value`` against ``base_url``, or ``None`` if off-origin.

    Probing never follows a discovered string to a third-party host (an
    analytics or payment-provider endpoint mined from JS, say) -- only the
    page's own origin is checked, keeping probing scoped to the site being
    analysed.
    """
    if not base_url or not value:
        return None
    try:
        resolved = urljoin(base_url, value)
        if not resolved.startswith(("http://", "https://")):
            return None
        if urlparse(resolved).netloc != urlparse(base_url).netloc:
            return None
        return resolved
    except Exception:  # noqa: BLE001 - a malformed URL is simply not probed
        return None


class ApiDiscoverer:
    """Discovers REST, GraphQL, OpenAPI, RPC, WebSocket and SSE surfaces.

    Passive by default: reads only material already present in the fetched
    HTML/JS. With ``config.probe_reachability=True`` it additionally checks a
    small, fixed set of well-known paths (and, optionally, endpoints already
    mined from the page) for reachability. Reuses the caller's
    :class:`ConfidenceEngine` so API findings are scored on the same scale as
    every other detection source. Construction is cheap and network-free.
    """

    def __init__(self, confidence: ConfidenceEngine | None = None,
                 config: ApiDiscoveryConfig | None = None):
        self.config = config or ApiDiscoveryConfig()
        self.confidence = confidence or ConfidenceEngine()
        self.engine = RuleEngine()

    # ------------------------------------------------------------------
    def analyze(self, parsed, base_url: str = "",
               headers: Dict[str, str] | None = None) -> ApiDiscoveryAnalysis:
        """Discover ``parsed``'s API surface and return detections + report.

        ``parsed`` is a :class:`technology.parser.ParsedHTML`; ``base_url`` is
        the page URL; ``headers`` are the response headers already fetched for
        the page (no request is made to obtain them). Never raises.
        """
        report = ApiDiscoveryReport(url=base_url)
        deadline = Deadline(self.config.time_budget_seconds)

        try:
            units, truncated = self._extract_units(parsed)
        except Exception as exc:  # noqa: BLE001 - extraction must never crash a scan
            logger.debug("api discovery extraction failed", exc_info=True)
            report.errors.append(f"extraction_failed:{type(exc).__name__}")
            return ApiDiscoveryAnalysis(technologies=[], report=report)
        report.truncated = truncated

        discovered: Dict[str, _Observation] = {}
        signatures: Dict[str, _Observation] = {}

        for text, location in units:
            if deadline.expired:
                report.truncated = True
                logger.debug("time budget exhausted after %ss", deadline.elapsed)
                break
            try:
                self._scan_unit(text, location, discovered, signatures)
            except Exception:  # noqa: BLE001 - one bad unit must not sink the scan
                logger.debug("unit scan failed at %s", location, exc_info=True)
                report.errors.append(f"unit_failed:{location}")

        for signal in graphql.scan_headers(headers or {}):
            self._merge(signatures, signal, "headers", DiscoverySource.HEADER)

        known_candidates: Dict[str, Candidate] = {}
        probe_results: Dict[str, ProbeResult] = {}
        if self.config.probe_reachability:
            try:
                known_candidates, probe_results = self._probe(base_url, discovered, report)
            except Exception:  # noqa: BLE001 - probing is best-effort
                logger.debug("reachability probing failed", exc_info=True)
                report.errors.append("probing_failed")

        tech_by_name: Dict[str, Technology] = {}
        self._emit_signatures(signatures, report, tech_by_name)
        self._emit_discovered(discovered, report, tech_by_name)
        self._emit_well_known(known_candidates, probe_results, report, tech_by_name)

        report.findings.sort(key=lambda f: (f.kind.value, -f.confidence, f.name))
        report.elapsed = deadline.elapsed
        logger.debug("api discovery: %d technology(s), %d finding(s) in %ss",
                     len(tech_by_name), len(report.findings), report.elapsed)
        return ApiDiscoveryAnalysis(technologies=list(tech_by_name.values()), report=report)

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------
    def _extract_units(self, parsed) -> Tuple[List[Tuple[str, str]], bool]:
        """Return bounded ``(text, location)`` units to scan from ``parsed``.

        Reads only fields :class:`technology.parser.ParsedHTML` already
        exposes -- no re-parse, no I/O. Script src URLs and resource hints
        are joined into one short unit so library markers in a URL
        (``socket.io.js``) are still caught, without treating every asset URL
        as its own scan unit.
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
    def _scan_unit(self, text: str, location: str, discovered, signatures) -> None:
        """Mine candidate endpoint strings and client-library markers from one unit.

        Endpoint/constructor mining is skipped for the ``html`` and
        ``script_urls`` units: markup attributes and asset URLs are not API
        call sites, and scanning them classifies ordinary asset paths (a
        ``socket.io.js`` script src, a stylesheet href) as endpoints. Mirrors
        the same exclusion :class:`technology.runtime.analyzer.RuntimeAnalyzer`
        applies to its markup unit. Client-library signature scanning still
        runs over every unit, since a marker legitimately appears in markup
        (``<redoc spec-url=`` ) or an asset filename (``socket.io.js``).
        """
        source = self._source_for(location)

        if location not in ("html", "script_urls"):
            # Constructor calls self-classify and must claim their literal's
            # dict slot *before* the generic classify chain reaches the same
            # string -- new EventSource("/api/x") is SSE even though "/api/x"
            # shape-classifies as REST, and _merge() never overwrites an
            # existing entry's kind, only its evidence.
            for signal in ws.scan_constructors(text, self.config.max_findings_per_kind):
                self._merge(discovered, signal, location, source)

            for value, evidence, call_hint in endpoints.find_candidate_strings(
                    text, self.config.max_strings_per_unit,
                    self.config.max_string_literal_length):
                kind = (ws.classify(value) or graphql.classify(value)
                       or swagger.classify(value) or endpoints.classify(value))
                if kind is None:
                    continue
                details = {"call": call_hint} if call_hint else {}
                value_out = truncate(value, self.config.max_value_length)
                if not value_out:
                    continue
                signal = RawSignal(name=value_out, kind=kind, value=value_out,
                                   evidence=[evidence], details=details)
                self._merge(discovered, signal, location, source)

        for scanner in (graphql.scan_signatures, swagger.scan_signatures,
                        ws.scan_signatures, endpoints.scan_signatures):
            for signal in scanner(text, self.engine):
                self._merge(signatures, signal, location, source)

    @staticmethod
    def _source_for(location: str) -> DiscoverySource:
        if location == "html":
            return DiscoverySource.HTML_MARKUP
        if location == "script_urls":
            return DiscoverySource.SCRIPT_URL
        return DiscoverySource.INLINE_SCRIPT

    @staticmethod
    def _merge(store: Dict[str, _Observation], signal: RawSignal, location: str,
              source: DiscoverySource) -> None:
        existing = store.get(signal.name)
        if existing is None:
            store[signal.name] = _Observation(signal=signal, location=location,
                                              source=source)
            return
        for evidence in signal.evidence:
            if evidence not in existing.signal.evidence:
                existing.signal.evidence.append(evidence)
        if existing.signal.value is None and signal.value is not None:
            existing.signal.value = signal.value

    # ------------------------------------------------------------------
    # Reachability probing (opt-in)
    # ------------------------------------------------------------------
    def _probe(self, base_url: str, discovered: Dict[str, _Observation],
              report: ApiDiscoveryReport
              ) -> Tuple[Dict[str, Candidate], Dict[str, ProbeResult]]:
        """Probe well-known paths and, optionally, discovered endpoints.

        Returns the resolved well-known candidate map and every probe result,
        and additionally attaches a matching :class:`ProbeResult` onto each
        discovered-endpoint :class:`_Observation` in place, so text evidence
        and live confirmation can be scored together for that endpoint.
        """
        known = resolve_candidates(
            base_url,
            list(endpoints.REST_CANDIDATES) + list(graphql.GRAPHQL_CANDIDATES)
            + list(swagger.SWAGGER_CANDIDATES),
        )

        value_by_resolved: Dict[str, str] = {}
        if self.config.probe_discovered_endpoints:
            for value in list(discovered.keys()):
                resolved = _resolve_same_origin(base_url, value)
                if resolved and resolved not in known:
                    value_by_resolved[resolved] = value

        probe_urls = dedupe(list(known.keys()) + list(value_by_resolved.keys()))
        if not probe_urls:
            return known, {}

        prober = ReachabilityProber(self.config)
        results = prober.probe_many(probe_urls)
        report.probed = True

        for url, probe in results.items():
            candidate = known.get(url)
            if probe.reachable and candidate is not None and candidate.kind is ApiKind.OPENAPI:
                body = prober.sniff_body(url)
                probe.confirmed = swagger.looks_like_openapi_doc(body)
            value = value_by_resolved.get(url)
            if value is not None and value in discovered:
                discovered[value].probe = probe

        return known, results

    # ------------------------------------------------------------------
    # Emission
    # ------------------------------------------------------------------
    def _emit_signatures(self, signatures: Dict[str, _Observation],
                         report: ApiDiscoveryReport,
                         tech_by_name: Dict[str, Technology]) -> None:
        for obs in list(signatures.values())[: self.config.max_findings_per_kind]:
            result = RuleResult(matched=True, evidence=list(obs.signal.evidence))
            score = self.confidence.calculate({API_EVIDENCE_SOURCE: result})
            if score < self.config.min_confidence:
                continue
            report.add(ApiFinding(
                kind=obs.signal.kind, name=obs.signal.name, confidence=score,
                source=obs.source, location=obs.location,
                evidence=obs.signal.evidence[: self.config.max_evidence_per_finding],
                details=dict(obs.signal.details),
            ))
            # A named client-library signature (Apollo, Socket.IO, tRPC, ...)
            # is evidence *for* its API kind, so both are reported: the
            # specific library, and the general surface it implies.
            technology_name = obs.signal.details.get("technology")
            if technology_name:
                self._add_named_technology(tech_by_name, technology_name,
                                           obs.signal.kind, score)
            self._add_kind_technology(tech_by_name, obs.signal.kind, score)

    def _emit_discovered(self, discovered: Dict[str, _Observation],
                         report: ApiDiscoveryReport,
                         tech_by_name: Dict[str, Technology]) -> None:
        for obs in list(discovered.values())[: self.config.max_findings_per_kind]:
            matches = {API_EVIDENCE_SOURCE: RuleResult(matched=True,
                                                        evidence=list(obs.signal.evidence))}
            reachable = None
            http_status = None
            if obs.probe is not None:
                reachable = obs.probe.reachable
                http_status = obs.probe.status
                if obs.probe.reachable:
                    probe_evidence = [f"probe:{obs.probe.status}"]
                    if obs.probe.confirmed:
                        probe_evidence.append("doc-shape:confirmed")
                    matches[API_PROBE_SOURCE] = RuleResult(matched=True,
                                                            evidence=probe_evidence)
            score = self.confidence.calculate(matches)
            if score < self.config.min_confidence:
                continue
            report.add(ApiFinding(
                kind=obs.signal.kind, name=obs.signal.name, confidence=score,
                source=obs.source, location=obs.location,
                evidence=obs.signal.evidence[: self.config.max_evidence_per_finding],
                value=obs.signal.value, reachable=reachable, http_status=http_status,
                details=dict(obs.signal.details),
            ))
            self._add_kind_technology(tech_by_name, obs.signal.kind, score)

    def _emit_well_known(self, known: Dict[str, Candidate],
                         probe_results: Dict[str, ProbeResult],
                         report: ApiDiscoveryReport,
                         tech_by_name: Dict[str, Technology]) -> None:
        """Emit findings for reachable well-known paths that had no prior
        text evidence -- many sites expose ``/swagger.json`` without ever
        referencing it from JavaScript."""
        for url, candidate in known.items():
            probe = probe_results.get(url)
            if probe is None or not probe.reachable:
                continue
            evidence = [f"probe:{probe.status}"]
            if probe.confirmed:
                evidence.append("doc-shape:confirmed")
            score = self.confidence.calculate(
                {API_PROBE_SOURCE: RuleResult(matched=True, evidence=evidence)})
            if score < self.config.min_confidence:
                continue
            details = {"path": candidate.path}
            if probe.confirmed:
                details["confirmed"] = True
            report.add(ApiFinding(
                kind=candidate.kind, name=candidate.label or candidate.path,
                confidence=score, source=DiscoverySource.WELL_KNOWN_PATH,
                location="well_known", evidence=evidence, value=url,
                reachable=True, http_status=probe.status, details=details,
            ))
            self._add_kind_technology(tech_by_name, candidate.kind, score)

    def _add_kind_technology(self, tech_by_name: Dict[str, Technology],
                             kind: ApiKind, score: float) -> None:
        self._add_named_technology(tech_by_name, _KIND_TECHNOLOGY_NAMES.get(kind, kind.value),
                                   kind, score)

    @staticmethod
    def _add_named_technology(tech_by_name: Dict[str, Technology], name: str,
                              kind: ApiKind, score: float) -> None:
        existing = tech_by_name.get(name)
        if existing is None:
            tech_by_name[name] = Technology(
                name=name, category="api", confidence=score, version=None,
                evidence=[f"{API_EVIDENCE_SOURCE}:{kind.value}"],
            )
        elif score > existing.confidence:
            existing.confidence = score
