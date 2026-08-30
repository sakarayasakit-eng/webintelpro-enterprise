"""
WebIntelPro Enterprise X
Duplicate / Near-Duplicate / Programmatic Content Detection

Clusters crawled pages by actual visible-text similarity (k-shingle Jaccard),
not just matching titles or URLs. This directly answers: "are these pages
genuinely unique, or is this a templated/programmatic pattern with a few
changed entities (country, bank, currency, location)?"

Method and limitations (state these to the user -- do not overclaim):
  - Similarity is computed on VISIBLE BODY TEXT ONLY (scripts/styles/noscript
    stripped). It does not read rendered/JS-injected content.
  - k-shingle Jaccard similarity is a well-established near-duplicate
    detection technique, but it is a heuristic: a legitimately large shared
    boilerplate (nav/footer/disclaimers) on otherwise-different pages can
    inflate similarity. Every result is labeled confidence="heuristic".
  - This clusters pages within a single crawl only; it cannot see pages that
    were not crawled.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from typing import Dict, Iterable, List, Set
from urllib.parse import urlparse

from bs4 import BeautifulSoup

_WORD_RE = re.compile(r"[a-z0-9']+")
_STRIP_TAGS = ("script", "style", "noscript", "template")

DEFAULT_SIMILARITY_THRESHOLD = 0.60
HIGH_RISK_SIMILARITY = 0.90
MEDIUM_RISK_SIMILARITY = 0.75
HIGH_RISK_MIN_CLUSTER = 4


def extract_text(html: str) -> str:
    """Visible body text with script/style/template markup removed."""
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(_STRIP_TAGS):
        tag.decompose()
    body = soup.find("body") or soup
    return body.get_text(" ", strip=True)


def shingle_set(text: str, k: int = 4) -> Set[int]:
    """k-word shingles of the text, each hashed to a stable int."""
    words = _WORD_RE.findall(text.lower())
    if len(words) < k:
        return {int(hashlib.md5(" ".join(words).encode()).hexdigest()[:12], 16)} if words else set()
    out = set()
    for i in range(len(words) - k + 1):
        shingle = " ".join(words[i:i + k])
        out.add(int(hashlib.md5(shingle.encode()).hexdigest()[:12], 16))
    return out


def jaccard(a: Set[int], b: Set[int]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def guess_template(urls: List[str]) -> str:
    """Best-effort label for what these pages appear to be templated from."""
    segments = []
    for u in urls:
        path = urlparse(u).path.strip("/")
        parts = [p for p in path.split("/") if p]
        segments.append(parts)
    if not segments:
        return "unknown"
    # most common leading path segment (e.g. "pages")
    leaders = defaultdict(int)
    for parts in segments:
        if parts:
            leaders[parts[0]] += 1
    common_leader = max(leaders, key=leaders.get) if leaders else None
    # most common trailing token fragment across last segments (e.g. "calculator")
    tails = defaultdict(int)
    for parts in segments:
        if parts:
            last = parts[-1]
            for token in re.split(r"[-_]", last):
                if len(token) > 3:
                    tails[token] += 1
    common_tail = max(tails, key=tails.get) if tails else None
    if common_leader and common_tail:
        return f"/{common_leader}/*-{common_tail}"
    if common_leader:
        return f"/{common_leader}/*"
    return "mixed / no common path pattern"


def _risk(avg_similarity: float, size: int) -> str:
    if avg_similarity >= HIGH_RISK_SIMILARITY and size >= HIGH_RISK_MIN_CLUSTER:
        return "HIGH"
    if avg_similarity >= MEDIUM_RISK_SIMILARITY:
        return "MEDIUM"
    return "LOW"


def cluster_pages(pages: List[Dict], threshold: float = DEFAULT_SIMILARITY_THRESHOLD) -> List[Dict]:
    """
    pages: list of {"url": str, "shingles": set[int], "word_count": int}
    Returns clusters (size >= 2) sorted by risk desc, then size desc.
    Union-find style greedy grouping on pairwise Jaccard >= threshold.
    """
    n = len(pages)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj

    pair_sims: Dict[tuple, float] = {}
    for i in range(n):
        si = pages[i]["shingles"]
        if not si:
            continue
        for j in range(i + 1, n):
            sj = pages[j]["shingles"]
            if not sj:
                continue
            sim = jaccard(si, sj)
            if sim >= threshold:
                pair_sims[(i, j)] = sim
                union(i, j)

    groups: Dict[int, List[int]] = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)

    clusters = []
    cid = 0
    for members in groups.values():
        if len(members) < 2:
            continue
        cid += 1
        urls = [pages[i]["url"] for i in members]
        sims = [v for (a, b), v in pair_sims.items() if a in members and b in members]
        avg_sim = sum(sims) / len(sims) if sims else 0.0
        risk = _risk(avg_sim, len(members))
        unique_pct = round(max(0.0, 1.0 - avg_sim) * 100, 1)
        clusters.append({
            "cluster_id": f"{cid:03d}",
            "pages": urls,
            "size": len(members),
            "similarity_pct": round(avg_sim * 100, 1),
            "template_guess": guess_template(urls),
            "unique_information_pct": unique_pct,
            "risk": risk,
            "confidence": "heuristic",
            "method": "k-shingle Jaccard similarity on visible body text",
            "recommendation": (
                "Consolidate into a single dynamic page, or substantially "
                "differentiate each page with unique, page-specific content."
                if risk in ("HIGH", "MEDIUM") else
                "Low risk; monitor if the cluster grows."
            ),
        })

    clusters.sort(key=lambda c: ({"HIGH": 0, "MEDIUM": 1, "LOW": 2}[c["risk"]], -c["size"]))
    return clusters


def summarize(clusters: List[Dict], total_pages: int) -> dict:
    high = sum(1 for c in clusters if c["risk"] == "HIGH")
    medium = sum(1 for c in clusters if c["risk"] == "MEDIUM")
    low = sum(1 for c in clusters if c["risk"] == "LOW")
    pages_in_clusters = len({u for c in clusters for u in c["pages"]})
    return {
        "total_pages_analyzed": total_pages,
        "clusters_found": len(clusters),
        "high_risk_clusters": high,
        "medium_risk_clusters": medium,
        "low_risk_clusters": low,
        "pages_in_any_cluster": pages_in_clusters,
        "pages_unclustered": max(0, total_pages - pages_in_clusters),
        "confidence": "heuristic",
    }
