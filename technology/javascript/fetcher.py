"""
WebIntelPro Enterprise X
JavaScript Bundle Intelligence - Downloader

Downloads discovered JavaScript bundles safely and cheaply:

  * transparent gzip / deflate (always) and Brotli (when a decoder is present)
  * follows redirects
  * per-request timeout and graceful failure (never raises to the caller)
  * hard size cap enforced *while streaming* so an oversized bundle is aborted
    mid-download rather than after being fully buffered
  * an in-process content cache keyed by URL so a bundle shared across pages
    (or referenced twice) is fetched at most once
  * de-duplication by content hash so byte-identical bundles served from
    different URLs are only scanned once downstream
"""

from __future__ import annotations

import hashlib
import logging
from typing import Dict

import requests

from .models import BundleConfig, JSBundle
from .utils import accept_encoding, clamp_text

logger = logging.getLogger("webintelpro.js.fetcher")

_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/137.0 Safari/537.36 WebIntelPro/2.5"
)


class BundleFetcher:
    """Fetches JavaScript bundles subject to a :class:`BundleConfig` budget.

    A single instance keeps one :class:`requests.Session` (connection reuse)
    and one URL->:class:`JSBundle` cache for its lifetime. Call :meth:`reset`
    between unrelated pages if you want the per-page byte budget to restart
    without discarding the content cache.
    """

    def __init__(self, config: BundleConfig | None = None):
        self.config = config or BundleConfig()
        self._cache: Dict[str, JSBundle] = {}
        self._seen_hashes: set[str] = set()
        self._spent_bytes = 0
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.config.user_agent or _DEFAULT_UA,
            "Accept-Encoding": accept_encoding(),
            "Accept": "*/*",
        })

    def reset_budget(self) -> None:
        """Restart the per-page cumulative byte budget (keeps the cache)."""
        self._spent_bytes = 0

    def fetch(self, url: str) -> JSBundle:
        """Download one bundle, honouring cache, budget and size caps.

        Always returns a :class:`JSBundle`; failures are reported via its
        ``error`` field rather than raised.
        """
        if self.config.enable_cache and url in self._cache:
            cached = self._cache[url]
            logger.debug("cache hit %s", url)
            # Return a shallow copy flagged as cached so callers can tell.
            return JSBundle(url=url, content=cached.content, size=cached.size,
                            status=cached.status, from_cache=True, error=cached.error)

        if self._spent_bytes >= self.config.total_budget_bytes:
            return JSBundle(url=url, error="budget_exhausted")

        bundle = self._download(url)

        if self.config.enable_cache:
            self._cache[url] = bundle

        if bundle.ok:
            digest = hashlib.sha1(bundle.content.encode("utf-8", "ignore")).hexdigest()
            if digest in self._seen_hashes:
                bundle.error = "duplicate_content"
                logger.debug("duplicate content skipped %s", url)
            else:
                self._seen_hashes.add(digest)
        return bundle

    def _download(self, url: str) -> JSBundle:
        try:
            resp = self.session.get(
                url, timeout=self.config.timeout, stream=True, allow_redirects=True
            )
        except requests.RequestException as exc:
            logger.debug("fetch error %s: %s", url, exc)
            return JSBundle(url=url, error=f"{type(exc).__name__}")

        with resp:
            status = resp.status_code
            if status != 200:
                return JSBundle(url=url, status=status, error=f"http_{status}")

            # Early reject via advertised length when present.
            declared = resp.headers.get("Content-Length")
            if declared and declared.isdigit() and int(declared) > self.config.max_bytes_per_bundle:
                return JSBundle(url=url, status=status, error="too_large")

            cap = self.config.max_bytes_per_bundle
            chunks = bytearray()
            try:
                # iter_content transparently decodes the content-encoding
                # (gzip/deflate/br); we cap on the *decoded* stream.
                for chunk in resp.iter_content(chunk_size=65536):
                    if not chunk:
                        continue
                    chunks.extend(chunk)
                    if len(chunks) > cap:
                        return JSBundle(url=url, status=status, error="too_large")
            except requests.RequestException as exc:
                logger.debug("stream error %s: %s", url, exc)
                return JSBundle(url=url, status=status, error=f"{type(exc).__name__}")

            self._spent_bytes += len(chunks)
            text = clamp_text(bytes(chunks), resp.encoding or "utf-8",
                              self.config.max_scan_bytes)
            logger.debug("fetched %s (%d bytes)", url, len(chunks))
            return JSBundle(url=url, content=text, size=len(chunks), status=status)
