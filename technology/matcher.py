"""
WebIntelPro Enterprise X
Enterprise Fingerprint Matcher
"""

from __future__ import annotations

from typing import Dict

from .rules import RuleEngine, RuleResult


class FingerprintMatcher:

    def __init__(self):
        self.engine = RuleEngine()

    def evaluate(
        self,
        rule: dict,
        parsed,
        headers: dict,
        cookies: dict | None = None,
    ) -> Dict[str, RuleResult]:

        cookies = cookies or {}

        header_text = " ".join(
            f"{k}:{v}"
            for k, v in headers.items()
        ).lower()

        cookie_header = (
            headers.get("set-cookie", "")
            or headers.get("Set-Cookie", "")
        )

        cookie_text = (
            " ".join(cookies.keys())
            + " "
            + " ".join(cookies.values())
            + " "
            + cookie_header
        ).lower()

        # Sources derived purely from the parsed document are constant across
        # every fingerprint in a single detect() pass, so build+lowercase them
        # once and cache on the parsed object. Without this the raw-HTML source
        # (up to ~1 MB) would be lowercased once per rule (~500x per page).
        base = getattr(parsed, "_match_sources", None)
        if base is None:
            base = {
                "meta": parsed.meta_text().lower(),
                "scripts": " ".join(parsed.scripts).lower(),
                "inline": " ".join(parsed.inline_scripts).lower(),
                "stylesheets": " ".join(parsed.stylesheets).lower(),
                "dom": parsed.dom_text().lower(),
                "json_ld": " ".join(parsed.json_ld).lower(),
                "favicon": (parsed.favicon or "").lower(),
                "canonical": (parsed.canonical or "").lower(),
                "html": (getattr(parsed, "html", "") or "").lower(),
                "body": (getattr(parsed, "body_text", "") or "").lower(),
                "comments": " ".join(getattr(parsed, "comments", [])).lower(),
                "url": (getattr(parsed, "url", "") or "").lower(),
            }
            try:
                parsed._match_sources = base
            except (AttributeError, TypeError):
                pass  # not cacheable (e.g. slotted); correctness unaffected

        # headers/cookies come from the request args, not the parsed doc.
        sources = {"headers": header_text, "cookies": cookie_text, **base}

        results: Dict[str, RuleResult] = {}

        for source_name, source_text in sources.items():

            patterns = rule.get(source_name, [])

            if not patterns:
                continue

            if not source_text:
                continue

            results[source_name] = self.engine.match(
                patterns,
                source_text,
            )

        return results