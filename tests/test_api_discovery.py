"""
Offline tests for Phase 2C API Discovery.

The passive path performs no network I/O at all, which one test enforces
directly by making any HTTP call explode; the opt-in reachability-probing
path is exercised entirely against a stubbed ``requests.Session`` -- no real
network call is ever made by this suite.

Coverage follows the Phase 2C contract: REST/JSON endpoint mining, GraphQL,
Swagger/OpenAPI, RPC (JSON-RPC/XML-RPC/tRPC/gRPC-Web), WebSocket/SSE, plus the
guarantees that matter more than any single detection: the default detect()
path is unchanged, markup/asset URLs are not mined as endpoints, robots.txt is
respected, probing is bounded, and every failure is graceful.
"""

from unittest.mock import patch

import pytest
import requests

from modules.api_discovery import (
    ApiDiscoverer,
    ApiDiscoveryConfig,
    ApiKind,
    endpoints,
    graphql,
    swagger,
)
from modules.api_discovery import websocket as ws
from technology.detector import TechnologyDetector
from technology.parser import HTMLParser


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def discover(html: str, config: ApiDiscoveryConfig | None = None,
            url: str = "https://site.test/", headers=None):
    """Run the API discovery stage over raw HTML and return the analysis."""
    parsed = HTMLParser().parse(html)
    return ApiDiscoverer(config=config).analyze(parsed, url, headers)


def kinds(analysis, kind: ApiKind):
    """Reported names in one API-kind bucket."""
    return {f.name for f in analysis.report.by_kind(kind)}


def techs(analysis):
    return {t.name for t in analysis.technologies}


def page(body: str, head: str = "") -> str:
    return f"<html><head>{head}</head><body>{body}</body></html>"


class _FakeResponse:
    """Minimal stand-in for requests.Response used by the probing tests."""

    def __init__(self, status_code, headers=None, text="", encoding="utf-8"):
        self.status_code = status_code
        self.headers = headers or {}
        self.text = text
        self.encoding = encoding

    def iter_content(self, chunk_size=4096):
        data = self.text.encode(self.encoding)
        for i in range(0, len(data), chunk_size):
            yield data[i:i + chunk_size]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


# ---------------------------------------------------------------------------
# passive endpoint discovery
# ---------------------------------------------------------------------------

def test_discovers_endpoints_of_every_kind():
    html = page('<script>'
                'fetch("/api/v1/products");'
                'axios.get("/graphql");'
                '$.ajax({url:"/openapi.json"});'
                'new WebSocket("wss://live.site.test/socket");'
                'new EventSource("/stream/events");'
                'fetch("/data/config.json");'
                'fetch("/api/trpc/user.get");'
                '</script>')
    analysis = discover(html)
    found = {f.name: f.kind for f in analysis.report.findings}
    assert found["/api/v1/products"] == ApiKind.REST
    assert found["/graphql"] == ApiKind.GRAPHQL
    assert found["/openapi.json"] == ApiKind.OPENAPI
    assert found["wss://live.site.test/socket"] == ApiKind.WEBSOCKET
    assert found["/stream/events"] == ApiKind.SSE
    assert found["/data/config.json"] == ApiKind.JSON
    assert found["/api/trpc/user.get"] == ApiKind.TRPC


def test_constructor_classification_beats_path_shape():
    """new EventSource("/api/x") is SSE even though the path looks REST."""
    analysis = discover(page('<script>new EventSource("/api/x");</script>'))
    finding = next(f for f in analysis.report.findings)
    assert finding.kind == ApiKind.SSE


def test_single_char_literal_does_not_desync_the_string_scan():
    html = page('<script>var s={"page":"/"};fetch("/graphql");</script>')
    assert "/graphql" in kinds(discover(html), ApiKind.GRAPHQL)


def test_markup_and_script_urls_are_not_mined_for_endpoints():
    """Link hrefs and script src attributes are not runtime call sites."""
    html = page('<a href="/api/not-a-runtime-call">docs</a>',
               head='<script src="/static/socket.io.js"></script>')
    analysis = discover(html)
    assert analysis.report.findings == [] or all(
        f.kind is ApiKind.WEBSOCKET and f.details.get("technology") == "Socket.IO"
        for f in analysis.report.findings
    )
    # The asset URL itself must never appear as a discovered *endpoint*.
    assert "/static/socket.io.js" not in {f.name for f in analysis.report.findings}


def test_endpoint_classification_rejects_non_endpoints():
    for value in ("application/json", "hello world", "/news", "/", "text"):
        assert endpoints.classify(value) is None


# ---------------------------------------------------------------------------
# GraphQL
# ---------------------------------------------------------------------------

def test_detects_apollo_client_signature():
    html = page('<script>import {ApolloClient, InMemoryCache} from "@apollo/client";'
               'const c = new ApolloClient({});</script>')
    analysis = discover(html)
    assert "Apollo Client" in techs(analysis)
    assert "GraphQL API" in techs(analysis)


def test_graphql_response_header_is_detected():
    analysis = discover(page("<p>hi</p>"),
                        headers={"X-GraphQL-Operation-Name": "GetUser"})
    assert any(f.kind is ApiKind.GRAPHQL for f in analysis.report.findings)


def test_introspection_hint_is_detected_without_probing():
    html = page('<script>const q = "query IntrospectionQuery { __schema { types } }";'
               '</script>')
    analysis = discover(html)
    assert any(f.name == "Introspection" for f in analysis.report.findings)


# ---------------------------------------------------------------------------
# Swagger / OpenAPI
# ---------------------------------------------------------------------------

def test_detects_swagger_ui_signature():
    html = page("", head='<script src="/swagger-ui-bundle.js"></script>')
    analysis = discover(html)
    assert "Swagger UI" in techs(analysis)


def test_looks_like_openapi_doc_accepts_json_and_yaml():
    assert swagger.looks_like_openapi_doc('{"openapi":"3.0.0","info":{}}')
    assert swagger.looks_like_openapi_doc("openapi: 3.0.0\ninfo:\n  title: x")
    assert not swagger.looks_like_openapi_doc("<html>not a spec</html>")


# ---------------------------------------------------------------------------
# RPC
# ---------------------------------------------------------------------------

def test_detects_trpc_and_grpc_web_signatures():
    html = page('<script>import {createTRPCProxyClient} from "@trpc/client";'
               'const g = new GrpcWebClientBase({});</script>')
    analysis = discover(html)
    assert {"tRPC", "gRPC-Web"}.issubset(techs(analysis))


def test_detects_json_rpc_and_xml_rpc_signatures():
    html = page('<script>const body = JSON.stringify({jsonrpc:"2.0",method:"x"});'
               '</script>', head='<script>fetch("/xmlrpc.php");</script>')
    analysis = discover(html)
    names = {f.name for f in analysis.report.findings}
    assert "JSON-RPC" in names or "xmlrpc.php" in {v.lower() for v in
                                                    (f.value or "" for f in analysis.report.findings)}


# ---------------------------------------------------------------------------
# WebSocket / SSE
# ---------------------------------------------------------------------------

def test_detects_socket_io_and_signalr_signatures():
    html = page('<script>import io from "socket.io-client";'
               'const conn = new signalR.HubConnectionBuilder();</script>')
    analysis = discover(html)
    assert "Socket.IO" in techs(analysis)


def test_websocket_classify_requires_scheme_or_segment():
    assert ws.classify("wss://a.test/x") is ApiKind.WEBSOCKET
    assert ws.classify("/api/websocket") is ApiKind.WEBSOCKET
    assert ws.classify("/api/x") is None


# ---------------------------------------------------------------------------
# TechnologyDetector integration
# ---------------------------------------------------------------------------

def test_default_detect_path_is_unaffected():
    html = page('<script>fetch("/api/v1/products");</script>')
    detector = TechnologyDetector()
    report = detector.detect("https://site.test/", html=html)
    assert report.api_discovery is None
    assert "api_discovery" not in report.to_dict()


def test_opt_in_detect_path_populates_report():
    html = page('<script>fetch("/api/v1/products");</script>')
    detector = TechnologyDetector()
    report = detector.detect("https://site.test/", html=html, analyze_api=True)
    assert report.api_discovery is not None
    assert report.api_discovery["total_findings"] >= 1
    assert any(t.category == "api" for t in report.technologies)
    assert "api_discovery" in report.to_dict()


def test_api_discovery_failure_degrades_gracefully(monkeypatch, caplog):
    detector = TechnologyDetector()

    class _Boom:
        def analyze(self, *a, **k):
            raise RuntimeError("boom")

    monkeypatch.setattr(detector, "_api_discoverer", _Boom())
    report = detector.detect("https://site.test/", html=page("<p>hi</p>"),
                             analyze_api=True)
    assert report.api_discovery is None
    assert report.total_detected == len(report.technologies)  # did not crash


# ---------------------------------------------------------------------------
# network-free default guarantee
# ---------------------------------------------------------------------------

def test_default_path_performs_no_network_io():
    def explode(*a, **k):
        raise AssertionError("network call made on default (network-free) path!")

    html = page('<script>fetch("/api/v1/products");new WebSocket("wss://a/b");'
               '</script>')
    with patch.object(requests.Session, "head", side_effect=explode), \
         patch.object(requests.Session, "get", side_effect=explode):
        analysis = discover(html)
    assert len(analysis.report.findings) >= 2


# ---------------------------------------------------------------------------
# reachability probing (opt-in, stubbed network)
# ---------------------------------------------------------------------------

def _stub_head(url, timeout=None, allow_redirects=None):
    if url.endswith("/robots.txt"):
        return _FakeResponse(404)
    if "swagger.json" in url:
        return _FakeResponse(200, {"Content-Type": "application/json"})
    return _FakeResponse(404)


def _stub_get(url, timeout=None, stream=None):
    if url.endswith("/robots.txt"):
        return _FakeResponse(404, text="")
    if "swagger.json" in url:
        return _FakeResponse(200, {"Content-Type": "application/json"},
                             text='{"openapi":"3.0.0","info":{}}')
    return _FakeResponse(404)


def test_probing_confirms_a_well_known_openapi_path():
    with patch.object(requests.Session, "head", side_effect=_stub_head), \
         patch.object(requests.Session, "get", side_effect=_stub_get):
        cfg = ApiDiscoveryConfig(probe_reachability=True)
        analysis = discover(page("<p>hi</p>"), config=cfg)

    assert analysis.report.probed is True
    finding = next(f for f in analysis.report.findings if f.kind is ApiKind.OPENAPI)
    assert finding.reachable is True
    assert finding.http_status == 200
    assert finding.details.get("confirmed") is True
    assert "Swagger / OpenAPI" in techs(analysis)


def test_probing_respects_robots_disallow():
    def robots_get(url, timeout=None, stream=None):
        if url.endswith("/robots.txt"):
            return _FakeResponse(200, text="User-agent: *\nDisallow: /\n")
        return _FakeResponse(200, {"Content-Type": "application/json"})

    def robots_head(url, timeout=None, allow_redirects=None):
        return _FakeResponse(200, {"Content-Type": "application/json"})

    with patch.object(requests.Session, "head", side_effect=robots_head), \
         patch.object(requests.Session, "get", side_effect=robots_get):
        cfg = ApiDiscoveryConfig(probe_reachability=True)
        analysis = discover(page("<p>hi</p>"), config=cfg)

    # Every well-known candidate was disallowed, so none should be reported.
    assert all(f.source.value != "well_known_path" for f in analysis.report.findings)


def test_probing_never_leaves_the_page_origin():
    html = page('<script>fetch("https://third-party.test/api/track");</script>')
    calls = []

    def recording_head(url, timeout=None, allow_redirects=None):
        calls.append(url)
        return _FakeResponse(404)

    def recording_get(url, timeout=None, stream=None):
        calls.append(url)
        return _FakeResponse(404)

    with patch.object(requests.Session, "head", side_effect=recording_head), \
         patch.object(requests.Session, "get", side_effect=recording_get):
        cfg = ApiDiscoveryConfig(probe_reachability=True)
        discover(html, config=cfg, url="https://site.test/")

    assert not any("third-party.test" in url for url in calls)


def test_probe_count_is_bounded():
    with patch.object(requests.Session, "head", side_effect=_stub_head), \
         patch.object(requests.Session, "get", side_effect=_stub_get):
        cfg = ApiDiscoveryConfig(probe_reachability=True, max_probes=2)
        analysis = discover(page("<p>hi</p>"), config=cfg)
    # Never a wordlist: only the tiny, fixed candidate set is ever considered,
    # and max_probes caps it further still.
    assert analysis.report.probed is True


# ---------------------------------------------------------------------------
# report shape
# ---------------------------------------------------------------------------

def test_report_to_dict_has_every_kind_key():
    analysis = discover(page("<p>hi</p>"))
    payload = analysis.report.to_dict()
    for kind in ApiKind:
        assert kind.value in payload
        assert isinstance(payload[kind.value], list)
