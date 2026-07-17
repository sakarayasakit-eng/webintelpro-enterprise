"""
WebIntelPro Enterprise X
JavaScript Bundle Intelligence (Phase 2A)

An additive detection capability that inspects downloaded JavaScript bundle
*contents* - not just script URLs - so client libraries, frameworks and build
tools can be identified even when a page's HTML carries no useful fingerprint.

Public surface
--------------
* :class:`JSBundleAnalyzer` - the orchestrator; discovers, downloads and scans
  bundles and returns :class:`technology.models.Technology` detections scored on
  the shared confidence scale. This is what :class:`TechnologyDetector` calls.
* :class:`BundleConfig`     - download/scan limits (fully bounded by default).
* :class:`BundleDiscovery`, :class:`BundleFetcher`, :class:`BundleScanner`,
  :class:`VersionExtractor` - the individually reusable stages.
* :data:`BUNDLE_SIGNATURES` - the content-signature database.

The sub-system is intentionally decoupled: it emits the project-wide
``Technology`` model and reuses the existing ``RuleEngine`` and
``ConfidenceEngine`` rather than introducing parallel machinery.
"""

from __future__ import annotations

from .analyzer import BUNDLE_SOURCE, JSBundleAnalyzer
from .detector import BUNDLE_SIGNATURES, BundleScanner
from .extractor import VersionExtractor
from .fetcher import BundleFetcher
from .models import BundleConfig, BundleFinding, JSBundle
from .parser import BundleDiscovery

__all__ = [
    "JSBundleAnalyzer",
    "BundleConfig",
    "BundleDiscovery",
    "BundleFetcher",
    "BundleScanner",
    "VersionExtractor",
    "BundleFinding",
    "JSBundle",
    "BUNDLE_SIGNATURES",
    "BUNDLE_SOURCE",
]
