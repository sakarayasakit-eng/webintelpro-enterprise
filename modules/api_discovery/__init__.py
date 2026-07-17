"""
WebIntelPro Enterprise X
API Discovery (Phase 2C)

An additive, opt-in detection capability that discovers a page's API surface --
REST/JSON endpoints, GraphQL, Swagger/OpenAPI, JSON-RPC/XML-RPC/tRPC/gRPC-Web,
WebSocket and Server-Sent Events -- from the HTML and JavaScript already
fetched for it, with an optional, conservative reachability-probing pass
against a small fixed set of well-known paths.

Public surface
--------------
* :class:`ApiDiscoverer`      - the orchestrator; returns an
  :class:`ApiDiscoveryAnalysis` carrying both
  :class:`technology.models.Technology` detections and the structured
  :class:`ApiDiscoveryReport`. This is what
  :class:`technology.detector.TechnologyDetector` calls when
  ``detect(analyze_api=True)``.
* :class:`ApiDiscoveryConfig`  - every limit and switch for the stage
  (network-free by default; reachability probing is a separate opt-in).
* :mod:`endpoints`, :mod:`graphql`, :mod:`swagger`, :mod:`websocket` - the
  per-API-type detectors; extending detection normally means adding a
  candidate path or signature to one of these.

The sub-system introduces no parallel machinery: it emits the project-wide
``Technology`` model and reuses the existing ``RuleEngine`` and
``ConfidenceEngine`` for all matching and scoring.
"""

from __future__ import annotations

from . import endpoints, graphql, swagger
from . import websocket as websocket_
from .discoverer import API_EVIDENCE_SOURCE, API_PROBE_SOURCE, ApiDiscoverer
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
from .utils import ReachabilityProber, RobotsChecker

# Backward/forward-friendly alias: importable as `websocket` without shadowing
# the standard-library-adjacent name inside this package's own modules.
websocket = websocket_

__all__ = [
    # orchestration
    "ApiDiscoverer",
    "ApiDiscoveryAnalysis",
    "ApiDiscoveryConfig",
    # sub-detectors
    "endpoints",
    "graphql",
    "swagger",
    "websocket",
    # models
    "ApiDiscoveryReport",
    "ApiFinding",
    "RawSignal",
    "Candidate",
    "ProbeResult",
    "Deadline",
    "ApiKind",
    "DiscoverySource",
    # probing primitives
    "ReachabilityProber",
    "RobotsChecker",
    # confidence source keys
    "API_EVIDENCE_SOURCE",
    "API_PROBE_SOURCE",
]
