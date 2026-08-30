"""
WebIntelPro Enterprise X
Competitor Comparison

Runs the full analysis on a primary site and one or more competitors, then
ranks each dimension, computes the technology gap, and picks an overall winner.
"""

from __future__ import annotations

from engine import AnalysisEngine

_DIMENSIONS = ["overall", "seo", "security", "performance", "accessibility"]


class CompetitorComparison:

    def __init__(self, timeout: int = 20, use_cache: bool = True, debug: bool = False,
                 site_checks: bool = False,
                 analyze_js: bool = False, analyze_runtime: bool = False,
                 analyze_api: bool = False, analyze_ai_stack: bool = False,
                 analyze_auth: bool = False):
        # Every site compared (primary + competitors) goes through
        # engine.analyze_url(), which already reads all of these off the
        # engine instance (see engine.py) -- so, unlike SiteCrawler, no
        # special-casing is needed here: constructing AnalysisEngine with
        # them is sufficient to fix --vs silently ignoring --js-bundles/
        # --runtime-analysis/--api-discovery/--ai-detection/--auth-detection/
        # site-check flags. All default False, matching single-page mode's
        # off-by-default flags (site_checks is on unconditionally only in
        # main.py::_run_single/_run_compare's CLI wiring, not as a class
        # default here -- so existing offline tests that construct
        # CompetitorComparison(use_cache=False) without these keyword
        # arguments keep making zero live network calls beyond the mocked
        # crawler, exactly as before this fix).
        self.engine = AnalysisEngine(
            timeout=timeout, use_cache=use_cache, debug=debug, site_checks=site_checks,
            analyze_js=analyze_js, analyze_runtime=analyze_runtime,
            analyze_api=analyze_api, analyze_ai_stack=analyze_ai_stack,
            analyze_auth=analyze_auth)

    def compare(self, primary: str, competitors: list) -> dict:
        sites = []
        for i, url in enumerate(dict.fromkeys([primary] + list(competitors))):
            sites.append(self._analyze(url, is_primary=(i == 0)))

        ok_sites = [s for s in sites if s["status"] == "ok"]
        dimensions = self._rank(ok_sites)
        gap = self._tech_gap(sites)
        winner = dimensions.get("overall", {}).get("winner")

        return {
            "primary": primary,
            "sites": sites,
            "dimensions": dimensions,
            "tech_gap": gap,
            "winner": winner,
        }

    # ----------------------------------------------------------------- helpers
    def _analyze(self, url: str, is_primary: bool) -> dict:
        row = {"url": url, "primary": is_primary, "status": "ok"}
        try:
            result = self.engine.analyze_url(url)
            o = result["overall"]
            tech = result["technology"]
            row.update({
                "overall": o["score"], "grade": o["grade"],
                "seo": o["parts"]["seo"], "security": o["parts"]["security"],
                "performance": o["parts"]["performance"],
                "accessibility": o["parts"]["accessibility"],
                "technologies": sorted({t.name for t in tech.technologies}),
                "tech_count": tech.total_detected,
                "server": tech.server or "", "cms": tech.cms or "",
                "recommendations": result["recommendation_summary"]["by_severity"],
            })
        except Exception as exc:  # noqa: BLE001
            row["status"] = f"error: {type(exc).__name__}: {exc}"
        return row

    def _rank(self, ok_sites: list) -> dict:
        dims = {}
        for dim in _DIMENSIONS:
            ranked = sorted(ok_sites, key=lambda s: s.get(dim, 0), reverse=True)
            dims[dim] = {
                "winner": ranked[0]["url"] if ranked else None,
                "ranking": [{"url": s["url"], "score": s.get(dim, 0)} for s in ranked],
            }
        return dims

    def _tech_gap(self, sites: list) -> dict:
        ok = [s for s in sites if s["status"] == "ok"]
        primary = next((s for s in ok if s["primary"]), None)
        if not primary:
            return {"missing": [], "unique": [], "competitor_tech": {}}

        p_tech = set(primary["technologies"])
        competitor_tech = {}
        all_comp = set()
        for s in ok:
            if s["primary"]:
                continue
            competitor_tech[s["url"]] = s["technologies"]
            all_comp |= set(s["technologies"])

        return {
            # tech competitors use that the primary does not
            "missing": sorted(all_comp - p_tech),
            # tech only the primary uses
            "unique": sorted(p_tech - all_comp),
            "competitor_tech": competitor_tech,
        }
