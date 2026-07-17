"""
WebIntelPro Enterprise X
JavaScript Runtime Intelligence (Phase 2B)

An additive, opt-in detection capability that reads a page's *runtime* surface -
global objects, hydration payloads, embedded JSON, runtime config, API
references - **without a browser**. No Playwright, Selenium, Chromium or
Puppeteer: everything is derived by reading HTML, inline JavaScript, embedded
JSON and (optionally) downloaded bundles as text.

Where Phase 2A (:mod:`technology.javascript`) answers "what is inside the
bundles?", Phase 2B answers "what does the page say about itself at runtime?" -
which framework mounted, how it hydrates, what it will call, how it is
configured.

Public surface
--------------
* :class:`RuntimeAnalyzer`  - the orchestrator; returns a :class:`RuntimeAnalysis`
  carrying both :class:`technology.models.Technology` detections and the
  structured :class:`RuntimeReport`. This is what :class:`TechnologyDetector`
  calls when ``detect(analyze_runtime=True)``.
* :class:`RuntimeConfig`    - every limit for the stage (bounded by default).
* :class:`RuntimeExtractor`, :class:`RuntimeParser`,
  :class:`RuntimeSignatureScanner`, :class:`HydrationInference` - the
  individually reusable stages.
* :data:`RUNTIME_SIGNATURES`, :data:`HYDRATION_RULES` - the signature databases;
  extending detection normally means adding a row to one of these.

The sub-system introduces no parallel machinery: it emits the project-wide
``Technology`` model and reuses the existing ``RuleEngine`` and
``ConfidenceEngine`` for all matching and scoring.
"""

from __future__ import annotations

from .analyzer import RUNTIME_SOURCE, RUNTIME_WEAK_SOURCE, RuntimeAnalyzer
from .detector import (
    CONFIG_GLOBALS,
    GENERIC_STATE_GLOBALS,
    HYDRATION_RULES,
    RUNTIME_SIGNATURES,
    HydrationInference,
    HydrationRule,
    HydrationSignal,
    RuntimeSignature,
    RuntimeSignatureScanner,
)
from .extractor import RuntimeExtractor
from .models import (
    CodeUnit,
    Deadline,
    EndpointKind,
    FindingKind,
    HydrationStrategy,
    JSONBlob,
    RawSignal,
    RuntimeAnalysis,
    RuntimeConfig,
    RuntimeContext,
    RuntimeFinding,
    RuntimeReport,
    RuntimeSource,
)
from .parser import RuntimeParser, classify_endpoint, extract_object_literal

__all__ = [
    # orchestration
    "RuntimeAnalyzer",
    "RuntimeAnalysis",
    "RuntimeConfig",
    # stages
    "RuntimeExtractor",
    "RuntimeParser",
    "RuntimeSignatureScanner",
    "HydrationInference",
    # models
    "RuntimeReport",
    "RuntimeFinding",
    "RuntimeContext",
    "RawSignal",
    "CodeUnit",
    "JSONBlob",
    "Deadline",
    "FindingKind",
    "RuntimeSource",
    "HydrationStrategy",
    "EndpointKind",
    # signature databases
    "RUNTIME_SIGNATURES",
    "HYDRATION_RULES",
    "CONFIG_GLOBALS",
    "GENERIC_STATE_GLOBALS",
    "RuntimeSignature",
    "HydrationRule",
    "HydrationSignal",
    # primitives
    "classify_endpoint",
    "extract_object_literal",
    # confidence source keys
    "RUNTIME_SOURCE",
    "RUNTIME_WEAK_SOURCE",
]
