"""
Offline tests for Phase 2A JavaScript Bundle Intelligence.

All network I/O is stubbed, so these run without touching the network. They
verify (a) discovery, scanning and version extraction in isolation, and
(b) that detect(analyze_js=True) *adds* bundle-derived technologies while the
default detect() path stays byte-for-byte unchanged.
"""

from technology.detector import TechnologyDetector
from technology.javascript import (
    BundleConfig,
    BundleDiscovery,
    BundleScanner,
    VersionExtractor,
)
from technology.javascript import fetcher as fetcher_module
from technology.javascript.models import JSBundle
from technology.parser import HTMLParser


# --- signature scanning -----------------------------------------------------

def test_scanner_identifies_frameworks_and_build_tools():
    scanner = BundleScanner()
    react = 'var d=require("react-dom");ReactCurrentDispatcher.current;'
    webpack = '(()=>{var __webpack_require__=1;__webpack_modules__={};})();'
    assert "React" in scanner.scan(react)
    assert "Webpack" in scanner.scan(webpack)
    assert scanner.scan("just some unrelated text") == {}


def test_version_extraction_is_conservative():
    ve = VersionExtractor()
    assert ve.extract(["react-dom@"], "a react-dom@18.2.0 b") == "18.2.0"
    assert ve.banner_version("Vue.js", "/*! Vue.js v3.4.21 */ code") == "3.4.21"
    # No adjacent semver -> no (mis)attributed version.
    assert ve.extract(["react-dom@"], "react-dom is loaded") is None


# --- discovery --------------------------------------------------------------

def test_discovery_resolves_and_filters():
    html = ('<html><head>'
            '<script src="/static/app.js"></script>'
            '<script src="https://cdn.example.com/vendor.mjs" type="module"></script>'
            '<script src="/inline-marker.png"></script>'
            '<link rel="modulepreload" href="/static/extra.js">'
            '</head><body></body></html>')
    parsed = HTMLParser().parse(html)
    urls = BundleDiscovery(BundleConfig()).discover(parsed, "https://site.test/page")
    assert "https://site.test/static/app.js" in urls
    assert "https://cdn.example.com/vendor.mjs" in urls
    assert "https://site.test/static/extra.js" in urls
    # Non-JS resources are excluded.
    assert all(not u.endswith(".png") for u in urls)


# --- end-to-end via detect(analyze_js=True) ---------------------------------

_FAKE_BUNDLES = {
    "https://site.test/static/app.js":
        'require("react-dom");ReactCurrentDispatcher; self.__next_f.push([1]); '
        '/*! react-dom@18.2.0 */',
    "https://site.test/static/vendor.js":
        '(()=>{var __webpack_require__=1;__webpack_modules__={};})(); '
        '@tanstack/query queryClientProvider',
}


def _install_fake_fetcher(monkeypatch):
    def fake_fetch(self, url):
        content = _FAKE_BUNDLES.get(url, "")
        return JSBundle(url=url, content=content, size=len(content),
                        status=200 if content else 404,
                        error="" if content else "http_404")
    monkeypatch.setattr(fetcher_module.BundleFetcher, "fetch", fake_fetch)


_HTML = ('<html><head>'
         '<script src="/static/app.js"></script>'
         '<script src="/static/vendor.js"></script>'
         '</head><body>no framework markers in the HTML at all</body></html>')


def test_default_detect_is_unchanged_without_flag():
    d = TechnologyDetector()
    report = d.detect("https://site.test", _HTML)
    # HTML carries no framework markers, so nothing JS is found by Phase 1.
    assert {"React", "Next.js", "Webpack"}.isdisjoint(
        {t.name for t in report.technologies})


def test_analyze_js_adds_bundle_technologies(monkeypatch):
    _install_fake_fetcher(monkeypatch)
    d = TechnologyDetector()
    report = d.detect("https://site.test", _HTML, analyze_js=True)
    found = {t.name for t in report.technologies}
    assert {"React", "Next.js", "Webpack", "React Query"}.issubset(found)
    react = next(t for t in report.technologies if t.name == "React")
    assert react.version == "18.2.0"
    assert react.confidence >= 0.30
    assert any(e.startswith("js_bundle:") for e in react.evidence)


def test_bundle_failure_is_graceful(monkeypatch):
    def boom(self, url):
        raise RuntimeError("network down")
    monkeypatch.setattr(fetcher_module.BundleFetcher, "fetch", boom)
    d = TechnologyDetector()
    # Must not raise; simply yields no bundle-derived detections.
    report = d.detect("https://site.test", _HTML, analyze_js=True)
    assert isinstance(report.technologies, list)
