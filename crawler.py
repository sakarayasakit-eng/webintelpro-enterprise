"""
WebIntelPro Enterprise X
Crawler Module

Downloads a webpage and returns HTML, headers, cookies, and network metadata
(redirect chain, HTTP version, raw Set-Cookie headers, timing).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

import requests

_HTTP_VERSION = {9: "0.9", 10: "1.0", 11: "1.1", 20: "2.0", 30: "3.0"}


@dataclass
class CrawlResult:
    url: str
    final_url: str
    status_code: int
    html: str
    headers: Dict[str, str] = field(default_factory=dict)
    cookies: Dict[str, str] = field(default_factory=dict)
    elapsed: float = 0.0
    ttfb: float = 0.0
    content_encoding: str = ""
    http_version: str = ""
    # `requests`/urllib3 (via Python's stdlib http.client) never negotiates
    # HTTP/2 or HTTP/3 over ALPN -- response.raw.version can only ever be 10
    # or 11, regardless of what the server actually served. So http_version
    # is NOT a reliable observation with this transport and must never be
    # treated as confirmed evidence of "legacy HTTP/1.1". Analyzers must
    # check this flag before drawing any conclusion from http_version.
    http_version_reliable: bool = False
    redirect_chain: List[dict] = field(default_factory=list)
    set_cookie: List[str] = field(default_factory=list)
    error: str = ""


class WebCrawler:

    DEFAULT_UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0 Safari/537.36 WebIntelPro/2.5"
    )

    def __init__(self, timeout: int = 20, user_agent: str = ""):
        self.timeout = timeout
        self.headers = {"User-Agent": user_agent or self.DEFAULT_UA}

    def crawl(self, url: str) -> CrawlResult:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        response = requests.get(url, headers=self.headers, timeout=self.timeout,
                                allow_redirects=True)
        response.raise_for_status()

        # raw Set-Cookie list (preserves attributes like Secure/HttpOnly/SameSite)
        set_cookie: List[str] = []
        try:
            set_cookie = response.raw.headers.getlist("Set-Cookie")
        except Exception:
            sc = response.headers.get("Set-Cookie")
            if sc:
                set_cookie = [sc]

        http_version = ""
        try:
            http_version = _HTTP_VERSION.get(response.raw.version, "")
        except Exception:
            pass

        chain = [{"status": r.status_code, "url": r.url} for r in response.history]

        return CrawlResult(
            url=url,
            final_url=response.url,
            status_code=response.status_code,
            html=response.text,
            headers=dict(response.headers),
            cookies=response.cookies.get_dict(),
            elapsed=response.elapsed.total_seconds(),
            ttfb=response.elapsed.total_seconds(),
            content_encoding=response.headers.get("Content-Encoding", ""),
            http_version=http_version,
            redirect_chain=chain,
            set_cookie=set_cookie,
        )
