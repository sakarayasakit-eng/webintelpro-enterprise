"""
WebIntelPro Enterprise X
JavaScript Bundle Intelligence - Discovery

Turns a parsed HTML document into the list of JavaScript bundle URLs worth
downloading. Responsibilities are limited to *finding* URLs; downloading and
scanning live in :mod:`fetcher` and :mod:`detector`.

Sources considered:
  * ``<script src>``            - classic and ``type="module"`` scripts
  * resource hints              - ``<link rel=preload/modulepreload/prefetch>``
                                  pointing at JavaScript
  * dynamic imports             - ``import("...")`` / ``import(`...`)`` and
                                  ``from "..."`` references found in inline code
"""

from __future__ import annotations

import logging
import re
from typing import List

from .models import BundleConfig
from .utils import dedupe, looks_like_js, resolve_url, same_origin

logger = logging.getLogger("webintelpro.js.discovery")

# Dynamic import + static-from specifiers inside inline scripts. Kept
# deliberately narrow (quoted string argument only) to avoid capturing
# arbitrary parentheses.
_DYNAMIC_IMPORT = re.compile(r"""import\s*\(\s*['"`]([^'"`]+)['"`]\s*\)""")
_STATIC_FROM = re.compile(r"""\bfrom\s+['"]([^'"]+\.m?js)['"]""")


class BundleDiscovery:
    """Discovers candidate JavaScript bundle URLs from a parsed document.

    The public entry point is :meth:`discover`, which returns a de-duplicated,
    origin-filtered list of absolute URLs capped at ``config.max_bundles``.
    """

    def __init__(self, config: BundleConfig | None = None):
        self.config = config or BundleConfig()

    def discover(self, parsed, base_url: str) -> List[str]:
        """Return absolute, unique bundle URLs for ``parsed`` at ``base_url``."""
        candidates: List[str] = []

        # 1. <script src> (module scripts are captured here too - the HTML
        #    parser records every script's src regardless of type).
        for src in getattr(parsed, "scripts", []) or []:
            candidates.append(src)

        # 2. Resource hints that reference JavaScript (preload/modulepreload).
        for href in getattr(parsed, "resource_hints", []) or []:
            if looks_like_js(resolve_url(base_url, href) or href):
                candidates.append(href)

        # 3. Dynamic imports / module specifiers inside inline scripts.
        for code in getattr(parsed, "inline_scripts", []) or []:
            candidates.extend(self._extract_dynamic(code))

        resolved = []
        for ref in candidates:
            url = resolve_url(base_url, ref)
            if not url:
                continue
            if not looks_like_js(url):
                continue
            if not self.config.allow_cross_origin and not same_origin(base_url, url):
                continue
            resolved.append(url)

        unique = dedupe(resolved)
        if len(unique) > self.config.max_bundles:
            logger.debug(
                "capping discovered bundles %d -> %d", len(unique), self.config.max_bundles
            )
            unique = unique[: self.config.max_bundles]
        logger.debug("discovered %d bundle URL(s) at %s", len(unique), base_url)
        return unique

    @staticmethod
    def _extract_dynamic(code: str) -> List[str]:
        refs = _DYNAMIC_IMPORT.findall(code or "")
        refs += _STATIC_FROM.findall(code or "")
        return refs
