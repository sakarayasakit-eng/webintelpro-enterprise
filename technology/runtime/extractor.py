"""
WebIntelPro Enterprise X
JavaScript Runtime Intelligence (Phase 2B) - Extraction

Turns a parsed HTML document into a :class:`RuntimeContext`: the bounded set of
code units, embedded JSON payloads and page-level facts that the rest of the
stage reasons over.

Material gathered (no browser, no execution - everything is read as text):

* **inline scripts**   - ``<script>`` bodies, where bootstraps, global
  assignments and runtime config literals live
* **embedded JSON**    - ``<script type="application/json">`` payloads such as
  ``__NEXT_DATA__``, plus JSON-LD, parsed when they are valid and small enough
* **markup**           - the raw document, for runtime markers that live in
  attributes rather than code (``astro-island``, ``q:container``, ``ng-version``)
* **bundles**          - opt-in only (:attr:`RuntimeConfig.analyze_bundles`), by
  reusing the Phase 2A fetcher rather than introducing a second downloader

Extraction is prioritised, not merely truncated: when a page has more inline
scripts than the cap allows, the ones carrying runtime markers are kept and the
rest dropped, so a cap costs the least possible signal.
"""

from __future__ import annotations

import logging
from typing import List, Tuple

from .models import CodeUnit, JSONBlob, RuntimeConfig, RuntimeContext, RuntimeSource
from .utils import clamp, safe_json_loads

logger = logging.getLogger("webintelpro.runtime.extractor")

# Cheap tokens that mark a code unit as likely to carry runtime intelligence.
# Used only for prioritisation under a cap - never to reject material outright.
_HIGH_SIGNAL_TOKENS: Tuple[str, ...] = (
    "window.", "self.__", "globalthis.", "__", "process.env", "import.meta",
    "import(", "fetch(", "graphql", "servicew", "navigator.", "createroot",
    "hydrate", "bootstrap", "/api/",
)

# Script types whose body is data, not code. Anything else (including a missing
# type, and module scripts) is treated as code.
_JSON_SCRIPT_TYPES = frozenset({
    "application/json",
    "application/ld+json",
    "importmap",
    "speculationrules",
})


class RuntimeExtractor:
    """Gathers the raw material for runtime analysis from a parsed page.

    Construction is cheap and network-free. :meth:`extract` performs no I/O
    unless :attr:`RuntimeConfig.analyze_bundles` is enabled, and never raises:
    any failure yields a smaller context, not an exception.
    """

    def __init__(self, config: RuntimeConfig | None = None):
        self.config = config or RuntimeConfig()

    # ------------------------------------------------------------------
    def extract(self, parsed, base_url: str = "") -> RuntimeContext:
        """Return the bounded :class:`RuntimeContext` for ``parsed``.

        ``parsed`` is a :class:`technology.parser.ParsedHTML`; ``base_url`` is
        the page URL, used to resolve bundle references when bundle analysis is
        enabled.
        """
        ctx = RuntimeContext(base_url=base_url)
        ctx.script_urls = list(getattr(parsed, "scripts", []) or [])
        ctx.resource_hints = list(getattr(parsed, "resource_hints", []) or [])
        ctx.manifest = getattr(parsed, "manifest", "") or ""
        ctx.html = clamp(getattr(parsed, "html", "") or "", self.config.max_html_bytes)

        budget = self.config.max_total_scan_bytes

        # 1. Inline scripts: split into code units and JSON payloads.
        code, blobs = self._split_inline(parsed)
        for blob in blobs:
            ctx.json_blobs.append(blob)

        for unit in self._prioritise(code):
            if budget <= 0:
                ctx.truncated = True
                break
            text = clamp(unit.text, min(self.config.max_bytes_per_unit, budget))
            if len(text) < len(unit.text):
                ctx.truncated = True
            budget -= len(text)
            ctx.units.append(
                CodeUnit(text=text, location=unit.location, source=unit.source)
            )

        # 2. The markup itself, for attribute-level runtime markers. Scanned by
        #    the signature/hydration passes only (see RuntimeAnalyzer), so page
        #    copy and link hrefs never pollute endpoint or env discovery.
        #    Code outranks markup, so it draws on whatever budget code left.
        if ctx.html and budget > 0:
            markup = clamp(ctx.html, budget)
            if len(markup) < len(ctx.html):
                ctx.truncated = True
            budget -= len(markup)
            ctx.units.append(
                CodeUnit(text=markup, location="html",
                         source=RuntimeSource.HTML_MARKUP)
            )
        elif ctx.html:
            ctx.truncated = True

        # 3. JSON payload bodies are also scanned as text, so a payload that
        #    failed to parse still contributes endpoint/config evidence.
        for blob in ctx.json_blobs:
            if budget <= 0:
                ctx.truncated = True
                break
            text = clamp(blob.text, min(self.config.max_bytes_per_unit, budget))
            budget -= len(text)
            ctx.units.append(
                CodeUnit(text=text, location=blob.location,
                         source=RuntimeSource.EMBEDDED_JSON)
            )

        # 4. Bundles: opt-in, reuses the Phase 2A downloader.
        if self.config.analyze_bundles:
            for unit in self._extract_bundles(parsed, base_url):
                if budget <= 0:
                    ctx.truncated = True
                    break
                text = clamp(unit.text, min(self.config.max_bytes_per_unit, budget))
                budget -= len(text)
                ctx.units.append(
                    CodeUnit(text=text, location=unit.location, source=unit.source)
                )

        ctx.scanned_bytes = sum(len(u.text) for u in ctx.units)
        logger.debug("extracted %d unit(s), %d json blob(s), %d byte(s)%s",
                     len(ctx.units), len(ctx.json_blobs), ctx.scanned_bytes,
                     " [truncated]" if ctx.truncated else "")
        return ctx

    # ------------------------------------------------------------------
    def _split_inline(self, parsed) -> Tuple[List[CodeUnit], List[JSONBlob]]:
        """Separate inline ``<script>`` bodies into code units and JSON blobs.

        Prefers a light re-parse of the raw document, because the shared
        HTMLParser keeps script *bodies* but not their ``id``/``type``
        attributes - and those attributes are exactly what names a payload
        (``id="__NEXT_DATA__"``). Falls back to the already-parsed bodies when
        the raw document is unavailable or unparseable.
        """
        html = getattr(parsed, "html", "") or ""
        if html and len(html) <= self.config.max_html_bytes:
            try:
                return self._split_from_soup(html)
            except Exception:  # noqa: BLE001 - extraction must degrade, not fail
                logger.debug("soup extraction failed; using parsed bodies",
                             exc_info=True)
        return self._split_from_parsed(parsed)

    def _split_from_soup(self, html: str) -> Tuple[List[CodeUnit], List[JSONBlob]]:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        code: List[CodeUnit] = []
        blobs: List[JSONBlob] = []
        for index, script in enumerate(soup.find_all("script")):
            if script.get("src"):
                continue
            body = script.string or script.get_text() or ""
            if not body.strip():
                continue
            stype = (script.get("type") or "").split(";")[0].strip().lower()
            identifier = script.get("id") or ""
            if stype in _JSON_SCRIPT_TYPES:
                label = identifier or stype
                blobs.append(self._make_blob(body, f"embedded_json[{label}]",
                                             identifier or stype))
            else:
                code.append(CodeUnit(text=body,
                                     location=f"inline_script[{index}]",
                                     source=RuntimeSource.INLINE_SCRIPT))
        return code, blobs

    def _split_from_parsed(self, parsed) -> Tuple[List[CodeUnit], List[JSONBlob]]:
        """Fallback split using only ``ParsedHTML`` fields (no re-parse).

        Without attributes, a payload is classified as JSON by shape: a body
        that parses as a JSON object/array is data, anything else is code.
        """
        code: List[CodeUnit] = []
        blobs: List[JSONBlob] = []
        for index, body in enumerate(getattr(parsed, "inline_scripts", []) or []):
            if not body or not body.strip():
                continue
            stripped = body.strip()
            if stripped[0] in "{[" and safe_json_loads(
                    stripped, self.config.max_json_bytes) is not None:
                blobs.append(self._make_blob(body, f"embedded_json[{index}]"))
            else:
                code.append(CodeUnit(text=body,
                                     location=f"inline_script[{index}]",
                                     source=RuntimeSource.INLINE_SCRIPT))
        return code, blobs

    def _make_blob(self, body: str, location: str, identifier: str = "") -> JSONBlob:
        """Build a :class:`JSONBlob`, parsing it when it is valid and small."""
        return JSONBlob(
            text=body,
            location=location,
            identifier=identifier,
            data=safe_json_loads(body, self.config.max_json_bytes),
        )

    # ------------------------------------------------------------------
    def _prioritise(self, units: List[CodeUnit]) -> List[CodeUnit]:
        """Cap inline units at the configured count, keeping the useful ones.

        Stable within each tier: units carrying runtime markers keep their
        document order, and are preferred over ones that carry none.
        """
        cap = self.config.max_inline_scripts
        if len(units) <= cap:
            return units
        ranked = sorted(
            enumerate(units),
            key=lambda pair: (0 if self._has_signal(pair[1].text) else 1, pair[0]),
        )
        logger.debug("capping inline scripts %d -> %d", len(units), cap)
        kept = sorted(ranked[:cap], key=lambda pair: pair[0])
        return [unit for _, unit in kept]

    @staticmethod
    def _has_signal(text: str) -> bool:
        low = text[:4000].lower()
        return any(token in low for token in _HIGH_SIGNAL_TOKENS)

    # ------------------------------------------------------------------
    def _extract_bundles(self, parsed, base_url: str) -> List[CodeUnit]:
        """Download and return bundle contents as code units (opt-in).

        Reuses :mod:`technology.javascript` for discovery and downloading -
        there is deliberately no second fetcher in this package - and is
        imported lazily so the dependency is only pulled in when used.
        """
        try:
            from ..javascript import BundleDiscovery, BundleFetcher
            from ..javascript.models import BundleConfig

            bundle_config = self.config.bundle_config or BundleConfig()
            urls = BundleDiscovery(bundle_config).discover(parsed, base_url)
            if not urls:
                return []
            fetcher = BundleFetcher(bundle_config)
            fetcher.reset_budget()
            units: List[CodeUnit] = []
            for url in urls[: self.config.max_bundles]:
                bundle = fetcher.fetch(url)
                if not bundle.ok:
                    logger.debug("bundle skipped %s (%s)", url, bundle.error)
                    continue
                units.append(CodeUnit(text=bundle.content,
                                      location=f"bundle:{url}",
                                      source=RuntimeSource.BUNDLE))
            return units
        except Exception:  # noqa: BLE001 - bundle intel is best-effort
            logger.debug("bundle extraction failed", exc_info=True)
            return []
