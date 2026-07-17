from technology.detector import TechnologyDetector
from engine import AnalysisEngine
from reporter import ReportGenerator


def test_debug_off_by_default_no_evidence_breakdown():
    d = TechnologyDetector()
    r = d.detect("https://x.example", "<html></html>",
                 {"Strict-Transport-Security": "max-age=1"}, {})
    tech = next(t for t in r.technologies if t.name == "HSTS")
    assert tech.debug is None


def test_debug_true_populates_source_breakdown():
    d = TechnologyDetector()
    r = d.detect("https://x.example", "<html></html>",
                 {"Strict-Transport-Security": "max-age=1"}, {}, debug=True)
    tech = next(t for t in r.technologies if t.name == "HSTS")
    assert tech.debug
    assert "headers" in tech.debug
    assert tech.debug["headers"]["weight"] == 0.60
    assert tech.debug["headers"]["patterns"]


def test_debug_breakdown_included_in_json_only_when_present():
    d = TechnologyDetector()
    off = d.detect("https://x.example", "<html></html>",
                    {"Strict-Transport-Security": "max-age=1"}, {})
    on = d.detect("https://x.example", "<html></html>",
                   {"Strict-Transport-Security": "max-age=1"}, {}, debug=True)
    off_dict = off.to_dict()["technologies"][0]
    on_dict = on.to_dict()["technologies"][0]
    assert "debug" not in off_dict
    assert "debug" in on_dict


def test_engine_debug_flag_flows_through_to_console(wordpress_html, wordpress_headers,
                                                      wordpress_cookies):
    engine = AnalysisEngine(debug=True)
    result = engine.analyze("https://acme.example", wordpress_html,
                            wordpress_headers, wordpress_cookies)
    out = ReportGenerator().console_str(result)
    assert "DETECTION EVIDENCE" in out
    assert "weight" in out
