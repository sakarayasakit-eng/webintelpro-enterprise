"""
WebIntelPro Enterprise X
Technology Detection Engine v3
"""

from __future__ import annotations

from typing import Dict

from .confidence import ConfidenceEngine
from .fingerprints import TECH_FINGERPRINTS
from .matcher import FingerprintMatcher
from .models import Technology, TechnologyReport
from .parser import HTMLParser
from .utils import normalize_headers
from .version import VersionEngine


class TechnologyDetector:
    """
    Enterprise technology detection engine.
    Coordinates parsing, matching, confidence scoring,
    and version extraction.
    """

    def __init__(self):

        self.parser = HTMLParser()
        self.matcher = FingerprintMatcher()
        self.confidence = ConfidenceEngine()
        self.version = VersionEngine()

    def detect(
        self,
        url: str,
        html: str = "",
        headers: Dict[str, str] | None = None,
    ) -> TechnologyReport:

        if headers is None:
            headers = {}

        report = TechnologyReport(url=url)
        report.headers = normalize_headers(headers)

        parsed = self.parser.parse(html)

        for rule in TECH_FINGERPRINTS:

            matches = self.matcher.evaluate(
                rule,
                parsed,
                report.headers,
            )

            confidence = self.confidence.calculate(matches)

            if confidence <= 0:
                continue

            version = self._extract_version(
                matches,
                parsed,
            )

            tech = Technology(
                name=rule["name"],
                category=rule["category"],
                confidence=confidence,
                version=version,
                evidence=self._collect_evidence(matches),
            )

            report.add(tech)

            if rule["category"] == "cms":
                report.cms = rule["name"]

            if rule["category"] == "server":
                report.server = rule["name"]

        return report

    def _collect_evidence(self, matches):

        evidence = []

        for source, result in matches.items():

            if result.matched:
                evidence.extend(result.evidence)

        return evidence

    def _extract_version(self, matches, parsed):

        for result in matches.values():

            if not result.matched:
                continue

            for value in result.evidence:

                version = self.version.extract(value)

                if version:
                    return version

        return None