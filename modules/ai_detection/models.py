"""
WebIntelPro Enterprise X
AI Stack Detection (Phase 2D) - Data Models

Value objects for the AI-stack detection sub-system, mirroring the shape of
:mod:`modules.api_discovery.models`:

* :class:`AIDetectionConfig` - every tunable limit and switch for the stage.
  No module in this package may hardcode a bound; they all read it from here.
* :class:`Signature` - one named technology's matchable evidence, meaning-free
  until :mod:`detector` scores and reports it.
* :class:`AIFinding` / :class:`AIDetectionReport` - the structured output.

Technology *detections* are deliberately NOT modelled here: they are emitted as
the project-wide :class:`technology.models.Technology` so AI-stack results
merge through exactly the same reporting path as every other detection source.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class AICategory(str, Enum):
    """Classification of a detected AI-stack technology.

    Values are the JSON keys used by :meth:`AIDetectionReport.to_dict`, so they
    are part of the module's output contract and should stay stable.
    """

    PROVIDER = "providers"
    OPEN_SOURCE_MODEL = "open_source_models"
    LOCAL_AI = "local_ai"
    FRAMEWORK = "frameworks"
    SDK = "sdks"
    VECTOR_DB = "vector_databases"
    EMBEDDING = "embedding_services"
    INFRASTRUCTURE = "infrastructure"


class DiscoverySource(str, Enum):
    """Where a finding's evidence was observed -- provenance for humans,
    distinct from the ConfidenceEngine *source key* used for scoring."""

    HTML_MARKUP = "html"
    INLINE_SCRIPT = "inline_script"
    SCRIPT_URL = "script_url"
    HEADER = "header"


@dataclass(frozen=True, slots=True)
class Signature:
    """One named AI-stack technology's matchable evidence.

    ``patterns`` are checked against page text (raw HTML, inline scripts,
    script/resource-hint URLs); ``headers`` are checked against response
    *header names* only (never values), so this cannot leak credential-bearing
    header content. A signature with no ``patterns`` still needs at least one
    entry in ``headers`` (or vice versa) to ever fire.
    """

    name: str
    category: AICategory
    patterns: Tuple[str, ...] = ()
    headers: Tuple[str, ...] = ()


@dataclass(slots=True)
class AIDetectionConfig:
    """Tunable limits and switches for AI-stack detection.

    Defaults are deliberately conservative and **network-free**: the stage
    only reads material already present in the fetched HTML/JS plus response
    headers already fetched for the page, so enabling ``--ai-detection`` costs
    no extra requests. Memory is bounded by the byte caps, wall-clock by
    :attr:`time_budget_seconds`. Mirrors
    :class:`modules.api_discovery.models.ApiDiscoveryConfig`.
    """

    # ---- scan volume (memory bound, passive text mining) --------------
    max_html_bytes: int = 3_000_000
    max_inline_scripts: int = 40
    max_bytes_per_unit: int = 400_000
    max_total_scan_bytes: int = 2_000_000

    # ---- output volume (report bound) ----------------------------------
    max_findings_per_category: int = 50
    max_evidence_per_finding: int = 5

    # ---- time bound (passive scan) -------------------------------------
    time_budget_seconds: float = 5.0

    # ---- behaviour -------------------------------------------------------
    # Minimum confidence for a finding (and AI-stack-only technology) to be
    # reported. Mirrors TechnologyDetector.MIN_CONFIDENCE so all stages of the
    # pipeline share a single bar.
    min_confidence: float = 0.30


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


@dataclass(slots=True)
class AIFinding:
    """One piece of AI-stack detection intelligence.

    Carries the fields the Phase 2D contract requires: provider/framework
    name, category, evidence, discovery source, confidence (scored by the
    shared ConfidenceEngine), and version when confidently detected.
    """

    category: AICategory
    name: str
    confidence: float
    sources: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    version: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        payload = {
            "name": self.name,
            "category": self.category.value,
            "confidence": self.confidence,
            "sources": self.sources,
            "evidence": self.evidence,
        }
        if self.version is not None:
            payload["version"] = self.version
        if self.details:
            payload.update(self.details)
        return payload


@dataclass(slots=True)
class AIDetectionReport:
    """Structured AI-stack detection findings for a single page.

    Findings are held in one flat list and grouped on demand by
    :meth:`to_dict`, which is what the detector attaches to
    :class:`technology.models.TechnologyReport`.
    """

    url: str = ""
    findings: List[AIFinding] = field(default_factory=list)
    elapsed: float = 0.0
    truncated: bool = False
    errors: List[str] = field(default_factory=list)

    def add(self, finding: AIFinding) -> None:
        self.findings.append(finding)

    def by_category(self, category: AICategory) -> List[AIFinding]:
        """Findings of one category, in report order."""
        return [f for f in self.findings if f.category is category]

    def to_dict(self) -> dict:
        """Serialise to the Phase 2D output contract.

        Every :class:`AICategory` gets a key (empty list when nothing was
        found) so consumers can rely on the shape without existence checks.
        """
        grouped: Dict[str, List[dict]] = {cat.value: [] for cat in AICategory}
        for finding in self.findings:
            grouped[finding.category.value].append(finding.to_dict())
        return {
            "url": self.url,
            "total_findings": len(self.findings),
            "elapsed": self.elapsed,
            "truncated": self.truncated,
            "errors": self.errors,
            **grouped,
        }


@dataclass(slots=True)
class AIDetectionAnalysis:
    """The detector's return value: detections plus the structured report.

    ``technologies`` are ordinary :class:`technology.models.Technology`
    objects, ready to merge into the caller's running detection map;
    ``report`` is the richer AI-stack-only intelligence (category, sources,
    evidence) that has no place in the flat technology list.
    """

    technologies: List[Any] = field(default_factory=list)
    report: AIDetectionReport = field(default_factory=AIDetectionReport)
