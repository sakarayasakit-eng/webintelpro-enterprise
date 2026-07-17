"""
WebIntelPro Enterprise X
Trend Tracking

Persists each scan's scores (per URL) to a small JSON history file and
reports how a site's scores have moved over time.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

_DIMENSIONS = ["overall", "seo", "security", "performance", "accessibility"]


class TrendTracker:

    def __init__(self, path: str = "data/trends.json"):
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    # ------------------------------------------------------------- storage
    def _load(self) -> dict:
        if not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save(self, data: dict) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _append(self, url: str, entry: dict) -> None:
        data = self._load()
        data.setdefault(url, []).append(entry)
        data[url] = data[url][-100:]   # keep last 100
        self._save(data)

    # ------------------------------------------------------------- record
    def record(self, result: dict) -> None:
        o = result["overall"]
        self._append(result["url"], {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "scope": "page",
            "overall": o["score"], **o["parts"],
            "tech_count": result["technology"].total_detected,
        })

    def record_site(self, site: dict) -> None:
        a = site["averages"]
        self._append(site["start_url"], {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "scope": "site",
            "overall": a["overall"], "seo": a["seo"], "security": a["security"],
            "performance": a["performance"], "accessibility": a["accessibility"],
            "tech_count": len(site.get("technologies", [])),
            "pages": site.get("pages_ok", 0),
        })

    # ------------------------------------------------------------- report
    def history(self, url: str) -> list:
        return self._load().get(url, [])

    def delta(self, url: str) -> dict:
        h = self.history(url)
        if len(h) < 2:
            return {}
        prev, cur = h[-2], h[-1]
        return {d: cur.get(d, 0) - prev.get(d, 0) for d in _DIMENSIONS}

    def format_history(self, url: str) -> str:
        h = self.history(url)
        if not h:
            return f"No history recorded yet for {url}."
        L = [f"Score history for {url}  ({len(h)} scan(s))", "-" * 60]
        L.append(f"{'DATE':20} {'OVR':>4} {'SEO':>4} {'SEC':>4} {'PERF':>4} {'A11Y':>4}")
        for e in h[-15:]:
            L.append(f"{e['ts'][:19]:20} {e.get('overall',0):>4} {e.get('seo',0):>4} "
                     f"{e.get('security',0):>4} {e.get('performance',0):>4} "
                     f"{e.get('accessibility',0):>4}")
        d = self.delta(url)
        if d:
            trend = ", ".join(f"{k} {'+' if d[k] >= 0 else ''}{d[k]}" for k in _DIMENSIONS)
            L.append("-" * 60)
            L.append(f"Change since previous scan: {trend}")
        return "\n".join(L)
