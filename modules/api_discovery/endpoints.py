"""
WebIntelPro Enterprise X
API Discovery (Phase 2C) - REST / JSON Endpoints & RPC

Two responsibilities:

* **Candidate-string extraction** -- the shared "what looks like an endpoint
  reference" pass used by :mod:`discoverer` for every API kind: named call
  sites (``fetch()``, ``XMLHttpRequest.open()``, ``axios``, jQuery AJAX) plus a
  generic quoted-string fallback for URL construction patterns and static JSON
  URLs. Classification of *what kind* a candidate is happens elsewhere
  (:func:`classify` here for REST/JSON/RPC; :mod:`graphql`, :mod:`swagger` and
  :mod:`websocket` for their own kinds), so this module owns extraction only.
* **REST/JSON/RPC classification and signatures** -- shape-based endpoint
  classification plus JSON-RPC / XML-RPC / tRPC / gRPC-Web library markers.

Everything here is regex-based, bounded and side-effect-free: no input can
make a function raise, and unparseable text simply yields no signals.
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Tuple

from technology.rules import RuleEngine, RuleResult

from .models import ApiKind, Candidate, RawSignal
from .utils import truncate

logger = logging.getLogger("webintelpro.api_discovery.endpoints")

# ---------------------------------------------------------------------------
# Well-known REST candidate paths (probed only when reachability probing is
# explicitly enabled). A small, fixed list -- never a wordlist.
# ---------------------------------------------------------------------------
REST_CANDIDATES: List[Candidate] = [
    Candidate("/api", ApiKind.REST, "api root"),
    Candidate("/api/v1", ApiKind.REST, "api v1"),
    Candidate("/api/v2", ApiKind.REST, "api v2"),
    Candidate("/rest", ApiKind.REST, "rest root"),
    Candidate("/services", ApiKind.REST, "services root"),
    Candidate("/service", ApiKind.REST, "service root"),
    Candidate("/backend", ApiKind.REST, "backend root"),
    Candidate("/public/api", ApiKind.REST, "public api"),
    Candidate("/private/api", ApiKind.REST, "private api"),
]

# ---------------------------------------------------------------------------
# Candidate-string extraction
# ---------------------------------------------------------------------------

# A quoted string literal (single, double or backtick). Same load-bearing
# shape as technology.runtime.parser._QUOTED: the backreference keeps the scan
# synchronised across a whole script, and length is filtered afterwards.
_QUOTED = re.compile(r"""(['"`])((?:\\.|(?!\1)[^\\\n])*)\1""")

# Named call sites, each capturing the URL argument directly so evidence can
# cite *how* the endpoint is called, not just that a string looked URL-shaped.
_CALL_SITES: Tuple[Tuple[str, re.Pattern], ...] = (
    ("fetch", re.compile(r"""fetch\s*\(\s*['"`]([^'"`\n]{1,300})['"`]""")),
    ("xhr", re.compile(
        r"""\.open\s*\(\s*['"`](?:GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)"""
        r"""['"`]\s*,\s*['"`]([^'"`\n]{1,300})['"`]""", re.IGNORECASE)),
    ("axios", re.compile(
        r"""axios(?:\.(?:get|post|put|delete|patch|head|options)\s*\(|"""
        r"""\s*\(\s*\{[^{}]{0,60}?url\s*:\s*)\s*['"`]([^'"`\n]{1,300})['"`]""",
        re.IGNORECASE)),
    ("jquery_ajax", re.compile(
        r"""\$\.(?:ajax|get|post|getJSON)\s*\(\s*(?:\{[^{}]{0,60}?url\s*:\s*)?"""
        r"""['"`]([^'"`\n]{1,300})['"`]""", re.IGNORECASE)),
)

_URL_SCHEMES = ("http://", "https://", "//")


def find_candidate_strings(text: str, max_strings: int,
                           max_literal_length: int) -> List[Tuple[str, str, str]]:
    """Return ``(value, evidence, call_hint)`` triples for candidate endpoints.

    ``call_hint`` is one of the named call sites (``fetch``, ``xhr``, ``axios``,
    ``jquery_ajax``) when the string was captured from a recognisable call, or
    ``""`` for the generic quoted-string fallback (URL construction patterns,
    static JSON URLs). Bounded by ``max_strings`` scanned literals; callers
    classify and cap the *output* separately.
    """
    if not text:
        return []
    seen_spans: set = set()
    results: List[Tuple[str, str, str]] = []

    for call_hint, pattern in _CALL_SITES:
        for match in pattern.finditer(text):
            value = match.group(1)
            if not value:
                continue
            seen_spans.add(match.span(1))
            results.append((value, truncate(match.group(0), 100), call_hint))

    scanned = 0
    for match in _QUOTED.finditer(text):
        scanned += 1
        if scanned > max_strings:
            logger.debug("string scan capped at %d", max_strings)
            break
        if match.span(2) in seen_spans:
            continue  # already captured by a named call site above
        value = match.group(2)
        if not 2 <= len(value) <= max_literal_length:
            continue
        results.append((value, value, ""))

    return results


# ---------------------------------------------------------------------------
# REST / JSON / RPC classification
# ---------------------------------------------------------------------------

def _has_segment(url: str, segment: str) -> bool:
    """Whether ``url`` contains ``segment`` as a whole path segment."""
    path = url.split("?", 1)[0].split("#", 1)[0]
    return f"/{segment}" == path[-len(segment) - 1:] or f"/{segment}/" in path


def classify(value: str) -> Optional[ApiKind]:
    """Classify a string as a REST, JSON, or RPC endpoint, or ``None``.

    Only called after :mod:`websocket`, :mod:`graphql` and :mod:`swagger` have
    had first refusal, so a ``/graphql`` or ``/swagger.json`` path never
    reaches here. A candidate must look like a path or URL and contain no
    whitespace -- the same guard :mod:`technology.runtime.parser` uses to
    reject MIME types, CSS values and prose.
    """
    if not value:
        return None
    candidate = value.strip()
    if len(candidate) < 2 or " " in candidate or "\t" in candidate:
        return None
    low = candidate.lower()
    if not (low.startswith("/") or low.startswith(_URL_SCHEMES)):
        return None
    if low.startswith("//") and len(low) < 5:
        return None

    if _has_segment(low, "trpc") or "/api/trpc" in low:
        return ApiKind.TRPC
    if "jsonrpc" in low or "json-rpc" in low:
        return ApiKind.JSONRPC
    if "xmlrpc" in low or "xml-rpc" in low:
        return ApiKind.XMLRPC
    if "grpc-web" in low or _has_segment(low, "grpc"):
        return ApiKind.GRPC_WEB
    if ("/api/" in low or low.endswith("/api") or "/rest/" in low
            or re.search(r"/v\d+(/|$)", low) or _has_segment(low, "services")
            or _has_segment(low, "service") or _has_segment(low, "backend")):
        return ApiKind.REST
    if low.endswith(".json") or ".json?" in low:
        return ApiKind.JSON
    return None


# ---------------------------------------------------------------------------
# RPC library signatures
# ---------------------------------------------------------------------------

RPC_SIGNATURES: Tuple[Tuple[str, ApiKind, Tuple[str, ...]], ...] = (
    ("tRPC", ApiKind.TRPC, (
        "@trpc/client", "@trpc/server", "@trpc/react-query",
        "createtrpcproxyclient", "createtrpcreact", "trpc.createrouter",
    )),
    ("JSON-RPC", ApiKind.JSONRPC, (
        '"jsonrpc":"2.0"', 'jsonrpc:"2.0"', 'jsonrpc: "2.0"',
        "jsonrpc-lite", "json-rpc-2.0", "application/json-rpc",
    )),
    ("XML-RPC", ApiKind.XMLRPC, (
        "<methodcall>", "xmlrpc.php", "text/xml; charset=\"utf-8\"",
        "system.multicall",
    )),
    ("gRPC-Web", ApiKind.GRPC_WEB, (
        "grpc-web", "@improbable-eng/grpc-web", "grpcwebclientbase",
        "application/grpc-web", "x-grpc-web",
    )),
)


def scan_signatures(text: str, engine: RuleEngine) -> List[RawSignal]:
    """Match RPC library markers against one unit of text."""
    if not text:
        return []
    low = text.lower()
    signals: List[RawSignal] = []
    for name, kind, patterns in RPC_SIGNATURES:
        candidates = [p for p in patterns if p.lower() in low]
        if not candidates:
            continue
        result: RuleResult = engine.match(candidates, low)
        if result.matched:
            signals.append(RawSignal(
                name=name, kind=kind,
                evidence=sorted(set(result.evidence)),
                details={"technology": name},
            ))
    return signals
