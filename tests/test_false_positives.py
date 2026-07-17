"""Regression tests for the word-boundary matching that prevents generic
substring false positives (e.g. 'ember' inside 'remember')."""

from technology.detector import TechnologyDetector
from technology.rules import RuleEngine


def names(report):
    return {t.name for t in report.technologies}


def test_word_boundary_matching():
    # plain-word signature must respect boundaries
    assert RuleEngine.match(["ember"], "remember september").matched is False
    assert RuleEngine.match(["ember"], "the ember glow").matched is True
    # delimiter signatures keep substring matching
    assert RuleEngine.match(["wp-content"], "/wp-content/x").matched is True
    # header value still matches (bounded by ':' and '/')
    assert RuleEngine.match(["nginx"], "server:nginx/1.25.3").matched is True


def test_no_false_positives_on_trap_page():
    d = TechnologyDetector()
    html = ("<html lang='en'><head><title>OpenAI</title>"
            "<meta name='description' content='remember to render pages, amp is loud'>"
            "<script src='/_next/static/chunks/main.js'></script>"
            "<script>function prerender(){} var member=\"september\";</script>"
            "</head><body class='remember-panel'><div id='__next'></div></body></html>")
    headers = {"Server": "Vercel", "X-Vercel-Id": "iad1"}
    found = names(d.detect("https://openai.com", html, headers, {}))
    for bad in ["Ember.js", "Render", "Adobe Experience Manager",
                "Contentful", "Google AMP", "Google Cloud"]:
        assert bad not in found, f"false positive: {bad}"
    assert "Next.js" in found  # real signal still detected


def test_genuine_signals_still_detected():
    d = TechnologyDetector()
    html = ("<html><head><script src='/assets/ember.debug.js'></script>"
            "<script src='https://cdn.contentful.com/x.js'></script>"
            "</head><body class='ember-application'></body></html>")
    headers = {"x-render-origin-server": "Render", "server": "nginx/1.25.3"}
    found = names(d.detect("https://x.com", html, headers, {}))
    assert {"Ember.js", "Render", "Contentful", "Nginx"} <= found


def test_no_false_positive_on_kebab_class_names():
    # "sofa-section" / "raw-data" style classes must not trigger 2-3 char
    # substring signals ("fa-" -> Font Awesome, "aw-" -> Google Ads).
    d = TechnologyDetector()
    html = ("<html><head></head><body class='sofa-section'>"
            "<div class='raw-data-panel drawer-widget'></div>"
            "<script>var raw = drawChart(); var strawVal = 1;</script>"
            "</body></html>")
    found = names(d.detect("https://furniture.example", html, {}, {}))
    assert "Font Awesome" not in found
    assert "Google Ads" not in found


def test_no_false_positive_on_common_bem_class_fragments():
    # "list-item" / "post-title" / "first-child" style class names contain
    # "st-" as a substring, which used to trigger a false ShareThis match.
    d = TechnologyDetector()
    html = ("<html><head></head><body>"
            "<ul class='list-item'><li class='post-title first-child'></li></ul>"
            "</body></html>")
    found = names(d.detect("https://blog.example", html, {}, {}))
    assert "ShareThis" not in found


def test_no_false_positive_on_generic_class_fragments_found_live():
    # Found via validate_live.py against real sites: "text-body"/"content-body"
    # style classes tripped Tilda ("t-body"); "desc-"/"disc-" tripped
    # styled-components ("sc-"); a language switcher tripped Prism.js
    # ("language-"); a pagination attribute tripped Inertia.js ("data-page").
    d = TechnologyDetector()
    html = ("<html><head></head><body class='content-body desc-panel'>"
            "<nav class='language-selector'></nav>"
            "<div data-page='2' class='pagination'></div>"
            "</body></html>")
    found = names(d.detect("https://generic.example", html, {}, {}))
    for bad in ["Tilda", "styled-components", "Prism.js", "Inertia.js"]:
        assert bad not in found, f"false positive: {bad}"


def test_no_false_positive_on_short_underscore_suffixed_tokens():
    # Found via validate_live.py on ~15/41 real sites: "ck_" (ConvertKit) and
    # "bv_" (Bazaarvoice) matched inside unrelated minified identifiers like
    # "check_", "click_", "block_", "stock_".
    d = TechnologyDetector()
    html = ("<html><head><script>"
            "function check_status(){} var click_count=0; var block_id='x';"
            "</script></head><body></body></html>")
    found = names(d.detect("https://x.example", html, {}, {}))
    assert "ConvertKit" not in found
    assert "Bazaarvoice" not in found


def test_no_false_positive_on_short_ga_token():
    # A bare "G-" substring inside unrelated inline JS must not trigger GA4.
    d = TechnologyDetector()
    html = ("<html><head><script>"
            "const bgColor = 'bg-red-500'; const imgSrc = 'img-loader';"
            "</script></head><body></body></html>")
    found = names(d.detect("https://x.example", html, {}, {}))
    assert "Google Analytics 4" not in found
