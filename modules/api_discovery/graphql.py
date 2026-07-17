"""
WebIntelPro Enterprise X
API Discovery (Phase 2C) - GraphQL

Detects GraphQL through path shape, client-library signatures (Apollo, Relay,
urql, graphql-request, GraphQL Yoga), response headers, and JavaScript bundle
references. Introspection is read as a *hint*, never performed: this module
recognises that the page's own code constructs an introspection query (the
literal string ``__schema`` / ``IntrospectionQuery``), which is what "without
performing intrusive probing" requires -- it never issues one itself.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from technology.rules import RuleEngine, RuleResult

from .models import ApiKind, Candidate, DiscoverySource, RawSignal

# ---------------------------------------------------------------------------
# Well-known candidate paths (probed only when reachability probing is
# explicitly enabled).
# ---------------------------------------------------------------------------
GRAPHQL_CANDIDATES: List[Candidate] = [
    Candidate("/graphql", ApiKind.GRAPHQL, "graphql endpoint"),
    Candidate("/graphiql", ApiKind.GRAPHQL, "graphiql playground"),
    Candidate("/api/graphql", ApiKind.GRAPHQL, "graphql endpoint"),
]

# ---------------------------------------------------------------------------
# Path classification
# ---------------------------------------------------------------------------
_URL_SCHEMES = ("http://", "https://", "//")


def classify(value: str) -> Optional[ApiKind]:
    """Classify a string as a GraphQL endpoint, or ``None``.

    Deliberately narrow: ``graphql`` appearing anywhere in the path, or a
    ``/gql`` path segment (the common short alias), both read as GraphQL
    regardless of what other path segments (``/api/``) surround them -- the
    most specific classification wins, matching
    :func:`technology.runtime.parser.classify_endpoint`'s precedence rule.
    """
    if not value:
        return None
    candidate = value.strip()
    if len(candidate) < 2 or " " in candidate or "\t" in candidate:
        return None
    low = candidate.lower()
    if not (low.startswith("/") or low.startswith(_URL_SCHEMES)):
        return None
    if "graphql" in low:
        return ApiKind.GRAPHQL
    path = low.split("?", 1)[0].split("#", 1)[0]
    if path.endswith("/gql") or "/gql/" in path:
        return ApiKind.GRAPHQL
    return None


# ---------------------------------------------------------------------------
# Client-library and introspection signatures
# ---------------------------------------------------------------------------
_SIGNATURES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("Apollo Client", (
        "@apollo/client", "apolloclient(", "apollolink", "inmemorycache(",
        "usequery(", "usemutation(",
    )),
    ("Relay", (
        "relay-runtime", "relayenvironment", "relaymodernrecord",
        "commitmutation(", "requestsubscription(",
    )),
    ("urql", (
        "@urql/core", "@urql/preact", "createclient({url", "usequery({query",
    )),
    ("graphql-request", (
        "graphql-request", "new graphqlclient(",
    )),
    ("GraphQL Yoga", (
        "graphql-yoga", "createyoga(",
    )),
    ("gql tag", (
        "graphql-tag", "gql`",
    )),
    ("Introspection", (
        "introspectionquery", "__schema", "queryplan.getintrospectionquery",
    )),
)

# Response headers that name GraphQL, seen from either the client library or
# the server implementation.
_HEADER_HINTS: Tuple[str, ...] = (
    "x-graphql", "apollo-require-preflight", "graphql-query",
    "x-apollo-operation-name", "x-apollo-operation-id",
)


def scan_signatures(text: str, engine: RuleEngine) -> List[RawSignal]:
    """Match GraphQL client-library and introspection markers in ``text``."""
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
                name=name, kind=ApiKind.GRAPHQL,
                evidence=sorted(set(result.evidence)),
                details={"technology": name} if name != "Introspection"
                        else {"capability": "introspection-hint"},
            ))
    return signals


def scan_headers(headers: Dict[str, str]) -> List[RawSignal]:
    """Match GraphQL-specific response header names.

    ``headers`` is whatever the caller already fetched for the page (no
    request is made here) -- header names only are matched, values are not
    inspected, so this cannot leak credential-bearing header content.
    """
    if not headers:
        return []
    signals: List[RawSignal] = []
    for header_name in headers:
        low = header_name.lower()
        for hint in _HEADER_HINTS:
            if hint in low:
                signals.append(RawSignal(
                    name="GraphQL response header", kind=ApiKind.GRAPHQL,
                    evidence=[header_name],
                    details={"source": DiscoverySource.HEADER.value},
                ))
                break
    return signals
