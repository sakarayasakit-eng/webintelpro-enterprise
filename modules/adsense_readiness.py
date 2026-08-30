"""
WebIntelPro Enterprise X
AdSense / Monetization Risk Report

IMPORTANT SCOPE STATEMENT (surfaced in output, not just here):
This module does NOT predict AdSense approval odds, does NOT predict search
ranking, and does NOT know Google's current policy enforcement thresholds.
It assembles OBSERVABLE risk factors from this tool's own findings --
duplicate/thin content clusters, missing policy-relevant pages, security
posture, accessibility posture -- that are publicly known to correlate with
monetization and content-quality review outcomes. Absence of a flagged risk
factor is not a guarantee of approval; presence of one is not a guarantee
of rejection. Every factor is labeled with a confidence level.
"""

from __future__ import annotations


def assess(site: dict) -> dict:
    factors = []

    dup = site.get("duplicate_content", {}).get("summary", {})
    clusters = site.get("duplicate_content", {}).get("clusters", [])
    high_risk_clusters = [c for c in clusters if c["risk"] == "HIGH"]
    if high_risk_clusters:
        pages_involved = sum(c["size"] for c in high_risk_clusters)
        factors.append({
            "factor": "Programmatic / near-duplicate content clusters",
            "detail": f"{len(high_risk_clusters)} high-similarity cluster(s) "
                      f"covering {pages_involved} page(s) with >=90% shared text.",
            "why_it_matters": ("Publisher content policies generally require pages to "
                               "offer genuinely unique value; large near-duplicate "
                               "clusters are a commonly cited rejection/re-review reason."),
            "severity": "high",
            "confidence": "heuristic",
        })
    elif clusters:
        factors.append({
            "factor": "Some near-duplicate content detected (not high-risk)",
            "detail": f"{len(clusters)} cluster(s) found, none at HIGH risk threshold.",
            "why_it_matters": "Monitor; templated pages with light unique content per page "
                               "are a common source of gradual duplicate-content drift.",
            "severity": "low",
            "confidence": "heuristic",
        })

    idx = site.get("indexability", {})
    qv = idx.get("query_variants", {})
    risky_qv = [g for g in qv.get("groups", []) if g["risk"] in ("HIGH", "MEDIUM")]
    if risky_qv:
        factors.append({
            "factor": "Query-parameter URL variants without consistent canonicalization",
            "detail": f"{len(risky_qv)} path(s) have multiple query-string variants "
                      f"that do not converge on a single canonical URL.",
            "why_it_matters": ("Search engines and content reviewers may treat each "
                               "variant as a separate low-value page."),
            "severity": "medium",
            "confidence": "confirmed",
        })

    thin_pages = [p for p in site.get("pages", []) if p.get("status") == "ok"
                  and p.get("word_count", 0) < 300]
    if thin_pages:
        factors.append({
            "factor": "Thin-content pages",
            "detail": f"{len(thin_pages)} page(s) under ~300 words of visible text.",
            "why_it_matters": "Thin content is a widely-cited factor in ad-quality and "
                               "content-quality review, though word count alone is not "
                               "a reliable quality measure.",
            "severity": "medium" if len(thin_pages) > 5 else "low",
            "confidence": "possible",
        })

    sec_avg = site.get("averages", {}).get("security", 100)
    if sec_avg < 70:
        factors.append({
            "factor": "Below-average site-wide security posture",
            "detail": f"Average security score {sec_avg}/100 across crawled pages.",
            "why_it_matters": "Not a direct ad-policy factor, but missing security "
                               "headers/HTTPS issues can affect trust signals and user safety.",
            "severity": "low",
            "confidence": "confirmed",
        })

    a11y_avg = site.get("averages", {}).get("accessibility", 100)
    if a11y_avg < 70:
        factors.append({
            "factor": "Below-average accessibility posture",
            "detail": f"Average accessibility score {a11y_avg}/100 across crawled pages.",
            "why_it_matters": "Not a direct ad-policy factor, but affects user experience "
                               "quality signals reviewers may weigh qualitatively.",
            "severity": "low",
            "confidence": "confirmed",
        })

    high = sum(1 for f in factors if f["severity"] == "high")
    medium = sum(1 for f in factors if f["severity"] == "medium")
    low = sum(1 for f in factors if f["severity"] == "low")

    return {
        "disclaimer": ("This is an OBSERVABLE risk-factor report, not an approval "
                       "prediction. It does not know Google's current review criteria "
                       "or enforcement thresholds. Use it to find and fix concrete "
                       "issues, not to estimate approval probability."),
        "factors": factors,
        "summary": {"high": high, "medium": medium, "low": low, "total": len(factors)},
    }
