import json

from engine import AnalysisEngine
from reporter import ReportGenerator


def build_result(html, headers, cookies):
    engine = AnalysisEngine()
    return engine.analyze("https://acme.example", html, headers, cookies)


def test_console_output(wordpress_html, wordpress_headers, wordpress_cookies):
    result = build_result(wordpress_html, wordpress_headers, wordpress_cookies)
    out = ReportGenerator().console_str(result)
    assert "WebIntelPro" in out
    assert "OVERALL SCORE" in out
    assert "WordPress" in out


def test_json_output(wordpress_html, wordpress_headers, wordpress_cookies):
    result = build_result(wordpress_html, wordpress_headers, wordpress_cookies)
    payload = json.loads(ReportGenerator().to_json(result))
    assert payload["url"] == "https://acme.example"
    assert "overall" in payload and "score" in payload["overall"]
    assert payload["technology"]["total_detected"] >= 3


def test_html_output(wordpress_html, wordpress_headers, wordpress_cookies):
    result = build_result(wordpress_html, wordpress_headers, wordpress_cookies)
    doc = ReportGenerator().to_html(result)
    assert doc.startswith("<!doctype html>")
    assert "Overall score" in doc
    assert "WordPress" in doc
