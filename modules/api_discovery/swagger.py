"""
WebIntelPro Enterprise X
API Discovery (Phase 2C) - Swagger / OpenAPI

Detects Swagger/OpenAPI documentation surfaces through well-known paths,
Swagger UI / Redoc client markers in HTML/JS, and (when reachability probing
is enabled) doc-shape validation of the fetched body -- so a 200 response from
an SPA's catch-all route is never mistaken for a real specification document.
"""

from __future__ import annotations

import json
import re
from typing import List, Optional, Tuple

from technology.rules import RuleEngine, RuleResult

from .models import ApiKind, Candidate, RawSignal

# ---------------------------------------------------------------------------
# Well-known candidate paths (probed only when reachability probing is
# explicitly enabled).
# ---------------------------------------------------------------------------
SWAGGER_CANDIDATES: List[Candidate] = [
    Candidate("/swagger", ApiKind.OPENAPI, "swagger root"),
    Candidate("/swagger-ui", ApiKind.OPENAPI, "swagger ui"),
    Candidate("/swagger/index.html", ApiKind.OPENAPI, "swagger ui"),
    Candidate("/swagger.json", ApiKind.OPENAPI, "swagger document"),
    Candidate("/openapi.json", ApiKind.OPENAPI, "openapi document"),
    Candidate("/openapi.yaml", ApiKind.OPENAPI, "openapi document"),
    Candidate("/api-docs", ApiKind.OPENAPI, "api docs"),
    Candidate("/v3/api-docs", ApiKind.OPENAPI, "springdoc api docs"),
]

_URL_SCHEMES = ("http://", "https://", "//")


def classify(value: str) -> Optional[ApiKind]:
    """Classify a string as a Swagger/OpenAPI resource, or ``None``."""
    if not value:
        return None
    candidate = value.strip()
    if len(candidate) < 2 or " " in candidate or "\t" in candidate:
        return None
    low = candidate.lower()
    if not (low.startswith("/") or low.startswith(_URL_SCHEMES)):
        return None
    if "openapi" in low or "swagger" in low or "/api-docs" in low:
        return ApiKind.OPENAPI
    return None


# ---------------------------------------------------------------------------
# Client / UI signatures
# ---------------------------------------------------------------------------
_SIGNATURES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("Swagger UI", (
        "swagger-ui", "swaggerui", "swagger-ui-bundle.js",
        "swagger-ui-standalone-preset",
    )),
    ("Redoc", (
        "redoc.standalone.js", "<redoc ", "spec-url=",
    )),
    ("Springdoc / OpenAPI", (
        "springdoc", "/v3/api-docs",
    )),
)


def scan_signatures(text: str, engine: RuleEngine) -> List[RawSignal]:
    """Match Swagger UI / Redoc client markers in ``text``."""
    if not text:
        return []
    low = text.lower()
    signals: List[RawSignal] = []
    for name, patterns in _SIGNATURES:
        candidates = [p for p in patterns if p in low]
        if not candidates:
            continue
        result: RuleResult = engine.match(candidates, low)
        if result.matched:
            signals.append(RawSignal(
                name=name, kind=ApiKind.OPENAPI,
                evidence=sorted(set(result.evidence)),
                details={"technology": name},
            ))
    return signals


# ---------------------------------------------------------------------------
# Doc-shape validation (used only against a probed response body)
# ---------------------------------------------------------------------------
_YAML_OPENAPI = re.compile(r"^\s*openapi\s*:\s*['\"]?3", re.MULTILINE)
_YAML_SWAGGER = re.compile(r"^\s*swagger\s*:\s*['\"]?2", re.MULTILINE)


def looks_like_openapi_doc(body: str) -> bool:
    """Whether ``body`` (a bounded snippet) looks like a genuine spec document.

    Tries strict JSON first (a truncated snippet often still parses if the
    top-level keys land within the sniffed window), then falls back to a
    shape check on the raw text -- which also covers YAML and JSON snippets
    cut off before the closing brace.
    """
    if not body:
        return False
    stripped = body.strip()
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
            if isinstance(data, dict) and ("swagger" in data or "openapi" in data):
                return True
        except (ValueError, TypeError):
            pass
    head = stripped[:400]
    if '"openapi"' in head or '"swagger"' in head:
        return True
    return bool(_YAML_OPENAPI.search(head) or _YAML_SWAGGER.search(head))
