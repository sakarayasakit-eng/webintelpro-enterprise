"""WebIntelPro Enterprise X - Technical SEO Analyzer"""

from __future__ import annotations

from .grading import grade, clamp


class TechnicalSEOAnalyzer:

    def analyze(self, parsed, url: str = "") -> dict:
        r: dict = {}
        issues: list = []

        title = (parsed.title or "").strip()
        r["title"] = title
        r["title_length"] = len(title)
        r["title_ok"] = 30 <= len(title) <= 60

        description = parsed.meta.get("description", "").strip()
        r["meta_description"] = description
        r["description_length"] = len(description)
        r["description_ok"] = 120 <= len(description) <= 160

        h1s = [h for h in parsed.headings if h["level"] == 1]
        r["h1_count"] = len(h1s)
        r["has_h1"] = len(h1s) >= 1
        r["multiple_h1"] = len(h1s) > 1
        r["heading_count"] = len(parsed.headings)

        r["has_canonical"] = bool(parsed.canonical)
        r["canonical_absolute"] = parsed.canonical.startswith(("http://", "https://")) \
            if parsed.canonical else False
        r["has_viewport"] = bool(parsed.viewport)
        r["has_language"] = bool(parsed.language)
        r["has_robots"] = bool(parsed.robots)
        r["noindex"] = "noindex" in (parsed.robots or "").lower()
        r["nofollow"] = "nofollow" in (parsed.robots or "").lower()

        og = parsed.open_graph
        r["open_graph"] = len(og)
        r["og_complete"] = all(f"og:{k}" in og for k in ("title", "description", "image"))
        r["twitter_cards"] = len(parsed.twitter)
        r["has_twitter_card"] = any("card" in k for k in parsed.twitter)
        r["json_ld"] = len(parsed.json_ld)
        r["hreflang"] = len(parsed.hreflang)
        r["word_count"] = parsed.text_length
        r["thin_content"] = parsed.text_length < 300

        r["scripts"] = len(parsed.scripts)
        r["stylesheets"] = len(parsed.stylesheets)
        r["images"] = len(parsed.images)
        r["forms"] = len(parsed.forms)
        r["links"] = len(parsed.links)

        score = 100
        if not title:
            score -= 18; issues.append("Missing <title> tag")
        elif not r["title_ok"]:
            score -= 7; issues.append(f"Title length {len(title)} chars (aim 30-60)")
        if not description:
            score -= 10; issues.append("Missing meta description")
        elif not r["description_ok"]:
            score -= 4; issues.append(f"Meta description {len(description)} chars (aim 120-160)")
        if r["noindex"]:
            score -= 20; issues.append("Page is set to noindex (won't be indexed)")
        if not r["has_h1"]:
            score -= 10; issues.append("No H1 heading")
        elif r["multiple_h1"]:
            score -= 5; issues.append(f"Multiple H1 headings ({r['h1_count']})")
        if not r["has_canonical"]:
            score -= 6; issues.append("No canonical URL")
        elif not r["canonical_absolute"]:
            score -= 3; issues.append("Canonical URL is not absolute")
        if not r["has_viewport"]:
            score -= 7; issues.append("No viewport meta (mobile)")
        if not r["has_language"]:
            score -= 5; issues.append("No lang attribute on <html>")
        if r["open_graph"] == 0:
            score -= 4; issues.append("No Open Graph tags")
        elif not r["og_complete"]:
            score -= 2; issues.append("Incomplete Open Graph (need title/description/image)")
        if not r["has_twitter_card"]:
            score -= 2; issues.append("No Twitter Card tags")
        if r["json_ld"] == 0:
            score -= 4; issues.append("No structured data (JSON-LD)")
        if r["thin_content"]:
            score -= 5; issues.append(f"Thin content (~{parsed.text_length} chars)")

        r["score"] = clamp(score)
        r["grade"] = grade(r["score"])
        r["issues"] = issues
        return r
