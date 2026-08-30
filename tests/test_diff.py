"""Offline tests for scan-to-scan diffing (diff.py). All fixtures are
hand-built dicts matching reporter.to_json()/save_site_json() shapes --
no live scans, no network."""

import json

import pytest

from diff import DiffError, diff_reports, diff_files


# --------------------------------------------------------------- fixtures

def _page_report(url="https://example.com", overall=70,
                 parts=None, technologies=None, security=None,
                 recommendations=None, optional_fields=None):
    parts = parts or {"seo": 80, "security": 50, "performance": 75, "accessibility": 90}
    technologies = technologies if technologies is not None else [
        {"name": "Nginx", "category": "server", "confidence": 0.9, "version": None},
    ]
    security = security or {"hsts": False, "csp": False, "x_frame_options": True,
                            "x_content_type": True, "referrer_policy": False,
                            "permissions_policy": False}
    report = {
        "url": url,
        "overall": {"score": overall, "grade": "C", "parts": parts},
        "technology": {"technologies": technologies},
        "security": security,
        "recommendations": recommendations or [],
    }
    if optional_fields:
        report["technology"].update(optional_fields)
    return report


def _site_report(start_url="https://demo.com", pages_ok=10, pages_crawled=10,
                 averages=None, technologies=None, recommendations=None,
                 site_checks=None, vitals=None):
    return {
        "start_url": start_url,
        "pages_ok": pages_ok,
        "pages_crawled": pages_crawled,
        "pages": [],
        "averages": averages or {"overall": 70, "seo": 75, "security": 60,
                                 "performance": 80, "accessibility": 85},
        "technologies": technologies if technologies is not None else ["Nginx", "jQuery"],
        "recommendations": recommendations or [],
        **({"site_checks": site_checks} if site_checks is not None else {}),
        **({"vitals": vitals} if vitals is not None else {}),
    }


def _rec(severity, area, issue):
    return {"severity": severity, "area": area, "issue": issue,
           "recommendation": "fix it", "confidence": "confirmed"}


# ----------------------------------------------------------- shape/URL guards

def test_rejects_different_urls():
    before = _page_report(url="https://a.com")
    after = _page_report(url="https://b.com")
    with pytest.raises(DiffError, match="different targets"):
        diff_reports(before, after)


def test_different_urls_allowed_with_strict_url_false():
    before = _page_report(url="https://a.com")
    after = _page_report(url="https://b.com")
    d = diff_reports(before, after, strict_url=False)
    assert d["mode"] == "page"


def test_url_trailing_slash_and_case_normalized():
    before = _page_report(url="https://Example.com/")
    after = _page_report(url="https://example.com")
    d = diff_reports(before, after)  # must NOT raise
    assert d["mode"] == "page"


def test_rejects_page_vs_site_shape_mismatch():
    before = _page_report()
    after = _site_report()
    with pytest.raises(DiffError, match="single-page report against a site-wide"):
        diff_reports(before, after)


def test_diff_files_loads_from_disk(tmp_path):
    before = _page_report(overall=70)
    after = _page_report(overall=90)
    bp, ap = tmp_path / "before.json", tmp_path / "after.json"
    bp.write_text(json.dumps(before))
    ap.write_text(json.dumps(after))
    d = diff_files(str(bp), str(ap))
    assert d["scores"]["overall"]["before"] == 70
    assert d["scores"]["overall"]["after"] == 90


# --------------------------------------------------------------- self-diff

def test_diffing_report_against_itself_is_empty():
    report = _page_report(
        technologies=[{"name": "Nginx", "category": "server", "confidence": 0.9, "version": None}],
        recommendations=[_rec("high", "Security", "No HSTS header")])
    d = diff_reports(report, report)
    assert d["technologies"]["added"] == []
    assert d["technologies"]["removed"] == []
    assert d["technologies"]["confidence_changed"] == []
    assert d["recommendations"]["new"] == []
    assert d["recommendations"]["resolved"] == []
    assert d["security_headers"] == []
    for dim in d["scores"].values():
        assert dim["delta"] == 0


# ----------------------------------------------------------------- scores

def test_score_delta_improved_and_regressed():
    before = _page_report(overall=70, parts={"seo": 80, "security": 50,
                                             "performance": 90, "accessibility": 90})
    after = _page_report(overall=85, parts={"seo": 80, "security": 80,
                                            "performance": 60, "accessibility": 90})
    d = diff_reports(before, after)
    assert d["scores"]["overall"]["delta"] == 15          # improved
    assert d["scores"]["security"]["delta"] == 30          # improved
    assert d["scores"]["performance"]["delta"] == -30      # regressed
    assert d["scores"]["seo"]["delta"] == 0                # unchanged


# ------------------------------------------------------------ technologies

def test_technology_added_and_removed():
    before = _page_report(technologies=[
        {"name": "Nginx", "category": "server", "confidence": 0.9, "version": None},
        {"name": "jQuery", "category": "javascript", "confidence": 0.6, "version": "1.9"},
    ])
    after = _page_report(technologies=[
        {"name": "Nginx", "category": "server", "confidence": 0.9, "version": None},
        {"name": "React", "category": "javascript", "confidence": 0.7, "version": None},
    ])
    d = diff_reports(before, after)
    added_names = {t["name"] for t in d["technologies"]["added"]}
    removed_names = {t["name"] for t in d["technologies"]["removed"]}
    assert added_names == {"React"}
    assert removed_names == {"jQuery"}
    assert d["technologies"]["unchanged_count"] == 1


def test_technology_confidence_changed_but_name_unchanged():
    before = _page_report(technologies=[
        {"name": "Nginx", "category": "server", "confidence": 0.5, "version": None}])
    after = _page_report(technologies=[
        {"name": "Nginx", "category": "server", "confidence": 0.9, "version": None}])
    d = diff_reports(before, after)
    assert d["technologies"]["added"] == []
    assert d["technologies"]["removed"] == []
    changed = d["technologies"]["confidence_changed"]
    assert len(changed) == 1
    assert changed[0]["name"] == "Nginx"
    assert changed[0]["confidence_before"] == 0.5
    assert changed[0]["confidence_after"] == 0.9
    assert changed[0]["delta"] == pytest.approx(0.4)


def test_technology_tiny_confidence_wobble_is_not_reported_as_changed():
    """A sub-threshold float wobble (e.g. evidence-set reordering) must not
    surface as a 'confidence changed' finding -- only deltas >=
    CONFIDENCE_CHANGE_THRESHOLD (0.05) count."""
    before = _page_report(technologies=[
        {"name": "Nginx", "category": "server", "confidence": 0.900, "version": None}])
    after = _page_report(technologies=[
        {"name": "Nginx", "category": "server", "confidence": 0.901, "version": None}])
    d = diff_reports(before, after)
    assert d["technologies"]["confidence_changed"] == []
    assert d["technologies"]["unchanged_count"] == 1


def test_near_threshold_flag_on_borderline_added_and_removed_tech():
    """A technology detected right at/near MIN_CONFIDENCE (0.30) is
    inherently unstable across scans -- report data can't distinguish
    'genuinely gone' from 'confidence dipped under the detection gate', so
    added/removed entries in that band must be flagged, not reported as an
    ordinary unambiguous change."""
    before = _page_report(technologies=[
        {"name": "Nginx", "category": "server", "confidence": 0.9, "version": None},
        {"name": "Borderline Lib", "category": "javascript", "confidence": 0.32, "version": None},
    ])
    after = _page_report(technologies=[
        {"name": "Nginx", "category": "server", "confidence": 0.9, "version": None},
        {"name": "Confident Lib", "category": "javascript", "confidence": 0.85, "version": None},
    ])
    d = diff_reports(before, after)
    removed = {t["name"]: t for t in d["technologies"]["removed"]}
    added = {t["name"]: t for t in d["technologies"]["added"]}
    assert removed["Borderline Lib"]["near_threshold"] is True
    assert added["Confident Lib"]["near_threshold"] is False


# ------------------------------------------------------------------ headers

def test_security_header_flip():
    before = _page_report(security={"hsts": False, "csp": True, "x_frame_options": True,
                                    "x_content_type": True, "referrer_policy": False,
                                    "permissions_policy": False})
    after = _page_report(security={"hsts": True, "csp": False, "x_frame_options": True,
                                   "x_content_type": True, "referrer_policy": False,
                                   "permissions_policy": False})
    d = diff_reports(before, after)
    flips = {f["header"]: f for f in d["security_headers"]}
    assert flips["hsts"]["change"] == "added"
    assert flips["csp"]["change"] == "removed"
    assert "x_frame_options" not in flips  # unchanged, must not appear


# ------------------------------------------------------------ recommendations

def test_recommendation_new_and_resolved():
    before = _page_report(recommendations=[_rec("high", "Security", "No HSTS header")])
    after = _page_report(recommendations=[_rec("critical", "Security", "TLS certificate has expired")])
    d = diff_reports(before, after)
    assert len(d["recommendations"]["new"]) == 1
    assert d["recommendations"]["new"][0]["issue"] == "TLS certificate has expired"
    assert len(d["recommendations"]["resolved"]) == 1
    assert d["recommendations"]["resolved"][0]["issue"] == "No HSTS header"
    assert d["recommendations"]["new_critical_high"] == d["recommendations"]["new"]
    assert d["recommendations"]["resolved_critical_high"] == d["recommendations"]["resolved"]


def test_recommendation_low_severity_resolved_not_counted_as_critical_high():
    before = _page_report(recommendations=[_rec("low", "SEO", "No Open Graph tags")])
    after = _page_report(recommendations=[])
    d = diff_reports(before, after)
    assert len(d["recommendations"]["resolved"]) == 1
    assert d["recommendations"]["resolved_critical_high"] == []


def test_recommendation_embedded_count_does_not_cause_false_new_and_resolved():
    """'3 form field(s) without a label' vs '1 form field(s)...' must be
    recognized as the SAME finding (count changed, not a resolved+new
    pair) -- this was a real bug caught by live validation against a
    production report (TTFB values differ per page)."""
    before = _page_report(recommendations=[
        _rec("medium", "Accessibility", "3 form field(s) without a label")])
    after = _page_report(recommendations=[
        _rec("medium", "Accessibility", "1 form field(s) without a label")])
    d = diff_reports(before, after)
    assert d["recommendations"]["new"] == []
    assert d["recommendations"]["resolved"] == []


def test_recommendation_embedded_number_mid_string_bucketed():
    """Regression for the exact bug found in live testing: 'Slow TTFB
    (1.20s)' vs 'Slow TTFB (2.04s)' must bucket together (number is not
    leading, it's embedded inside parentheses)."""
    before = _page_report(recommendations=[
        _rec("medium", "Performance", "Slow TTFB (1.20s)")])
    after = _page_report(recommendations=[
        _rec("medium", "Performance", "Slow TTFB (2.04s)")])
    d = diff_reports(before, after)
    assert d["recommendations"]["new"] == []
    assert d["recommendations"]["resolved"] == []


def test_recommendation_severity_changed():
    before = _page_report(recommendations=[_rec("low", "Security", "HSTS max-age below 180 days")])
    after = _page_report(recommendations=[_rec("high", "Security", "HSTS max-age below 180 days")])
    d = diff_reports(before, after)
    assert d["recommendations"]["new"] == []
    assert d["recommendations"]["resolved"] == []
    assert len(d["recommendations"]["severity_changed"]) == 1
    sc = d["recommendations"]["severity_changed"][0]
    assert sc["severity_before"] == "low" and sc["severity_after"] == "high"


# -------------------------------------------------------- optional fields

@pytest.mark.parametrize("field", ["ai_stack", "api_discovery", "authentication", "runtime"])
def test_optional_field_absent_on_both_sides(field):
    before = _page_report()
    after = _page_report()
    d = diff_reports(before, after)
    assert d["optional_fields"][field] == {"status": "absent_both"}


@pytest.mark.parametrize("field", ["ai_stack", "api_discovery", "authentication", "runtime"])
def test_optional_field_present_on_after_only(field):
    before = _page_report()
    after = _page_report(optional_fields={
        field: {"total_findings": 1, "providers": [
            {"name": "OpenAI", "confidence": 0.8, "version": None}]}})
    d = diff_reports(before, after)
    assert d["optional_fields"][field]["status"] == "added_field"


@pytest.mark.parametrize("field", ["ai_stack", "api_discovery", "authentication", "runtime"])
def test_optional_field_present_on_before_only(field):
    before = _page_report(optional_fields={
        field: {"total_findings": 1, "providers": [
            {"name": "OpenAI", "confidence": 0.8, "version": None}]}})
    after = _page_report()
    d = diff_reports(before, after)
    assert d["optional_fields"][field]["status"] == "removed_field"


@pytest.mark.parametrize("field", ["ai_stack", "api_discovery", "authentication", "runtime"])
def test_optional_field_present_on_both_sides_compared(field):
    before = _page_report(optional_fields={
        field: {"total_findings": 1, "providers": [
            {"name": "OpenAI", "confidence": 0.6, "version": None}]}})
    after = _page_report(optional_fields={
        field: {"total_findings": 2, "providers": [
            {"name": "OpenAI", "confidence": 0.6, "version": None},
            {"name": "Anthropic", "confidence": 0.7, "version": None}]}})
    d = diff_reports(before, after)
    result = d["optional_fields"][field]
    assert result["status"] == "compared"
    assert [f["name"] for f in result["added"]] == ["Anthropic"]
    assert result["removed"] == []


def test_optional_field_confidence_changed_within_compared():
    before = _page_report(optional_fields={
        "ai_stack": {"total_findings": 1, "providers": [
            {"name": "OpenAI", "confidence": 0.5, "version": None}]}})
    after = _page_report(optional_fields={
        "ai_stack": {"total_findings": 1, "providers": [
            {"name": "OpenAI", "confidence": 0.9, "version": None}]}})
    d = diff_reports(before, after)
    changed = d["optional_fields"]["ai_stack"]["confidence_changed"]
    assert len(changed) == 1
    assert changed[0]["name"] == "OpenAI"


# --------------------------------------------------------------- site-wide

def test_site_diff_technology_names_added_removed():
    before = _site_report(technologies=["Nginx", "jQuery"])
    after = _site_report(technologies=["Nginx", "React"])
    d = diff_reports(before, after)
    assert d["mode"] == "site"
    assert d["technologies"]["added"] == ["React"]
    assert d["technologies"]["removed"] == ["jQuery"]
    assert d["technologies"]["unchanged_count"] == 1
    # site-wide tech entries are plain strings, not dicts w/ confidence
    assert all(isinstance(t, str) for t in d["technologies"]["added"])


def test_site_diff_pages_and_scores():
    before = _site_report(pages_ok=10, pages_crawled=10,
                          averages={"overall": 70, "seo": 75, "security": 60,
                                   "performance": 80, "accessibility": 85})
    after = _site_report(pages_ok=12, pages_crawled=12,
                         averages={"overall": 78, "seo": 75, "security": 75,
                                  "performance": 80, "accessibility": 85})
    d = diff_reports(before, after)
    assert d["pages"]["before_ok"] == 10 and d["pages"]["after_ok"] == 12
    assert d["scores"]["overall"]["delta"] == 8
    assert d["scores"]["security"]["delta"] == 15


def test_site_diff_recommendations_use_pages_affected_not_confused_by_count():
    before = _site_report(recommendations=[
        {"severity": "high", "area": "Security", "issue": "No CSP",
         "recommendation": "add it", "pages_affected": 296}])
    after = _site_report(recommendations=[
        {"severity": "high", "area": "Security", "issue": "No CSP",
         "recommendation": "add it", "pages_affected": 300}])
    d = diff_reports(before, after)
    # same issue, only pages_affected differs -- must not show as new+resolved
    assert d["recommendations"]["new"] == []
    assert d["recommendations"]["resolved"] == []


@pytest.mark.parametrize("before_sc,after_sc,expected_status", [
    (None, None, "absent_both"),
    (None, {"robots": {"exists": True}, "sitemap": {"exists": True}, "tls": {}}, "added_field"),
    ({"robots": {"exists": True}, "sitemap": {"exists": True}, "tls": {}}, None, "removed_field"),
])
def test_site_checks_delta_three_states(before_sc, after_sc, expected_status):
    before = _site_report(site_checks=before_sc)
    after = _site_report(site_checks=after_sc)
    d = diff_reports(before, after)
    assert d["site_checks"]["status"] == expected_status


def test_site_checks_delta_compared():
    before = _site_report(site_checks={
        "robots": {"exists": False}, "sitemap": {"exists": True},
        "tls": {"checked": True, "protocol": "TLSv1.2"}})
    after = _site_report(site_checks={
        "robots": {"exists": True}, "sitemap": {"exists": True},
        "tls": {"checked": True, "protocol": "TLSv1.3"}})
    d = diff_reports(before, after)
    sc = d["site_checks"]
    assert sc["status"] == "compared"
    assert sc["robots_exists"] == {"before": False, "after": True}
    assert sc["tls_protocol"] == {"before": "TLSv1.2", "after": "TLSv1.3"}


@pytest.mark.parametrize("before_v,after_v,expected_status", [
    (None, None, "absent_both"),
    (None, {"available": True, "metrics": {}}, "added_field"),
    ({"available": True, "metrics": {}}, None, "removed_field"),
])
def test_vitals_delta_three_states(before_v, after_v, expected_status):
    before = _site_report(vitals=before_v)
    after = _site_report(vitals=after_v)
    d = diff_reports(before, after)
    assert d["vitals"]["status"] == expected_status


def test_vitals_delta_compared_ratings():
    before = _site_report(vitals={"available": True, "metrics": {
        "lcp": {"value": 4200.0, "rating": "poor"}}})
    after = _site_report(vitals={"available": True, "metrics": {
        "lcp": {"value": 1800.0, "rating": "good"}}})
    d = diff_reports(before, after)
    v = d["vitals"]
    assert v["status"] == "compared"
    assert v["ratings"]["lcp"] == {"before": "poor", "after": "good"}


# ----------------------------------------------------------- reporter output

def test_reporter_diff_console_str_page_mode_does_not_crash():
    from reporter import ReportGenerator
    before = _page_report(overall=70, recommendations=[_rec("high", "Security", "No HSTS header")])
    after = _page_report(overall=85, technologies=[
        {"name": "Nginx", "category": "server", "confidence": 0.9, "version": None},
        {"name": "React", "category": "javascript", "confidence": 0.7, "version": None}],
        recommendations=[_rec("critical", "Security", "TLS certificate has expired")])
    d = diff_reports(before, after)
    txt = ReportGenerator().diff_console_str(d)
    assert "Scan Diff" in txt
    assert "React" in txt
    assert "TLS certificate has expired" in txt


def test_reporter_diff_console_str_site_mode_does_not_crash():
    from reporter import ReportGenerator
    before = _site_report()
    after = _site_report(technologies=["Nginx", "React"])
    d = diff_reports(before, after)
    txt = ReportGenerator().diff_console_str(d)
    assert "Site-wide" in txt


def test_reporter_save_diff_json_and_html(tmp_path):
    from reporter import ReportGenerator
    before = _page_report(overall=70)
    after = _page_report(overall=85)
    d = diff_reports(before, after)
    rep = ReportGenerator()

    jp = tmp_path / "d.json"
    rep.save_diff_json(d, str(jp))
    reloaded = json.loads(jp.read_text())
    assert reloaded["scores"]["overall"]["after"] == 85

    hp = tmp_path / "d.html"
    rep.save_diff_html(d, str(hp))
    assert hp.read_text().startswith("<!doctype html>")
