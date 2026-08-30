"""
WebIntelPro Enterprise X
Scan-to-Scan Diff

Compares two previously-saved WebIntelPro reports (single-page `-f json`
output, or site-wide `-f json` output from --crawl) for the same target and
produces a structured diff: technologies added/removed/confidence-changed,
score deltas, security-header flips (single-page only -- see
_diff_page_reports), recommendation deltas, and -- where present on both
sides -- Phase 2 (ai_stack/api_discovery/authentication/runtime) deltas.

Deliberately narrow scope: diffs exactly two reports for the same target.
"Diff since last scan" / N-scan trend lines are a separate, later feature
(see docs/phase3_roadmap_2026-08-09.md, item D2) -- this module doesn't try
to do both, and doesn't touch trends.py.

Public surface: diff_reports(before, after) and diff_files(path1, path2).
Both raise DiffError (not a bare exception) when the two reports aren't
comparable, rather than silently producing a confusing partial diff.
"""

from __future__ import annotations

import json
from typing import Optional

_SCORE_DIMENSIONS = ["overall", "seo", "security", "performance", "accessibility"]
_SECURITY_FLAGS = ["hsts", "csp", "x_frame_options", "x_content_type",
                   "referrer_policy", "permissions_policy"]
_OPTIONAL_TECH_FIELDS = ["ai_stack", "api_discovery", "authentication", "runtime"]

# TechnologyDetector.MIN_CONFIDENCE (0.30) is the gate below which a
# detection never appears in a report at all -- imported lazily inside
# functions that need it so importing diff.py never requires network or
# pulls in the full detection stack just to diff two already-saved JSON
# files.
_MIN_CONFIDENCE_FALLBACK = 0.30
# A technology detected within this margin of MIN_CONFIDENCE is "borderline":
# an ordinary scan-to-scan confidence wobble (slightly different page state
# or evidence collected) could tip it across the detection threshold and
# make it appear/disappear from the technologies list even though nothing
# about the site actually changed. Added/removed entries whose confidence
# sits in this band are flagged `near_threshold: True` rather than reported
# as unambiguous change -- report data alone can't distinguish "genuinely
# removed" from "confidence dipped under the gate", since anything below the
# gate is never recorded in either report to begin with.
NEAR_THRESHOLD_MARGIN = 0.15
# Confidence-changed-but-name-unchanged is only reported when the delta is
# at least this large, so trivial evidence-set reordering noise (e.g. a
# 0.001 float wobble from set-ordering in evidence merging) doesn't produce
# a "change" that isn't meaningfully one.
CONFIDENCE_CHANGE_THRESHOLD = 0.05


class DiffError(ValueError):
    """Raised when two reports can't be meaningfully diffed: different
    target URL, or one is single-page and the other is site-wide."""


def _min_confidence() -> float:
    try:
        from technology.detector import TechnologyDetector
        return TechnologyDetector.MIN_CONFIDENCE
    except Exception:  # noqa: BLE001 -- diffing must never hard-depend on this
        return _MIN_CONFIDENCE_FALLBACK


def load_report(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _is_site_report(report: dict) -> bool:
    return "pages" in report


def _report_url(report: dict) -> str:
    return report.get("url") or report.get("start_url") or ""


def _normalize_url(url: str) -> str:
    return url.rstrip("/").lower()


def diff_files(before_path: str, after_path: str, *, strict_url: bool = True) -> dict:
    """Load two saved report JSON files and diff them. See diff_reports()."""
    return diff_reports(load_report(before_path), load_report(after_path),
                        strict_url=strict_url)


def diff_reports(before: dict, after: dict, *, strict_url: bool = True) -> dict:
    """Diff two report dicts (as produced by reporter.to_json()/
    save_site_json()) for what should be the same target.

    Raises DiffError if they're not comparable: one is single-page and the
    other is site-wide (different top-level shape entirely -- diffing them
    would silently compare unrelated fields), or they're for different URLs
    (pass strict_url=False to force a diff anyway, e.g. when comparing a
    site before/after a domain migration).
    """
    before_is_site = _is_site_report(before)
    after_is_site = _is_site_report(after)
    if before_is_site != after_is_site:
        raise DiffError(
            "Cannot diff a single-page report against a site-wide report "
            f"(before is {'site-wide' if before_is_site else 'single-page'}, "
            f"after is {'site-wide' if after_is_site else 'single-page'}). "
            "Both reports must come from the same scan mode.")

    before_url = _report_url(before)
    after_url = _report_url(after)
    if strict_url and _normalize_url(before_url) != _normalize_url(after_url):
        raise DiffError(
            f"Cannot diff reports for different targets ({before_url!r} vs "
            f"{after_url!r}). Pass strict_url=False to force it anyway.")

    if before_is_site:
        return _diff_site_reports(before, after, before_url, after_url)
    return _diff_page_reports(before, after, before_url, after_url)


# ------------------------------------------------------------- technologies

def _tech_index(tech_list: list) -> dict:
    """name -> {category, confidence, version} for a technology.to_dict()
    'technologies' list. Last-write-wins on duplicate names (shouldn't
    happen -- the detector already dedupes by name -- but be defensive)."""
    return {t["name"]: t for t in (tech_list or []) if t.get("name")}


def _diff_technologies(before_list: list, after_list: list) -> dict:
    """Full added/removed/confidence-changed diff for a page-level
    technologies list (each entry has name/category/confidence/version)."""
    before_idx = _tech_index(before_list)
    after_idx = _tech_index(after_list)
    before_names = set(before_idx)
    after_names = set(after_idx)
    threshold = _min_confidence()
    near_band = threshold + NEAR_THRESHOLD_MARGIN

    def _entry(name, idx):
        t = idx[name]
        return {"name": name, "category": t.get("category"),
                "confidence": t.get("confidence"), "version": t.get("version")}

    added = []
    for name in sorted(after_names - before_names):
        e = _entry(name, after_idx)
        e["near_threshold"] = (e["confidence"] or 0) < near_band
        added.append(e)

    removed = []
    for name in sorted(before_names - after_names):
        e = _entry(name, before_idx)
        e["near_threshold"] = (e["confidence"] or 0) < near_band
        removed.append(e)

    confidence_changed = []
    for name in sorted(before_names & after_names):
        b, a = before_idx[name], after_idx[name]
        b_conf, a_conf = b.get("confidence") or 0, a.get("confidence") or 0
        if abs(a_conf - b_conf) >= CONFIDENCE_CHANGE_THRESHOLD:
            confidence_changed.append({
                "name": name, "category": a.get("category"),
                "confidence_before": b_conf, "confidence_after": a_conf,
                "delta": round(a_conf - b_conf, 3),
            })

    return {
        "added": added,
        "removed": removed,
        "confidence_changed": confidence_changed,
        "unchanged_count": len(before_names & after_names) - len(confidence_changed),
    }


def _diff_technology_names(before_names: list, after_names: list) -> dict:
    """Name-only added/removed diff, for site-wide reports where the
    aggregate `technologies` list is flat strings (no per-tech confidence/
    category at that level -- see sitecrawl.py's tech_union)."""
    before_set, after_set = set(before_names or []), set(after_names or [])
    return {
        "added": sorted(after_set - before_set),
        "removed": sorted(before_set - after_set),
        "unchanged_count": len(before_set & after_set),
    }


# --------------------------------------------------------- optional fields

def _named_findings(field_value: dict) -> dict:
    """Flatten an ai_stack/api_discovery/authentication/runtime to_dict()
    payload (each is `{"total_findings": N, ..., category_a: [...], ...}`,
    per-category lists of finding dicts that each carry a "name") into a
    single {name: finding_dict} map across every category. Scalar summary
    keys (total_findings/truncated/errors/elapsed/url/hydration_strategies)
    are skipped since they aren't findings."""
    out = {}
    for key, value in (field_value or {}).items():
        if not isinstance(value, list):
            continue
        for finding in value:
            if isinstance(finding, dict) and finding.get("name"):
                out[finding["name"]] = finding
    return out


def _diff_optional_field(before_val: Optional[dict], after_val: Optional[dict]) -> dict:
    """Three-state diff for an Optional Phase 2 field (ai_stack/
    api_discovery/authentication/runtime), each of which is None/absent
    unless the corresponding --*-detection/--*-analysis flag was used on
    that scan:
      - absent on both sides  -> {"status": "absent_both"}
      - present on one side only -> {"status": "added_field"/"removed_field"}
        (the flag was newly turned on, or turned off / no longer set)
      - present on both sides -> {"status": "compared", "added": [...],
        "removed": [...], "confidence_changed": [...]}, diffed by finding
        name the same way _diff_technologies() diffs the main list.
    """
    before_present = bool(before_val)
    after_present = bool(after_val)

    if not before_present and not after_present:
        return {"status": "absent_both"}
    if before_present and not after_present:
        return {"status": "removed_field",
                "note": "Present in the before-scan, absent in the after-scan "
                        "-- most likely the corresponding flag wasn't used on "
                        "the after-scan (not necessarily that the site changed)."}
    if after_present and not before_present:
        return {"status": "added_field",
                "note": "Absent in the before-scan, present in the after-scan "
                        "-- most likely the corresponding flag was newly used "
                        "(not necessarily that the site changed)."}

    before_findings = _named_findings(before_val)
    after_findings = _named_findings(after_val)
    before_names, after_names = set(before_findings), set(after_findings)
    threshold = _min_confidence()
    near_band = threshold + NEAR_THRESHOLD_MARGIN

    def _entry(name, idx):
        f = idx[name]
        e = {"name": name, "confidence": f.get("confidence"), "version": f.get("version")}
        e["near_threshold"] = (e["confidence"] or 0) < near_band
        return e

    added = [_entry(n, after_findings) for n in sorted(after_names - before_names)]
    removed = [_entry(n, before_findings) for n in sorted(before_names - after_names)]
    confidence_changed = []
    for name in sorted(before_names & after_names):
        b_conf = before_findings[name].get("confidence") or 0
        a_conf = after_findings[name].get("confidence") or 0
        if abs(a_conf - b_conf) >= CONFIDENCE_CHANGE_THRESHOLD:
            confidence_changed.append({"name": name, "confidence_before": b_conf,
                                       "confidence_after": a_conf,
                                       "delta": round(a_conf - b_conf, 3)})

    return {"status": "compared", "added": added, "removed": removed,
            "confidence_changed": confidence_changed}


# -------------------------------------------------------------- severity

import re as _re
_NUMBER_RE = _re.compile(r"\d+(?:\.\d+)?")


def _bucket_issue(issue: str) -> str:
    """Collapse issue strings that only differ by an embedded number --
    anywhere in the string, not just a leading count -- so a recommendation
    diff doesn't report a resolved+new pair for what is really the same
    finding with a different number. Covers both leading-count issues
    ('1 form field(s) without a label' vs '5 form field(s)...') and
    embedded-elsewhere issues discovered via live validation against a real
    300-page production report ('Slow TTFB (1.20s)' vs 'Slow TTFB (2.04s)'
    -- every page has a different TTFB, so without this every single page's
    TTFB reading produced its own spurious new+resolved pair instead of
    being recognized as the same recurring finding).

    Deliberately NOT shared with sitecrawl.py's own `_bucket_issue` (which
    only strips a *leading* count): that one is already shipped, tested,
    and covers a narrower case (page-level recurring-issue rollup across a
    single crawl); this one is broader because scan-to-scan diffing sees
    the embedded-number problem in more places (TTFB, byte sizes, etc.).
    Fixing sitecrawl.py's version to match is worth doing separately -- see
    the final report -- but is out of scope for the diff feature itself."""
    return _NUMBER_RE.sub("N", issue)


def _rec_key(rec: dict) -> tuple:
    return (rec.get("area"), _bucket_issue(rec.get("issue", "")))


def _diff_recommendations(before_list: list, after_list: list) -> dict:
    before_idx = {_rec_key(r): r for r in (before_list or [])}
    after_idx = {_rec_key(r): r for r in (after_list or [])}
    before_keys, after_keys = set(before_idx), set(after_idx)

    new_recs = [after_idx[k] for k in sorted(after_keys - before_keys,
                                             key=lambda k: (k[0] or "", k[1] or ""))]
    resolved = [before_idx[k] for k in sorted(before_keys - after_keys,
                                              key=lambda k: (k[0] or "", k[1] or ""))]
    severity_changed = []
    for k in sorted(before_keys & after_keys, key=lambda k: (k[0] or "", k[1] or "")):
        b, a = before_idx[k], after_idx[k]
        if b.get("severity") != a.get("severity"):
            severity_changed.append({
                "area": k[0], "issue": k[1],
                "severity_before": b.get("severity"), "severity_after": a.get("severity"),
            })

    high_sev = {"critical", "high"}
    return {
        "new": new_recs,
        "resolved": resolved,
        "severity_changed": severity_changed,
        "new_critical_high": [r for r in new_recs if r.get("severity") in high_sev],
        "resolved_critical_high": [r for r in resolved if r.get("severity") in high_sev],
    }


# ---------------------------------------------------------- single-page

def _score_deltas(before_overall: dict, after_overall: dict) -> dict:
    before_parts = before_overall.get("parts", {})
    after_parts = after_overall.get("parts", {})
    out = {}
    for dim in _SCORE_DIMENSIONS:
        b = before_overall.get("score") if dim == "overall" else before_parts.get(dim)
        a = after_overall.get("score") if dim == "overall" else after_parts.get(dim)
        out[dim] = {"before": b, "after": a,
                    "delta": (a - b) if isinstance(a, (int, float))
                             and isinstance(b, (int, float)) else None}
    return out


def _security_header_deltas(before_security: dict, after_security: dict) -> list:
    flips = []
    for flag in _SECURITY_FLAGS:
        b = bool(before_security.get(flag))
        a = bool(after_security.get(flag))
        if b != a:
            flips.append({"header": flag, "before": b, "after": a,
                          "change": "added" if a else "removed"})
    return flips


def _diff_page_reports(before: dict, after: dict, before_url: str, after_url: str) -> dict:
    before_tech = before.get("technology", {})
    after_tech = after.get("technology", {})

    optional_fields = {
        field: _diff_optional_field(before_tech.get(field), after_tech.get(field))
        for field in _OPTIONAL_TECH_FIELDS
    }

    return {
        "mode": "page",
        "before_url": before_url,
        "after_url": after_url,
        "scores": _score_deltas(before.get("overall", {}), after.get("overall", {})),
        "technologies": _diff_technologies(
            before_tech.get("technologies", []), after_tech.get("technologies", [])),
        "security_headers": _security_header_deltas(
            before.get("security", {}), after.get("security", {})),
        "recommendations": _diff_recommendations(
            before.get("recommendations", []), after.get("recommendations", [])),
        "optional_fields": optional_fields,
    }


# ----------------------------------------------------------- site-wide

def _site_checks_delta(before_sc: Optional[dict], after_sc: Optional[dict]) -> dict:
    if not before_sc and not after_sc:
        return {"status": "absent_both"}
    if bool(before_sc) != bool(after_sc):
        return {"status": "added_field" if after_sc else "removed_field"}
    b_robots, a_robots = before_sc.get("robots", {}), after_sc.get("robots", {})
    b_sitemap, a_sitemap = before_sc.get("sitemap", {}), after_sc.get("sitemap", {})
    b_tls, a_tls = before_sc.get("tls", {}), after_sc.get("tls", {})
    return {
        "status": "compared",
        "robots_exists": {"before": b_robots.get("exists"), "after": a_robots.get("exists")},
        "sitemap_exists": {"before": b_sitemap.get("exists"), "after": a_sitemap.get("exists")},
        "tls_protocol": {"before": b_tls.get("protocol"), "after": a_tls.get("protocol")},
    }


def _vitals_delta(before_v: Optional[dict], after_v: Optional[dict]) -> dict:
    if not before_v and not after_v:
        return {"status": "absent_both"}
    if bool(before_v) != bool(after_v):
        return {"status": "added_field" if after_v else "removed_field"}
    if not before_v.get("available") or not after_v.get("available"):
        return {"status": "compared", "available_before": before_v.get("available"),
                "available_after": after_v.get("available"), "ratings": {}}
    ratings = {}
    b_metrics, a_metrics = before_v.get("metrics", {}), after_v.get("metrics", {})
    for key in set(b_metrics) | set(a_metrics):
        ratings[key] = {"before": b_metrics.get(key, {}).get("rating"),
                        "after": a_metrics.get(key, {}).get("rating")}
    return {"status": "compared", "available_before": True, "available_after": True,
            "ratings": ratings}


def _diff_site_reports(before: dict, after: dict, before_url: str, after_url: str) -> dict:
    b_avg, a_avg = before.get("averages", {}), after.get("averages", {})
    scores = {}
    for dim in _SCORE_DIMENSIONS:
        b, a = b_avg.get(dim), a_avg.get(dim)
        scores[dim] = {"before": b, "after": a,
                       "delta": (a - b) if isinstance(a, (int, float))
                                and isinstance(b, (int, float)) else None}

    return {
        "mode": "site",
        "before_url": before_url,
        "after_url": after_url,
        "pages": {
            "before_ok": before.get("pages_ok"), "after_ok": after.get("pages_ok"),
            "before_crawled": before.get("pages_crawled"),
            "after_crawled": after.get("pages_crawled"),
        },
        "scores": scores,
        # Site-wide reports store the technology union as flat names only
        # (no per-tech confidence/category at that aggregate level -- see
        # sitecrawl.py's tech_union), so this is a name-only diff, not the
        # richer added/removed/confidence_changed shape _diff_page_reports
        # produces. Security-header flips aren't available at all here for
        # the same reason: they're a per-page fact, not an aggregate one,
        # and the site-wide report doesn't retain a per-page header dict.
        "technologies": _diff_technology_names(
            before.get("technologies", []), after.get("technologies", [])),
        "recommendations": _diff_recommendations(
            before.get("recommendations", []), after.get("recommendations", [])),
        "site_checks": _site_checks_delta(before.get("site_checks"), after.get("site_checks")),
        "vitals": _vitals_delta(before.get("vitals"), after.get("vitals")),
    }
