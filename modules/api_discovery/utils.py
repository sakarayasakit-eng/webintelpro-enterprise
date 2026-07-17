"""
WebIntelPro Enterprise X
API Discovery (Phase 2C) - Utilities

Small, dependency-light helpers used across the sub-detectors and the
orchestrator: text primitives (truncate/dedupe), robots.txt-aware reachability
probing, and response doc-shape sniffing.

Two invariants hold for everything in this module, mirroring
:mod:`technology.runtime.utils`:

* **Never raises.** Malformed input or a failed request yields an
  empty/neutral result, never an exception to the caller.
* **Never unbounded.** Probing is capped by count, per-request timeout and a
  wall-clock budget, all read from
  :class:`~modules.api_discovery.models.ApiDiscoveryConfig`.
"""

from __future__ import annotations

import logging
import time
import urllib.robotparser
from typing import Dict, Iterable, List, Optional
from urllib.parse import urljoin, urlparse

import requests

from .models import ApiDiscoveryConfig, Candidate, ProbeResult

logger = logging.getLogger("webintelpro.api_discovery.utils")


def truncate(value: str, limit: int) -> str:
    """Shorten ``value`` to ``limit`` characters, marking that it was cut."""
    if not value:
        return ""
    value = value.strip()
    if limit <= 0 or len(value) <= limit:
        return value
    return value[: max(limit - 1, 1)] + "…"


def clamp(text: str, max_bytes: int) -> str:
    """Return at most ``max_bytes`` characters of ``text`` (0 = no cap)."""
    if not text or max_bytes <= 0 or len(text) <= max_bytes:
        return text or ""
    return text[:max_bytes]


def dedupe(items: Iterable[str]) -> List[str]:
    """Order-preserving de-duplication of strings."""
    seen = set()
    out: List[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


class RobotsChecker:
    """Per-host robots.txt cache, consulted before any probe request.

    A fetch failure (no robots.txt, timeout, non-200) is treated as "no
    restriction": the absence of a robots.txt is the common case and must not
    block a handful of well-known-path checks.
    """

    def __init__(self, session: requests.Session, timeout: float, user_agent: str):
        self._session = session
        self._timeout = timeout
        self._user_agent = user_agent
        self._cache: Dict[str, Optional[urllib.robotparser.RobotFileParser]] = {}

    def allowed(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
            origin = f"{parsed.scheme}://{parsed.netloc}"
        except Exception:  # noqa: BLE001 - a malformed URL is simply not probed
            return False
        parser = self._get(origin)
        if parser is None:
            return True
        try:
            return parser.can_fetch(self._user_agent, url)
        except Exception:  # noqa: BLE001 - a parser bug must not block probing
            return True

    def _get(self, origin: str) -> Optional[urllib.robotparser.RobotFileParser]:
        if origin in self._cache:
            return self._cache[origin]
        parser = None
        try:
            resp = self._session.get(urljoin(origin, "/robots.txt"),
                                     timeout=self._timeout)
            if resp.status_code == 200 and resp.text:
                parser = urllib.robotparser.RobotFileParser()
                parser.parse(resp.text.splitlines())
        except requests.RequestException as exc:
            logger.debug("robots.txt fetch failed for %s: %s", origin, exc)
        except Exception:  # noqa: BLE001 - a malformed robots.txt is not fatal
            logger.debug("robots.txt parse failed for %s", origin, exc_info=True)
            parser = None
        self._cache[origin] = parser
        return parser


class ReachabilityProber:
    """Conservative, bounded live-reachability checks against candidate URLs.

    Never a wordlist, never brute force: callers pass a small fixed set of
    candidate URLs (well-known paths plus, optionally, endpoints already
    mined from the page). One request per URL -- HEAD first, falling back to
    a byte-capped GET only when HEAD is refused or unsupported (some servers
    405/501 on HEAD for API routes; a plain 404 is trusted as-is and costs no
    second request). Bounded by :attr:`ApiDiscoveryConfig.max_probes`,
    per-request timeout and a wall-clock budget; whichever is exhausted first
    stops further probing.
    """

    _READ_CAP = 4096  # bytes sniffed from a fallback GET body

    def __init__(self, config: ApiDiscoveryConfig | None = None):
        self.config = config or ApiDiscoveryConfig()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.config.user_agent,
            "Accept": "application/json, text/yaml, */*",
        })
        self._robots = RobotsChecker(self.session, self.config.probe_timeout,
                                      self.config.user_agent)

    def probe_many(self, urls: List[str]) -> Dict[str, ProbeResult]:
        """Probe up to :attr:`max_probes` distinct URLs, budget-permitting."""
        results: Dict[str, ProbeResult] = {}
        started = time.perf_counter()
        budget = self.config.probe_time_budget_seconds
        count = 0
        for url in dedupe(urls):
            if count >= self.config.max_probes:
                logger.debug("probe count cap reached (%d)", self.config.max_probes)
                break
            if (time.perf_counter() - started) >= budget:
                logger.debug("probe time budget exhausted after %ss", budget)
                break
            count += 1
            results[url] = self.probe_one(url)
        return results

    def probe_one(self, url: str) -> ProbeResult:
        """Check one URL's reachability with a single (or, rarely, two) requests."""
        if self.config.respect_robots_txt and not self._robots.allowed(url):
            return ProbeResult(url=url, error="robots_disallowed")

        resp = None
        try:
            resp = self.session.head(url, timeout=self.config.probe_timeout,
                                     allow_redirects=True)
            if resp.status_code in (405, 501):
                resp = self._get_snippet(url) or resp
        except requests.RequestException as exc:
            logger.debug("HEAD failed for %s: %s", url, exc)
            resp = self._get_snippet(url)
            if resp is None:
                return ProbeResult(url=url, error=type(exc).__name__)

        if resp is None:
            return ProbeResult(url=url, error="no_response")

        content_type = resp.headers.get("Content-Type", "").split(";")[0].strip()
        status = resp.status_code
        return ProbeResult(
            url=url,
            status=status,
            reachable=status not in (404, 410) and status < 500,
            content_type=content_type,
        )

    def _get_snippet(self, url: str) -> Optional[requests.Response]:
        try:
            return self.session.get(url, timeout=self.config.probe_timeout,
                                    stream=True)
        except requests.RequestException as exc:
            logger.debug("GET failed for %s: %s", url, exc)
            return None

    def sniff_body(self, url: str) -> str:
        """Read a small, bounded snippet of ``url``'s body for shape checks.

        Separate from :meth:`probe_one` so the common reachability check never
        pays for a body read; only doc-shape validation (Swagger/OpenAPI)
        calls this, and only for candidates that already look reachable.
        """
        try:
            resp = self.session.get(url, timeout=self.config.probe_timeout,
                                    stream=True)
            with resp:
                chunk = next(resp.iter_content(chunk_size=self._READ_CAP), b"")
                return chunk.decode(resp.encoding or "utf-8", errors="ignore")
        except (requests.RequestException, StopIteration) as exc:
            logger.debug("body sniff failed for %s: %s", url, exc)
            return ""


def resolve_candidates(base_url: str,
                       candidates: List[Candidate]) -> Dict[str, Candidate]:
    """Resolve each candidate's path against ``base_url`` into a full URL."""
    resolved: Dict[str, Candidate] = {}
    for candidate in candidates:
        try:
            url = urljoin(base_url, candidate.path)
        except Exception:  # noqa: BLE001 - a malformed base URL yields no candidates
            continue
        resolved[url] = candidate
    return resolved
