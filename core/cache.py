"""
WebIntelPro Enterprise X
Crawl Cache - on-disk cache of crawl responses (keyed by URL) with a TTL.
"""

from __future__ import annotations

import hashlib
import json
import os
import time

from crawler import CrawlResult

_FIELDS = ("url", "final_url", "status_code", "html", "headers", "cookies",
           "elapsed", "ttfb", "content_encoding", "http_version",
           "redirect_chain", "set_cookie", "error")


class CrawlCache:

    def __init__(self, directory: str = "cache", ttl: int = 3600):
        self.directory = directory
        self.ttl = ttl
        os.makedirs(directory, exist_ok=True)

    def _path(self, url: str) -> str:
        key = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
        return os.path.join(self.directory, f"{key}.json")

    def get(self, url: str):
        path = self._path(url)
        if not os.path.exists(path):
            return None
        if time.time() - os.path.getmtime(path) > self.ttl:
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return CrawlResult(**{k: v for k, v in data.items() if k in _FIELDS})
        except Exception:
            return None

    def put(self, crawl: CrawlResult) -> None:
        data = {k: getattr(crawl, k) for k in _FIELDS}
        try:
            with open(self._path(crawl.url), "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception:
            pass

    def clear(self) -> int:
        removed = 0
        for name in os.listdir(self.directory):
            if name.endswith(".json"):
                try:
                    os.remove(os.path.join(self.directory, name))
                    removed += 1
                except OSError:
                    pass
        return removed
