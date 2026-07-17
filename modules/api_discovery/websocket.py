"""
WebIntelPro Enterprise X
API Discovery (Phase 2C) - WebSocket & Server-Sent Events

Detects WebSocket usage (``ws://``/``wss://``, ``new WebSocket(...)``,
Socket.IO, SockJS, SignalR) and Server-Sent Events (``new EventSource(...)``,
``text/event-stream``) from JavaScript and HTML alone.

No candidate paths are probed for either kind: confirming a WebSocket or SSE
endpoint requires a protocol upgrade / a held-open stream, which a bounded
HTTP HEAD/GET cannot meaningfully verify -- so, unlike REST/GraphQL/OpenAPI,
this module is passive-only by design, not merely by default.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from technology.rules import RuleEngine, RuleResult

from .models import ApiKind, RawSignal
from .utils import truncate

# new WebSocket("...") / new EventSource("...") - the constructor itself
# classifies the endpoint, independently of what its path looks like.
_CONSTRUCTOR = re.compile(
    r"""new\s+(WebSocket|EventSource)\s*\(\s*['"`]([^'"`\n]{1,300})['"`]""",
    re.IGNORECASE,
)

_URL_SCHEMES = ("ws://", "wss://")


def classify(value: str) -> Optional[ApiKind]:
    """Classify a string as a WebSocket or SSE endpoint, or ``None``."""
    if not value:
        return None
    candidate = value.strip()
    if len(candidate) < 2 or " " in candidate or "\t" in candidate:
        return None
    low = candidate.lower()
    if low.startswith(_URL_SCHEMES):
        return ApiKind.WEBSOCKET
    if not (low.startswith("/") or low.startswith(("http://", "https://", "//"))):
        return None
    path = low.split("?", 1)[0].split("#", 1)[0]
    if "/socket.io" in path or _has_segment(path, "websocket") or _has_segment(path, "ws"):
        return ApiKind.WEBSOCKET
    if "event-stream" in low or _has_segment(path, "sse") or _has_segment(path, "eventsource"):
        return ApiKind.SSE
    return None


def _has_segment(path: str, segment: str) -> bool:
    """Whether ``path`` contains ``segment`` as a whole path segment."""
    return f"/{segment}" == path[-len(segment) - 1:] or f"/{segment}/" in path


def scan_constructors(text: str, max_matches: int) -> List[RawSignal]:
    """Match ``new WebSocket(...)`` / ``new EventSource(...)`` call sites."""
    if not text:
        return []
    signals: dict = {}
    for match in _CONSTRUCTOR.finditer(text):
        if len(signals) >= max_matches:
            break
        ctor, url = match.group(1).lower(), match.group(2)
        kind = ApiKind.WEBSOCKET if ctor == "websocket" else ApiKind.SSE
        value = truncate(url.strip(), 200)
        if not value:
            continue
        evidence = truncate(match.group(0), 100)
        existing = signals.get(value)
        if existing is None:
            signals[value] = RawSignal(name=value, kind=kind, value=value,
                                       evidence=[evidence])
        elif evidence not in existing.evidence:
            existing.evidence.append(evidence)
    return list(signals.values())


# ---------------------------------------------------------------------------
# Client-library signatures
# ---------------------------------------------------------------------------
_SIGNATURES: Tuple[Tuple[str, ApiKind, Tuple[str, ...]], ...] = (
    ("Socket.IO", ApiKind.WEBSOCKET, (
        "socket.io-client", "socket.io.js", "io.connect(", "io(url",
        "/socket.io/?eio=",
    )),
    ("SockJS", ApiKind.WEBSOCKET, (
        "sockjs-client", "sockjs.js", "new sockjs(",
    )),
    ("SignalR", ApiKind.WEBSOCKET, (
        "@microsoft/signalr", "signalr.js", "hubconnectionbuilder(",
        "/signalr/hubs",
    )),
    ("Server-Sent Events", ApiKind.SSE, (
        "text/event-stream",
    )),
)


def scan_signatures(text: str, engine: RuleEngine) -> List[RawSignal]:
    """Match WebSocket/SSE client-library markers in ``text``."""
    if not text:
        return []
    low = text.lower()
    signals: List[RawSignal] = []
    for name, kind, patterns in _SIGNATURES:
        candidates = [p for p in patterns if p in low]
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
