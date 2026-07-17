"""
WebIntelPro Enterprise X
JavaScript Runtime Intelligence (Phase 2B) - Data Models

Value objects for the runtime intelligence sub-system.

Three groups live here:

* :class:`RuntimeConfig`  - every tunable limit for the stage. No module in
  this package may hardcode a bound; they all read it from here, so the whole
  feature can be tightened, loosened or effectively disabled from one place.
* :class:`RuntimeContext` / :class:`CodeUnit` / :class:`JSONBlob` - the raw
  material the extractor gathers from a page, each carrying the *location* it
  came from so every downstream finding can cite its origin.
* :class:`RuntimeFinding` / :class:`RuntimeReport` - the structured output.

Technology *detections* are deliberately NOT modelled here: they are emitted as
the project-wide :class:`technology.models.Technology` so runtime results merge
through exactly the same reporting path as every other detection source.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class FindingKind(str, Enum):
    """The bucket a :class:`RuntimeFinding` is reported under.

    Values are the JSON keys used by :meth:`RuntimeReport.to_dict`, so they are
    part of the module's output contract and should stay stable.
    """

    FRAMEWORK = "frameworks"
    HYDRATION = "hydration"
    API = "api"
    RUNTIME_CONFIG = "runtime_config"
    ENV_VAR = "env"
    STATE_MANAGEMENT = "state_management"
    DYNAMIC_IMPORT = "dynamic_imports"
    PWA = "pwa"
    GLOBAL = "globals"


class RuntimeSource(str, Enum):
    """Where a finding's evidence was observed.

    This is provenance for humans ("which part of the page said so"), distinct
    from the ConfidenceEngine *source key* used for scoring.
    """

    INLINE_SCRIPT = "inline_script"
    EMBEDDED_JSON = "embedded_json"
    HTML_MARKUP = "html"
    SCRIPT_URL = "script_url"
    BUNDLE = "bundle"


class HydrationStrategy(str, Enum):
    """How a page appears to get its markup and become interactive."""

    SSR = "ssr"
    CSR = "csr"
    SSG = "ssg"
    ISR = "isr"
    PARTIAL = "partial-hydration"
    STREAMING = "streaming-ssr"
    RESUMABILITY = "resumability"


class EndpointKind(str, Enum):
    """Classification of a discovered API endpoint."""

    REST = "rest"
    GRAPHQL = "graphql"
    WEBSOCKET = "websocket"
    SSE = "sse"
    JSON = "json"
    OPENAPI = "openapi"


@dataclass(slots=True)
class RuntimeConfig:
    """Tunable limits and switches for runtime analysis.

    Defaults are deliberately conservative and **network-free**: with
    ``analyze_bundles=False`` the stage only reads material already present in
    the fetched HTML, so enabling ``--runtime-analysis`` costs no extra
    requests. Memory is bounded by the byte caps, output by the count caps, and
    wall-clock by :attr:`time_budget_seconds`.
    """

    # ---- scan volume (memory bound) ----------------------------------
    # Number of inline <script> blocks scanned, largest-signal-first order.
    max_inline_scripts: int = 40
    # Per-unit scan cap: only the first N bytes of any single code unit are
    # examined. Runtime markers (globals, config, bootstraps) sit near the top.
    max_bytes_per_unit: int = 400_000
    # Cumulative cap across every unit scanned for one page.
    max_total_scan_bytes: int = 2_000_000
    # Cap on the raw document admitted for markup scanning and for the light
    # re-parse that recovers script id/type attributes.
    max_html_bytes: int = 3_000_000
    # Embedded JSON payloads (e.g. __NEXT_DATA__) above this size are not
    # json-parsed; they are still regex-scanned under the byte caps above.
    max_json_bytes: int = 1_000_000
    # Ceiling on nodes visited when walking a parsed JSON payload.
    max_json_nodes: int = 5_000
    # Quoted-string candidates considered per code unit during endpoint mining.
    max_strings_per_unit: int = 4_000
    # Longest string literal still considered as an endpoint candidate. Real
    # endpoints are short; longer literals are inlined data (base64, CSS, SVG)
    # and only cost time to classify.
    max_string_literal_length: int = 300

    # ---- output volume (report bound) --------------------------------
    max_findings_per_kind: int = 50
    max_evidence_per_finding: int = 5
    # Longest reported value (endpoint URL, env value, ...) before truncation.
    max_value_length: int = 200

    # ---- time bound ---------------------------------------------------
    # Wall-clock budget for one page's runtime analysis. Checked between units;
    # exceeding it stops further scanning and reports what was found so far.
    time_budget_seconds: float = 5.0

    # ---- behaviour -----------------------------------------------------
    # Minimum confidence for a runtime finding (and runtime-only technology) to
    # be reported. Mirrors TechnologyDetector.MIN_CONFIDENCE so all stages of
    # the pipeline share a single bar.
    min_confidence: float = 0.30
    # Replace values of environment variables whose *name* looks secret-bearing
    # with a redaction marker. The name is always reported; only the value is
    # masked. Leaving this on is strongly recommended: reports get shared.
    redact_secrets: bool = True
    # Opt-in: additionally scan downloaded bundle contents by reusing the
    # Phase 2A fetcher. Off by default, which keeps this stage network-free.
    analyze_bundles: bool = False
    # Bundles scanned when analyze_bundles is True (further capped by the
    # BundleConfig's own max_bundles).
    max_bundles: int = 6
    # Optional technology.javascript.BundleConfig; None uses that module's
    # defaults. Typed loosely to avoid importing the Phase 2A package unless
    # bundle analysis is actually requested.
    bundle_config: Optional[Any] = None


@dataclass(slots=True)
class Deadline:
    """A monotonic wall-clock budget shared across the analysis stages.

    Created once per page by the analyzer and consulted between units of work,
    so a pathological page degrades into fewer findings rather than a hang.
    """

    budget: float
    started: float = field(default_factory=time.perf_counter)

    @property
    def expired(self) -> bool:
        """True once the budget has been consumed."""
        return (time.perf_counter() - self.started) >= self.budget

    @property
    def elapsed(self) -> float:
        """Seconds spent since the deadline was created."""
        return round(time.perf_counter() - self.started, 3)


@dataclass(slots=True)
class CodeUnit:
    """A block of JavaScript-ish text to scan, plus where it came from.

    ``location`` is a human-readable provenance string (``inline_script[0]``,
    ``bundle:https://cdn/app.js``) echoed into every finding derived from it.
    """

    text: str
    location: str
    source: RuntimeSource


@dataclass(slots=True)
class JSONBlob:
    """An embedded JSON payload discovered in the document.

    ``data`` is the parsed structure when the payload was valid JSON and small
    enough to parse; it stays ``None`` otherwise, in which case only ``text``
    is available for regex scanning. Both paths are supported so a malformed or
    oversized payload degrades gracefully instead of being dropped.
    """

    text: str
    location: str
    identifier: str = ""
    data: Optional[Any] = None


@dataclass(slots=True)
class RuntimeContext:
    """Everything the extractor gathered for one page.

    This is the analyzer's working set: the units to scan, any embedded JSON,
    and the page-level facts (manifest link, script URLs) that some findings
    key off of.
    """

    base_url: str = ""
    units: List[CodeUnit] = field(default_factory=list)
    json_blobs: List[JSONBlob] = field(default_factory=list)
    script_urls: List[str] = field(default_factory=list)
    resource_hints: List[str] = field(default_factory=list)
    manifest: str = ""
    html: str = ""
    # Bytes actually admitted for scanning, after the config's caps.
    scanned_bytes: int = 0
    # True when a cap stopped extraction early; surfaced in the report so a
    # partial result is never mistaken for a complete one.
    truncated: bool = False


@dataclass(slots=True)
class RawSignal:
    """A syntactic hit produced by :mod:`technology.runtime.parser`.

    Intentionally meaning-free: the parser reports *what the text said*
    (an endpoint URL, an env name, an ``import()`` specifier) and leaves both
    interpretation and scoring to the detector/analyzer, which turn signals
    into :class:`RuntimeFinding` objects.
    """

    name: str
    value: Optional[str] = None
    evidence: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RuntimeFinding:
    """One piece of runtime intelligence.

    Every finding carries the four fields the Phase 2B contract requires:
    ``confidence`` (scored by the shared ConfidenceEngine), ``source``
    (provenance), ``evidence`` (the concrete tokens that matched) and
    ``location`` (which code unit they were seen in).
    """

    kind: FindingKind
    name: str
    confidence: float
    source: RuntimeSource
    location: str
    evidence: List[str] = field(default_factory=list)
    value: Optional[str] = None
    # Kind-specific extras (endpoint kind, hydration strategy, framework, ...).
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        payload = {
            "name": self.name,
            "confidence": self.confidence,
            "source": self.source.value,
            "location": self.location,
            "evidence": self.evidence,
        }
        if self.value is not None:
            payload["value"] = self.value
        if self.details:
            payload.update(self.details)
        return payload


@dataclass(slots=True)
class RuntimeReport:
    """Structured runtime findings for a single page.

    Findings are held in one flat list and grouped on demand by
    :meth:`to_dict`, which is what the detector attaches to
    :class:`technology.models.TechnologyReport`.
    """

    url: str = ""
    findings: List[RuntimeFinding] = field(default_factory=list)
    hydration_strategies: List[str] = field(default_factory=list)
    elapsed: float = 0.0
    truncated: bool = False
    errors: List[str] = field(default_factory=list)

    def add(self, finding: RuntimeFinding) -> None:
        self.findings.append(finding)

    def by_kind(self, kind: FindingKind) -> List[RuntimeFinding]:
        """Findings in one bucket, highest confidence first."""
        return [f for f in self.findings if f.kind is kind]

    def to_dict(self) -> dict:
        """Serialise to the Phase 2B output contract.

        Every :class:`FindingKind` gets a key (empty list when nothing was
        found) so consumers can rely on the shape without existence checks.
        """
        grouped: Dict[str, List[dict]] = {kind.value: [] for kind in FindingKind}
        for finding in self.findings:
            grouped[finding.kind.value].append(finding.to_dict())
        return {
            "url": self.url,
            "total_findings": len(self.findings),
            "hydration_strategies": self.hydration_strategies,
            "elapsed": self.elapsed,
            "truncated": self.truncated,
            "errors": self.errors,
            **grouped,
        }


@dataclass(slots=True)
class RuntimeAnalysis:
    """The analyzer's return value: detections plus the structured report.

    ``technologies`` are ordinary :class:`technology.models.Technology`
    objects, ready to merge into the detector's running detection map;
    ``report`` is the richer runtime-only intelligence that has no place in the
    flat technology list (endpoints, env vars, hydration, ...).
    """

    technologies: List[Any] = field(default_factory=list)
    report: RuntimeReport = field(default_factory=RuntimeReport)
