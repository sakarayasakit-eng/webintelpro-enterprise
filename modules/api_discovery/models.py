"""
WebIntelPro Enterprise X
API Discovery (Phase 2C) - Data Models

Value objects for the API discovery sub-system, mirroring the shape of
:mod:`technology.runtime.models`:

* :class:`ApiDiscoveryConfig` - every tunable limit and switch for the stage.
  No module in this package may hardcode a bound; they all read it from here.
* :class:`Candidate` / :class:`ProbeResult` - the well-known-path probing
  primitives (opt-in, network-bearing).
* :class:`RawSignal` - a syntactic hit produced by a sub-detector, meaning-free
  until :mod:`discoverer` scores and reports it.
* :class:`ApiFinding` / :class:`ApiDiscoveryReport` - the structured output.

Technology *detections* are deliberately NOT modelled here: they are emitted as
the project-wide :class:`technology.models.Technology` so API discovery results
merge through exactly the same reporting path as every other detection source.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ApiKind(str, Enum):
    """Classification of a discovered API endpoint or resource.

    Values are the JSON keys used by :meth:`ApiDiscoveryReport.to_dict`, so
    they are part of the module's output contract and should stay stable.
    """

    REST = "rest"
    GRAPHQL = "graphql"
    OPENAPI = "openapi"
    WEBSOCKET = "websocket"
    SSE = "sse"
    JSON = "json"
    JSONRPC = "jsonrpc"
    XMLRPC = "xmlrpc"
    TRPC = "trpc"
    GRPC_WEB = "grpc_web"


class DiscoverySource(str, Enum):
    """Where a finding's evidence was observed or established.

    Provenance for humans ("which part of the page/response said so"),
    distinct from the ConfidenceEngine *source key* used for scoring.
    """

    HTML_MARKUP = "html"
    INLINE_SCRIPT = "inline_script"
    SCRIPT_URL = "script_url"
    HEADER = "header"
    WELL_KNOWN_PATH = "well_known_path"
    PROBE = "probe"


@dataclass(slots=True)
class ApiDiscoveryConfig:
    """Tunable limits and switches for API discovery.

    Defaults are deliberately conservative and **network-free**: with
    ``probe_reachability=False`` the stage only reads material already present
    in the fetched HTML/JS, so enabling ``--api-discovery`` costs no extra
    requests. Memory is bounded by the byte caps, output by the count caps, and
    wall-clock by :attr:`time_budget_seconds` / :attr:`probe_time_budget_seconds`.
    """

    # ---- scan volume (memory bound, passive text mining) --------------
    max_html_bytes: int = 3_000_000
    max_inline_scripts: int = 40
    max_bytes_per_unit: int = 400_000
    max_total_scan_bytes: int = 2_000_000
    max_strings_per_unit: int = 4_000
    # Longest string literal still considered as an endpoint candidate. Real
    # endpoints are short; longer literals are inlined data and only cost
    # time to classify.
    max_string_literal_length: int = 300

    # ---- output volume (report bound) ----------------------------------
    max_findings_per_kind: int = 50
    max_evidence_per_finding: int = 5
    max_value_length: int = 200

    # ---- time bound (passive scan) -------------------------------------
    time_budget_seconds: float = 5.0

    # ---- behaviour -------------------------------------------------------
    # Minimum confidence for a finding (and API-only technology) to be
    # reported. Mirrors TechnologyDetector.MIN_CONFIDENCE so all stages of the
    # pipeline share a single bar.
    min_confidence: float = 0.30

    # ---- reachability probing (opt-in, network-bearing) -----------------
    # Off by default. When enabled, a small FIXED candidate list (the common
    # REST/GraphQL/Swagger paths) is checked with one lightweight request
    # each -- never a wordlist, never brute force. Discovered-but-unconfirmed
    # endpoints mined from JS/HTML may also be probed, subject to the same
    # budget, when probe_discovered_endpoints is True.
    probe_reachability: bool = False
    probe_discovered_endpoints: bool = True
    probe_timeout: float = 3.0
    # Hard ceiling on the number of HTTP requests made for one page, across
    # both well-known candidates and discovered endpoints.
    max_probes: int = 24
    probe_time_budget_seconds: float = 12.0
    # Respect robots.txt Disallow rules for the probing user agent before
    # requesting a candidate path. Fetch failures (no robots.txt, network
    # error) are treated as "no restriction" rather than blocking probing.
    respect_robots_txt: bool = True
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/137.0 Safari/537.36 WebIntelPro/2.5"
    )


@dataclass(slots=True)
class Deadline:
    """A monotonic wall-clock budget shared across the analysis stages."""

    budget: float
    started: float = field(default_factory=time.perf_counter)

    @property
    def expired(self) -> bool:
        return (time.perf_counter() - self.started) >= self.budget

    @property
    def elapsed(self) -> float:
        return round(time.perf_counter() - self.started, 3)


@dataclass(frozen=True, slots=True)
class Candidate:
    """One well-known path checked during reachability probing."""

    path: str
    kind: ApiKind
    label: str = ""


@dataclass(slots=True)
class ProbeResult:
    """The outcome of one reachability check against a candidate URL."""

    url: str
    status: Optional[int] = None
    reachable: bool = False
    error: Optional[str] = None
    content_type: str = ""
    # True once the response body was inspected and looks like a genuine
    # document of its claimed kind (e.g. a Swagger/OpenAPI JSON document),
    # rather than merely a non-404 status -- guards against catch-all pages
    # (SPA fallback routes, custom error pages) reading as false positives.
    confirmed: bool = False


@dataclass(slots=True)
class RawSignal:
    """A syntactic hit produced by a sub-detector.

    Intentionally meaning-free about scoring: sub-detectors report *what the
    text said* and leave confidence to :mod:`discoverer`, which turns signals
    into :class:`ApiFinding` objects via the shared ConfidenceEngine.
    """

    name: str
    kind: ApiKind
    value: Optional[str] = None
    evidence: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ApiFinding:
    """One piece of API discovery intelligence.

    Carries the fields the Phase 2C contract requires: endpoint/resource
    (``name``/``value``), API type (``kind``), evidence, discovery source,
    confidence (scored by the shared ConfidenceEngine), and reachability /
    HTTP status when a live probe was performed.
    """

    kind: ApiKind
    name: str
    confidence: float
    source: DiscoverySource
    location: str
    evidence: List[str] = field(default_factory=list)
    value: Optional[str] = None
    reachable: Optional[bool] = None
    http_status: Optional[int] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        payload = {
            "name": self.name,
            "type": self.kind.value,
            "confidence": self.confidence,
            "source": self.source.value,
            "location": self.location,
            "evidence": self.evidence,
        }
        if self.value is not None:
            payload["value"] = self.value
        if self.reachable is not None:
            payload["reachable"] = self.reachable
        if self.http_status is not None:
            payload["http_status"] = self.http_status
        if self.details:
            payload.update(self.details)
        return payload


@dataclass(slots=True)
class ApiDiscoveryReport:
    """Structured API discovery findings for a single page.

    Findings are held in one flat list and grouped on demand by
    :meth:`to_dict`, which is what the detector attaches to
    :class:`technology.models.TechnologyReport`.
    """

    url: str = ""
    findings: List[ApiFinding] = field(default_factory=list)
    probed: bool = False
    elapsed: float = 0.0
    truncated: bool = False
    errors: List[str] = field(default_factory=list)

    def add(self, finding: ApiFinding) -> None:
        self.findings.append(finding)

    def by_kind(self, kind: ApiKind) -> List[ApiFinding]:
        """Findings of one API type, in report order."""
        return [f for f in self.findings if f.kind is kind]

    def to_dict(self) -> dict:
        """Serialise to the Phase 2C output contract.

        Every :class:`ApiKind` gets a key (empty list when nothing was found)
        so consumers can rely on the shape without existence checks.
        """
        grouped: Dict[str, List[dict]] = {kind.value: [] for kind in ApiKind}
        for finding in self.findings:
            grouped[finding.kind.value].append(finding.to_dict())
        return {
            "url": self.url,
            "total_findings": len(self.findings),
            "probed": self.probed,
            "elapsed": self.elapsed,
            "truncated": self.truncated,
            "errors": self.errors,
            **grouped,
        }


@dataclass(slots=True)
class ApiDiscoveryAnalysis:
    """The discoverer's return value: detections plus the structured report.

    ``technologies`` are ordinary :class:`technology.models.Technology`
    objects, ready to merge into the detector's running detection map;
    ``report`` is the richer API-only intelligence (endpoint inventory,
    reachability, HTTP status) that has no place in the flat technology list.
    """

    technologies: List[Any] = field(default_factory=list)
    report: ApiDiscoveryReport = field(default_factory=ApiDiscoveryReport)
