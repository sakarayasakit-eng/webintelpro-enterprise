"""
WebIntelPro Enterprise X
Technology Detection Data Models
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(slots=True)
class Technology:
    """A single detected technology."""

    name: str
    category: str
    confidence: float
    version: Optional[str] = None
    evidence: List[str] = field(default_factory=list)
    # Populated only when TechnologyDetector.detect(debug=True): per-source
    # breakdown of what matched and how much it contributed to `confidence`.
    debug: Optional[Dict[str, dict]] = None


@dataclass(slots=True)
class TechnologyReport:
    """Container for all technology detection results."""

    url: str

    server: Optional[str] = None
    backend: Optional[str] = None
    cms: Optional[str] = None

    technologies: List[Technology] = field(default_factory=list)

    headers: Dict[str, str] = field(default_factory=dict)
    cookies: Dict[str, str] = field(default_factory=dict)
    meta: Dict[str, str] = field(default_factory=dict)

    total_detected: int = 0
    elapsed: float = 0.0

    errors: List[str] = field(default_factory=list)

    # Populated only when TechnologyDetector.detect(analyze_runtime=True):
    # structured JavaScript runtime intelligence (hydration, API discovery,
    # runtime config, env vars, state management, dynamic imports, PWA) as
    # produced by technology.runtime.RuntimeReport.to_dict(). Stays None on the
    # default path, so to_dict() output is unchanged when the stage is off.
    runtime: Optional[Dict[str, object]] = None

    def add(self, technology: Technology) -> None:
        self.technologies.append(technology)

    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def by_category(self) -> Dict[str, List[str]]:
        """Group detected technology names by category."""
        grouped: Dict[str, List[str]] = {}
        for tech in self.technologies:
            grouped.setdefault(tech.category, []).append(tech.name)
        return grouped

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "server": self.server,
            "backend": self.backend,
            "cms": self.cms,
            "total_detected": self.total_detected,
            "elapsed": self.elapsed,
            "categories": self.by_category(),
            "headers": self.headers,
            "cookies": self.cookies,
            "errors": self.errors,
            "technologies": [
                {
                    "name": tech.name,
                    "category": tech.category,
                    "confidence": tech.confidence,
                    "version": tech.version,
                    "evidence": tech.evidence,
                    **({"debug": tech.debug} if tech.debug else {}),
                }
                for tech in self.technologies
            ],
            **({"runtime": self.runtime} if self.runtime else {}),
        }
