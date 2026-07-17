"""
WebIntelPro Enterprise X
JavaScript Runtime Intelligence (Phase 2B) - Parsing primitives

Mechanical, meaning-free extraction from JavaScript-ish text. This module knows
*syntax* - how a global is referenced, where a quoted string sits, what an
object literal's extent is - and deliberately knows nothing about which
technology any of it implies. That judgement belongs to :mod:`detector`, which
builds on these primitives.

The split matters for extensibility: teaching the stage about a new framework
means adding a signature in :mod:`detector`, never touching the parsing here.

Everything is regex-based and bounded. No JavaScript is executed, no browser is
involved, and no input can make a primitive raise: unparseable text simply
yields no signals.
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional

from .models import EndpointKind, RawSignal, RuntimeConfig
from .utils import (
    dedupe,
    is_public_env_name,
    redact_value,
    safe_json_loads,
    truncate,
    walk_json,
)

logger = logging.getLogger("webintelpro.runtime.parser")

# ---------------------------------------------------------------------------
# Syntactic patterns
# ---------------------------------------------------------------------------

# A quoted string literal (single, double or backtick).
#
# The backreference is load-bearing, and so is allowing empty/1-char content:
# this scanner walks a whole script sequentially, so every literal must pair
# with its own opening quote type and no literal may be skipped. A minimum
# length here would desynchronise the scan - a 1-char literal like the "/" in
# {"page":"/"} would be missed, its closing quote would then be read as the
# *opening* quote of the next literal, and every string after it on the line
# would be misparsed. Length is filtered afterwards, in Python.
#
# The alternation consumes each character exactly once (escape, or a non-quote
# non-escape), so it cannot backtrack catastrophically.
_QUOTED = re.compile(r"""(['"`])((?:\\.|(?!\1)[^\\\n])*)\1""")

# new WebSocket("...") / new EventSource("...") - the call itself classifies the
# endpoint, independently of what its path happens to look like.
_CONSTRUCTOR = re.compile(
    r"""new\s+(WebSocket|EventSource)\s*\(\s*['"`]([^'"`\n]{1,300})['"`]""",
    re.IGNORECASE,
)

# process.env.FOO / process.env["FOO"] / import.meta.env.FOO
_PROCESS_ENV = re.compile(r"""process\s*\.\s*env\s*\.\s*([A-Za-z_$][\w$]*)""")
_PROCESS_ENV_INDEX = re.compile(
    r"""process\s*\.\s*env\s*\[\s*['"]([^'"\]]{1,80})['"]\s*\]"""
)
_IMPORT_META_ENV = re.compile(
    r"""import\s*\.\s*meta\s*\.\s*env\s*\.\s*([A-Za-z_$][\w$]*)"""
)

# import("./chunk-abc.js") and import(`...`) - dynamic module specifiers.
_DYNAMIC_IMPORT = re.compile(r"""import\s*\(\s*['"`]([^'"`\n]{1,300})['"`]\s*\)""")

# Cache the per-name global accessor patterns; a page is scanned against the
# same signature set repeatedly, and these are rebuilt per unit otherwise.
_GLOBAL_CACHE: dict = {}

_URL_SCHEMES = ("http://", "https://", "ws://", "wss://", "//")


def present(token: str, lowered_text: str) -> bool:
    """Fast, case-insensitive "could this token possibly match?" pre-filter.

    Every matcher in this package - the accessor regexes here, and the shared
    RuleEngine's word-boundary and substring modes alike - can only match where
    the raw token appears literally in the text. So a failed substring test is a
    guaranteed non-match, which makes this a **safe superset**: it can never
    turn a real match into a miss.

    It exists purely for speed, and it is not a micro-optimisation. Scanning a
    unit means testing ~80 globals and ~150 patterns; without this gate each one
    costs a full regex pass over the whole text, and a large embedded payload
    then takes ~1 second on its own. A C-speed ``in`` test rejects nearly all of
    them up front.

    ``lowered_text`` must already be lowercased by the caller (once per unit).
    """
    return token.lower() in lowered_text


def global_pattern(name: str, allow_bare: bool) -> re.Pattern:
    """Return a compiled pattern matching references to a JS global ``name``.

    Always matches explicit accessor forms (``window.__NUXT__``,
    ``self["__NUXT__"]``, ``globalThis.__NUXT__``). When ``allow_bare`` is set,
    also matches the bare identifier, which is how dunder payloads appear in
    markup (``id="__NEXT_DATA__"``) and in minified code that aliases ``window``.

    Matching is **case-sensitive**, because JavaScript identifiers are:
    ``window.ENV`` and ``window.env`` are different globals, and ``__NEXT_F``
    (App Router) is not ``__next_f``. Folding case here would silently report
    globals the page never referenced.

    ``allow_bare`` must stay off for short, English-like globals (``React``,
    ``Vue``, ``angular``) or prose and unrelated identifiers would match.
    """
    key = (name, allow_bare)
    cached = _GLOBAL_CACHE.get(key)
    if cached is not None:
        return cached
    escaped = re.escape(name)
    accessor = (
        r"(?:window|self|globalThis|top|parent)\s*"
        rf"(?:\.\s*{escaped}(?![\w$])|\[\s*['\"]{escaped}['\"]\s*\])"
    )
    if allow_bare:
        pattern = rf"(?:{accessor}|(?<![\w$.]){escaped}(?![\w$]))"
    else:
        pattern = accessor
    compiled = re.compile(pattern)
    _GLOBAL_CACHE[key] = compiled
    return compiled


class RuntimeParser:
    """Extracts structured signals from a single unit of code text.

    Each ``find_*`` method returns a list of :class:`RawSignal`, capped by the
    supplied :class:`RuntimeConfig`. Methods are pure and stateless; the same
    parser instance is safely reused across units and pages.
    """

    def __init__(self, config: RuntimeConfig | None = None):
        self.config = config or RuntimeConfig()

    # ------------------------------------------------------------------
    # Globals
    # ------------------------------------------------------------------
    def find_global(self, text: str, name: str,
                    allow_bare: bool = True) -> Optional[str]:
        """Return the matched snippet for global ``name``, or ``None``.

        The snippet (not just a boolean) is returned so findings can quote the
        exact reference form that was observed as their evidence.
        """
        if not text or not name:
            return None
        match = global_pattern(name, allow_bare).search(text)
        if not match:
            return None
        return truncate(match.group(0), 80)

    # ------------------------------------------------------------------
    # API endpoints
    # ------------------------------------------------------------------
    def find_endpoints(self, text: str) -> List[RawSignal]:
        """Discover REST/GraphQL/WebSocket/SSE/JSON/OpenAPI endpoints.

        Two passes: constructor calls (which self-classify) and quoted string
        literals (classified by shape). Results are de-duplicated by URL, with
        the strongest classification kept.
        """
        if not text:
            return []
        signals: dict = {}

        for match in _CONSTRUCTOR.finditer(text):
            ctor, url = match.group(1).lower(), match.group(2)
            kind = EndpointKind.WEBSOCKET if ctor == "websocket" else EndpointKind.SSE
            self._add_endpoint(signals, url, kind, truncate(match.group(0), 100))

        seen = 0
        for match in _QUOTED.finditer(text):
            seen += 1
            if seen > self.config.max_strings_per_unit:
                logger.debug("string scan capped at %d", self.config.max_strings_per_unit)
                break
            value = match.group(2)
            if not 2 <= len(value) <= self.config.max_string_literal_length:
                continue
            kind = classify_endpoint(value)
            if kind is not None:
                self._add_endpoint(signals, value, kind, value)
            if len(signals) >= self.config.max_findings_per_kind:
                break

        return list(signals.values())

    def find_endpoints_in_json(self, data) -> List[RawSignal]:
        """Discover endpoints among the string values of a parsed JSON payload.

        Framework payloads (``__NEXT_DATA__``, ``__NUXT__``) routinely carry the
        API base URLs the client will call. The JSON path is used as evidence,
        which is far more useful than the bare string.
        """
        signals: dict = {}
        for path, value in walk_json(data, self.config.max_json_nodes):
            if not isinstance(value, str):
                continue
            kind = classify_endpoint(value)
            if kind is None:
                continue
            self._add_endpoint(signals, value, kind, f"{path}={truncate(value, 80)}")
            if len(signals) >= self.config.max_findings_per_kind:
                break
        return list(signals.values())

    def _add_endpoint(self, signals: dict, url: str, kind: EndpointKind,
                      evidence: str) -> None:
        url = truncate(url.strip(), self.config.max_value_length)
        if not url:
            return
        existing = signals.get(url)
        if existing is None:
            signals[url] = RawSignal(name=url, value=url, evidence=[evidence],
                                     details={"kind": kind.value})
        elif evidence not in existing.evidence:
            existing.evidence.append(evidence)

    # ------------------------------------------------------------------
    # Environment variables
    # ------------------------------------------------------------------
    def find_env_vars(self, text: str) -> List[RawSignal]:
        """Find ``process.env.X`` / ``import.meta.env.X`` accessor names.

        Only names are recoverable this way - bundlers inline the *values* at
        build time, so an accessor surviving in shipped code usually means the
        variable is read at runtime. Values, when present, come from
        :meth:`find_env_in_json` instead.
        """
        if not text:
            return []
        signals: dict = {}
        for pattern, form in ((_PROCESS_ENV, "process.env"),
                              (_PROCESS_ENV_INDEX, "process.env"),
                              (_IMPORT_META_ENV, "import.meta.env")):
            for match in pattern.finditer(text):
                name = match.group(1)
                if not name or name in signals:
                    continue
                signals[name] = RawSignal(
                    name=name,
                    value=None,
                    evidence=[truncate(match.group(0), 80)],
                    details={"accessor": form, "public": is_public_env_name(name)},
                )
                if len(signals) >= self.config.max_findings_per_kind:
                    return list(signals.values())
        return list(signals.values())

    def find_env_in_json(self, data) -> List[RawSignal]:
        """Find public-prefixed env names *with values* inside parsed JSON.

        Restricted to names carrying a framework's client-exposed prefix
        (``NEXT_PUBLIC_``, ``VITE_``, ...): those are public by construction.
        Values are still passed through redaction, because a secret-looking name
        under a public prefix is a real (and worth-reporting) mistake - the name
        is reported, the value is masked.
        """
        signals: dict = {}
        for path, value in walk_json(data, self.config.max_json_nodes):
            key = path.rsplit(".", 1)[-1]
            if not key or not is_public_env_name(key):
                continue
            if key in signals:
                continue
            signals[key] = RawSignal(
                name=key,
                value=redact_value(key, value, self.config.max_value_length,
                                   self.config.redact_secrets),
                evidence=[truncate(path, 100)],
                details={"public": True},
            )
            if len(signals) >= self.config.max_findings_per_kind:
                break
        return list(signals.values())

    # ------------------------------------------------------------------
    # Runtime configuration objects
    # ------------------------------------------------------------------
    def find_config_object(self, text: str, name: str,
                           allow_bare: bool = True) -> Optional[RawSignal]:
        """Extract the object literal assigned to a runtime-config global.

        Handles ``window.__ENV__ = { ... }`` and friends by locating the
        assignment and taking the balanced literal that follows. The literal is
        JSON-parsed when possible so its keys can be reported; when it is not
        valid JSON (a JS literal with unquoted keys, say), the finding still
        stands on the assignment itself, just without key detail.
        """
        if not text or not name:
            return None
        pattern = global_pattern(name, allow_bare)
        match = pattern.search(text)
        if not match:
            return None
        tail = text[match.end():]
        literal = extract_object_literal(tail, self.config.max_json_bytes)
        details = {}
        if literal:
            data = safe_json_loads(literal, self.config.max_json_bytes)
            if isinstance(data, dict):
                details["keys"] = sorted(data.keys())[: self.config.max_findings_per_kind]
        return RawSignal(
            name=name,
            value=truncate(literal, self.config.max_value_length) or None,
            evidence=[truncate(match.group(0), 80)],
            details=details,
        )

    # ------------------------------------------------------------------
    # Dynamic imports
    # ------------------------------------------------------------------
    def find_dynamic_imports(self, text: str) -> List[RawSignal]:
        """Return the specifiers of ``import("...")`` calls found in ``text``."""
        if not text:
            return []
        specifiers = dedupe(
            m.group(1) for m in _DYNAMIC_IMPORT.finditer(text)
        )[: self.config.max_findings_per_kind]
        return [
            RawSignal(name=truncate(spec, self.config.max_value_length),
                      value=truncate(spec, self.config.max_value_length),
                      evidence=[f'import("{truncate(spec, 80)}")'],
                      details={"form": "dynamic-import"})
            for spec in specifiers
        ]


# ---------------------------------------------------------------------------
# Module-level primitives
# ---------------------------------------------------------------------------

def classify_endpoint(value: str) -> Optional[EndpointKind]:
    """Classify a string literal as an API endpoint, or ``None``.

    Order matters: the most specific classification wins, so ``/graphql`` is
    GraphQL rather than REST even when served under ``/api/``.

    A candidate must look like a path or URL (leading ``/`` or a known scheme)
    and contain no whitespace. That single guard removes the bulk of false
    positives - MIME types (``application/json``), CSS values and prose all fail
    it while real endpoints pass.
    """
    if not value:
        return None
    candidate = value.strip()
    if len(candidate) < 2 or " " in candidate or "\t" in candidate:
        return None
    low = candidate.lower()
    if not (low.startswith("/") or low.startswith(_URL_SCHEMES)):
        return None
    # Protocol-relative and absolute URLs are fine; a bare "//" comment is not.
    if low.startswith("//") and len(low) < 5:
        return None

    if low.startswith(("ws://", "wss://")) or "/socket.io" in low \
            or "/websocket" in low or _has_segment(low, "ws"):
        return EndpointKind.WEBSOCKET
    if "graphql" in low or _has_segment(low, "gql"):
        return EndpointKind.GRAPHQL
    if "openapi" in low or "swagger" in low or "/api-docs" in low:
        return EndpointKind.OPENAPI
    if "event-stream" in low or _has_segment(low, "sse") or "/eventsource" in low:
        return EndpointKind.SSE
    if "/api/" in low or low.endswith("/api") or "/rest/" in low or "/v1/" in low:
        return EndpointKind.REST
    if low.endswith(".json") or ".json?" in low:
        return EndpointKind.JSON
    return None


def _has_segment(url: str, segment: str) -> bool:
    """Whether ``url`` contains ``segment`` as a whole path segment.

    Prevents ``/ws`` from matching ``/wsdl`` or ``/news``, which is the
    difference between a WebSocket finding and a false positive.
    """
    path = url.split("?", 1)[0].split("#", 1)[0]
    return f"/{segment}" == path[-len(segment) - 1:] or f"/{segment}/" in path


def extract_object_literal(text: str, max_bytes: int) -> str:
    """Return the first balanced ``{...}`` literal at the head of ``text``.

    Brace-counting scanner that is quote-aware (braces inside strings do not
    count) and escape-aware. Bounded by ``max_bytes``; returns an empty string
    if the literal does not start within a short lookahead, never closes, or
    exceeds the cap - all of which are "no finding", not errors.
    """
    if not text:
        return ""
    window = text[:max_bytes] if max_bytes else text
    head = window[:40].lstrip()
    if not head.startswith(("=", "{")):
        # Allow "= {", "={" and a direct literal; anything else is not an
        # assignment of an object we can read.
        return ""
    start = window.find("{")
    if start == -1 or start > 40:
        return ""

    depth = 0
    quote = ""
    escaped = False
    for index in range(start, len(window)):
        char = window[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if quote:
            if char == quote:
                quote = ""
            continue
        if char in "\"'`":
            quote = char
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return window[start: index + 1]
    return ""
