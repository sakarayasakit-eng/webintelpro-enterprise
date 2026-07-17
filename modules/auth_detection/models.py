"""
WebIntelPro Enterprise X
Authentication & Identity Intelligence (Phase 2E) - Data Models

Value objects for the auth-detection sub-system, mirroring the shape of
:mod:`modules.ai_detection.models`:

* :class:`AuthDetectionConfig` - every tunable limit and switch for the stage.
  No module in this package may hardcode a bound; they all read it from here.
* :class:`Signature` - one named provider/protocol/feature's matchable
  evidence, meaning-free until :mod:`detector` scores and reports it.
* :class:`AuthFinding` / :class:`AuthDetectionReport` - the structured output.

Technology *detections* are deliberately NOT modelled here: they are emitted
as the project-wide :class:`technology.models.Technology` so auth-stack
results merge through exactly the same reporting path as every other
detection source.

One addition over the Phase 2D shape: :class:`Signature` carries a
``cookies`` field alongside ``headers``. Session-cookie *names* (e.g.
``connect.sid``, ``__session``) are some of the strongest passive signals of
an authentication architecture, and the project already treats cookie
*names* (never values) as a legitimate first-class evidence source
elsewhere (``technology.matcher``'s "cookies" source, weight 0.55). This
package is the first Phase-2x sub-system to read them, via
:meth:`AuthDetector._scan_cookies`, which -- exactly like header scanning --
never inspects a cookie's *value*.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class AuthCategory(str, Enum):
    """Classification of a detected authentication technology.

    Values are the JSON keys used by :meth:`AuthDetectionReport.to_dict`, so
    they are part of the module's output contract and should stay stable.

    ``PROVIDER`` covers Auth-as-a-Service / CIAM platforms (Auth0, Clerk,
    Firebase Auth, AWS Cognito, Supabase Auth, Descope, FusionAuth, Stytch,
    Magic.link) -- products a site integrates as a client.
    ``IDENTITY_PROVIDER`` covers enterprise SSO/IdP systems (Okta, Azure
    Entra ID, Keycloak) -- the classic "Identity Provider" role in SAML/OIDC
    federation, distinct enough in practice (and in the reporter's requested
    grouping) to warrant its own bucket rather than folding into PROVIDER.
    """

    PROVIDER = "providers"
    IDENTITY_PROVIDER = "identity_providers"
    PROTOCOL = "protocols"
    SECURITY_FEATURE = "security_features"


class DiscoverySource(str, Enum):
    """Where a finding's evidence was observed -- provenance for humans,
    distinct from the ConfidenceEngine *source key* used for scoring."""

    HTML_MARKUP = "html"
    INLINE_SCRIPT = "inline_script"
    SCRIPT_URL = "script_url"
    HEADER = "header"
    COOKIE = "cookie"


@dataclass(frozen=True, slots=True)
class Signature:
    """One named auth technology's matchable evidence.

    ``patterns`` are checked against page text (raw HTML, inline scripts,
    script/resource-hint URLs); ``headers`` are checked against response
    *header names* only (never values); ``cookies`` are checked against
    *cookie names* only (never values) -- so this cannot leak
    credential-bearing header/cookie content. A signature needs at least one
    non-empty field to ever fire.
    """

    name: str
    category: AuthCategory
    patterns: Tuple[str, ...] = ()
    headers: Tuple[str, ...] = ()
    cookies: Tuple[str, ...] = ()


@dataclass(slots=True)
class AuthDetectionConfig:
    """Tunable limits and switches for auth detection.

    Defaults are deliberately conservative and **network-free**: the stage
    only reads material already present in the fetched HTML/JS plus response
    headers and cookies already fetched for the page, so enabling
    ``--auth-detection`` costs no extra requests. Memory is bounded by the
    byte caps, wall-clock by :attr:`time_budget_seconds`. Mirrors
    :class:`modules.ai_detection.models.AIDetectionConfig`.
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
    # Minimum confidence for a finding (and auth-only technology) to be
    # reported. Mirrors TechnologyDetector.MIN_CONFIDENCE so all stages of
    # the pipeline share a single bar.
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
class AuthFinding:
    """One piece of authentication/identity detection intelligence.

    Carries the fields the Phase 2E contract requires: provider/protocol/
    feature name, category, evidence, discovery source, confidence (scored
    by the shared ConfidenceEngine).
    """

    category: AuthCategory
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
class AuthDetectionReport:
    """Structured authentication detection findings for a single page.

    Findings are held in one flat list and grouped on demand by
    :meth:`to_dict`, which is what the detector attaches to
    :class:`technology.models.TechnologyReport`.
    """

    url: str = ""
    findings: List[AuthFinding] = field(default_factory=list)
    elapsed: float = 0.0
    truncated: bool = False
    errors: List[str] = field(default_factory=list)

    def add(self, finding: AuthFinding) -> None:
        self.findings.append(finding)

    def by_category(self, category: AuthCategory) -> List[AuthFinding]:
        """Findings of one category, in report order."""
        return [f for f in self.findings if f.category is category]

    def to_dict(self) -> dict:
        """Serialise to the Phase 2E output contract.

        Every :class:`AuthCategory` gets a key (empty list when nothing was
        found) so consumers can rely on the shape without existence checks.
        """
        grouped: Dict[str, List[dict]] = {cat.value: [] for cat in AuthCategory}
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
class AuthDetectionAnalysis:
    """The detector's return value: detections plus the structured report.

    ``technologies`` are ordinary :class:`technology.models.Technology`
    objects, ready to merge into the caller's running detection map;
    ``report`` is the richer auth-stack-only intelligence (category, sources,
    evidence) that has no place in the flat technology list.
    """

    technologies: List[Any] = field(default_factory=list)
    report: AuthDetectionReport = field(default_factory=AuthDetectionReport)
