"""
WebIntelPro Enterprise X
JavaScript Runtime Intelligence (Phase 2B) - Utilities

Small, dependency-light helpers shared by the extractor, parser, detector and
analyzer: JSON tolerance, JSON tree walking, secret redaction, value
normalisation and de-duplication.

Two invariants hold for everything in this module:

* **Never raises.** Malformed input yields an empty/neutral result, because a
  parsing failure must degrade to "no detection", never to a crash.
* **Never unbounded.** Any function that could walk or build something large
  takes an explicit cap from :class:`~technology.runtime.models.RuntimeConfig`.
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable, Iterator, List, Optional, Tuple

# Environment-variable name prefixes that frameworks expose to the client. A
# name carrying one of these is, by construction, meant to be public - which is
# exactly why it is useful intelligence and safe to report.
PUBLIC_ENV_PREFIXES: Tuple[str, ...] = (
    "NEXT_PUBLIC_",
    "VITE_",
    "PUBLIC_",
    "REACT_APP_",
    "VUE_APP_",
    "NUXT_PUBLIC_",
    "GATSBY_",
    "EXPO_PUBLIC_",
    "STORYBOOK_",
)

# Name fragments that suggest a value is a credential. Public-prefixed names
# routinely and legitimately contain "KEY" (NEXT_PUBLIC_STRIPE_KEY), so this is
# used only to decide whether to mask the *value* - the name is always kept.
_SECRET_HINTS: Tuple[str, ...] = (
    "secret", "password", "passwd", "private", "credential",
    "token", "apikey", "api_key", "auth", "session",
)

REDACTED = "<redacted>"

# Trailing JS object noise that a lenient JSON pass may leave behind.
_TRAILING_COMMA = re.compile(r",\s*([}\]])")


def truncate(value: str, limit: int) -> str:
    """Shorten ``value`` to ``limit`` characters, marking that it was cut."""
    if not value:
        return ""
    value = value.strip()
    if limit <= 0 or len(value) <= limit:
        return value
    return value[: max(limit - 1, 1)] + "…"


def clamp(text: str, max_bytes: int) -> str:
    """Return at most ``max_bytes`` characters of ``text`` (0 = no cap).

    Characters, not bytes, are counted: the caller's caps exist to bound work
    and memory, and an exact byte count is not worth an encode round-trip.
    """
    if not text or max_bytes <= 0 or len(text) <= max_bytes:
        return text or ""
    return text[:max_bytes]


def safe_json_loads(text: str, max_bytes: int = 0) -> Optional[Any]:
    """Parse ``text`` as JSON, tolerating common embedded-payload quirks.

    Handles the shapes real pages emit: a bare JSON document, a payload wrapped
    in an assignment (``window.__NUXT__ = {...}``), and trailing commas. Returns
    ``None`` for anything that will not parse - callers fall back to regex
    scanning, which needs no structure.
    """
    if not text:
        return None
    if max_bytes and len(text) > max_bytes:
        return None
    candidate = text.strip()
    try:
        return json.loads(candidate)
    except (ValueError, TypeError):
        pass

    # Assignment wrapper: keep only the object/array literal.
    start = min(
        (i for i in (candidate.find("{"), candidate.find("[")) if i != -1),
        default=-1,
    )
    if start == -1:
        return None
    end = max(candidate.rfind("}"), candidate.rfind("]"))
    if end <= start:
        return None
    body = candidate[start: end + 1]
    for attempt in (body, _TRAILING_COMMA.sub(r"\1", body)):
        try:
            return json.loads(attempt)
        except (ValueError, TypeError):
            continue
    return None


def walk_json(data: Any, max_nodes: int) -> Iterator[Tuple[str, Any]]:
    """Yield ``(dotted_path, scalar_value)`` for a parsed JSON structure.

    Iterative (no recursion limit to blow) and hard-capped at ``max_nodes``
    visited nodes, so a deeply nested or enormous payload cannot stall the
    stage. Paths use ``a.b[0].c`` form and are what findings cite as evidence.
    """
    if data is None or max_nodes <= 0:
        return
    stack: List[Tuple[str, Any]] = [("", data)]
    visited = 0
    while stack and visited < max_nodes:
        path, node = stack.pop()
        visited += 1
        if isinstance(node, dict):
            for key, value in node.items():
                child = f"{path}.{key}" if path else str(key)
                stack.append((child, value))
        elif isinstance(node, (list, tuple)):
            for index, value in enumerate(node):
                stack.append((f"{path}[{index}]", value))
        else:
            yield path, node


def looks_like_secret(name: str, value: Any = None) -> bool:
    """Whether an env/config *name* suggests its value is a credential."""
    low = (name or "").lower()
    return any(hint in low for hint in _SECRET_HINTS)


def redact_value(name: str, value: Any, limit: int, enabled: bool = True) -> Optional[str]:
    """Return a reportable string for an env/config value.

    Masks values whose name looks secret-bearing (when ``enabled``), stringifies
    scalars, and refuses to inline whole objects/arrays - a nested structure is
    reported as its type, not dumped into the report.
    """
    if value is None:
        return None
    if enabled and looks_like_secret(name):
        return REDACTED
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return truncate(value, limit)
    if isinstance(value, dict):
        return f"<object:{len(value)} keys>"
    if isinstance(value, (list, tuple)):
        return f"<array:{len(value)} items>"
    return truncate(str(value), limit)


def is_public_env_name(name: str) -> bool:
    """Whether ``name`` carries a framework's client-exposed env prefix."""
    upper = (name or "").upper()
    return upper.startswith(PUBLIC_ENV_PREFIXES)


# Paths bundlers emit code-split chunks under, and the content-hashed filename
# shape they use (app.4f3a9c21.js, index-a1b2c3d4.mjs).
_CHUNK_PATHS: Tuple[str, ...] = (
    "/_next/static/chunks/", "/_next/static/", "/_nuxt/", "/chunks/",
    "/_app/immutable/", "/assets/", "/build/", "/static/js/",
)
_HASHED_CHUNK = re.compile(r"[-.][0-9a-f]{8,}\.m?js(\?|$)", re.IGNORECASE)


def looks_like_chunk(url: str) -> bool:
    """Whether a URL looks like a bundler-emitted, code-split chunk.

    Narrower on purpose than "is this JavaScript?": every ``<script src>`` is
    JavaScript, but only chunks belong in an import graph. Listing a site's
    analytics tags as dynamic imports would be noise, so this matches the
    tell-tale chunk directories and content-hashed filenames instead.
    """
    if not url:
        return False
    low = url.split("?", 1)[0].lower()
    if not low.endswith((".js", ".mjs")) and not any(
            marker in low for marker in _CHUNK_PATHS):
        return False
    return bool(_HASHED_CHUNK.search(url)) or any(
        marker in low for marker in _CHUNK_PATHS)


def dedupe(items: Iterable[str]) -> List[str]:
    """Order-preserving de-duplication of strings."""
    seen = set()
    out: List[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out
