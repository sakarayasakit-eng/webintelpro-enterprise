"""
WebIntelPro Enterprise X
Canonical / Indexability / Internal-Link Analysis

Answers three questions the scoring engine alone cannot:
  1. Query-parameter homogenization: are many crawled "pages" actually the
     same normalized path with different query strings, and if so, do they
     correctly canonicalize to one URL (fine) or not (indexation risk)?
  2. Canonical correctness: does every page's canonical resolve sensibly,
     and -- for canonical targets that are themselves in the crawled set --
     does that target point back (reciprocate)?
  3. Internal-link health: within the crawled set, which pages have very
     few (or zero) other crawled pages linking to them? A same-domain
     link-following crawler cannot discover true orphans (pages with zero
     internal links can't be reached by following links at all), so this
     is reported as "weakly linked within the crawled set", not "orphaned
     site-wide" -- that distinction is stated explicitly to avoid overclaiming.

All findings carry a "confidence" field per the false-positive-control
policy: confirmed (directly observed), likely, possible, or unknown.
Scope limitations are stated in each finding, not just in this docstring.
"""

from __future__ import annotations

from collections import defaultdict
from urllib.parse import urlparse


def _normalized_path(url: str) -> str:
    p = urlparse(url)
    path = p.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    return path


def analyze_query_variants(pages: list) -> dict:
    """Group crawled pages by normalized path; flag paths with >1 distinct
    query string. This directly answers "are the 296 pages 296 unique
    documents, or query-parameter variants of a smaller set of templates?"
    """
    groups: dict = defaultdict(list)
    for p in pages:
        groups[_normalized_path(p["url"])].append(p)

    variant_groups = []
    for path, members in groups.items():
        queries = {m.get("query", "") for m in members}
        if len(members) <= 1 or len(queries) <= 1:
            continue
        canonical_targets = {m.get("canonical") or "" for m in members}
        canonical_targets.discard("")
        converges = len(canonical_targets) == 1
        finding = {
            "path": path,
            "variant_count": len(members),
            "distinct_query_strings": len(queries),
            "sample_urls": [m["url"] for m in members[:5]],
            "canonicalizes_to_single_url": converges,
            "canonical_target": next(iter(canonical_targets)) if converges else None,
        }
        if converges:
            finding["risk"] = "LOW"
            finding["note"] = ("All variants declare the same canonical URL -- "
                                "correctly signals one indexable document.")
            finding["confidence"] = "confirmed"
        elif canonical_targets:
            finding["risk"] = "MEDIUM"
            finding["note"] = ("Variants declare DIFFERING canonical URLs -- "
                                "conflicting signals to search engines.")
            finding["confidence"] = "confirmed"
        else:
            finding["risk"] = "MEDIUM" if len(members) < 10 else "HIGH"
            finding["note"] = ("No canonical tag on these variants -- each "
                                "query-string URL may be indexed separately, "
                                "diluting ranking signals across near-identical pages.")
            finding["confidence"] = "likely"
        variant_groups.append(finding)

    variant_groups.sort(key=lambda f: ({"HIGH": 0, "MEDIUM": 1, "LOW": 2}[f["risk"]],
                                        -f["variant_count"]))
    pages_in_variant_groups = sum(f["variant_count"] for f in variant_groups)
    return {
        "unique_normalized_paths": len(groups),
        "pages_analyzed": len(pages),
        "paths_with_query_variants": len(variant_groups),
        "pages_in_variant_groups": pages_in_variant_groups,
        "groups": variant_groups,
    }


def analyze_canonicals(pages: list) -> dict:
    """Self-canonical / cross-canonical checks, scoped to the crawled set."""
    by_url = {p["url"]: p for p in pages}
    noindex_pages = [p["url"] for p in pages if p.get("noindex")]
    self_canonical, points_elsewhere, no_canonical = [], [], []
    unreciprocated = []

    for p in pages:
        canon = (p.get("canonical") or "").rstrip("/")
        url = p["url"].rstrip("/")
        if not canon:
            no_canonical.append(p["url"])
            continue
        if canon == url:
            self_canonical.append(p["url"])
            continue
        points_elsewhere.append({"url": p["url"], "canonical": p["canonical"]})
        target = by_url.get(p["canonical"]) or by_url.get(p["canonical"].rstrip("/"))
        if target is not None:
            target_canon = (target.get("canonical") or "").rstrip("/")
            if target_canon and target_canon != p["canonical"].rstrip("/"):
                unreciprocated.append({
                    "page": p["url"], "declared_canonical": p["canonical"],
                    "target_actually_canonicalizes_to": target.get("canonical"),
                    "confidence": "confirmed",
                    "note": "Canonical target does not point back to itself as declared "
                            "(observed within the crawled set only).",
                })

    return {
        "pages_with_noindex": noindex_pages,
        "self_canonical_count": len(self_canonical),
        "points_elsewhere_count": len(points_elsewhere),
        "points_elsewhere_sample": points_elsewhere[:20],
        "no_canonical_count": len(no_canonical),
        "no_canonical_sample": no_canonical[:20],
        "unreciprocated_canonicals": unreciprocated,
        "scope_limitation": ("Reciprocation is checked only against pages that were "
                              "actually crawled; a canonical target outside the crawl "
                              "set cannot be verified and is not flagged either way."),
    }


def analyze_internal_links(pages: list, link_graph: dict) -> dict:
    """Inbound internal-link counts within the crawled set.

    Scope limitation stated explicitly: a same-domain, link-following crawler
    can only discover pages that are reachable via at least one internal
    link from the start page (or the start page itself), so "0 inbound
    links found in this crawl" cannot mean "truly orphaned site-wide" --
    it means "not linked *by any other page this crawl visited*", which is
    itself a legitimate weak-internal-linking signal worth surfacing.
    """
    if not link_graph:
        return {"available": False}

    def norm(u):
        return u.rstrip("/") or u

    inbound = defaultdict(int)
    for src, targets in link_graph.items():
        for t in targets:
            if norm(t) != norm(src):
                inbound[norm(t)] += 1

    rows = []
    for p in pages:
        key = norm(p["url"])
        rows.append({"url": p["url"], "inbound_links_in_crawl": inbound.get(key, 0)})
    rows.sort(key=lambda r: r["inbound_links_in_crawl"])

    weakly_linked = [r for r in rows if r["inbound_links_in_crawl"] <= 1]
    return {
        "available": True,
        "weakly_linked_count": len(weakly_linked),
        "weakly_linked_sample": weakly_linked[:25],
        "confidence": "confirmed",
        "scope_limitation": ("Counts internal links found on pages that were crawled "
                              "in this run only; does not reflect the full site's "
                              "link graph if max-pages truncated the crawl."),
    }


def run(pages: list, start_url: str, link_graph: dict | None = None) -> dict:
    return {
        "query_variants": analyze_query_variants(pages),
        "canonicals": analyze_canonicals(pages),
        "internal_links": analyze_internal_links(pages, link_graph or {}),
    }
