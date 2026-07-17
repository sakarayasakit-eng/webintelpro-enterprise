"""WebIntelPro Enterprise X - Accessibility Analyzer"""

from __future__ import annotations

from .grading import grade, clamp


class AccessibilityAnalyzer:

    def analyze(self, parsed) -> dict:
        r: dict = {}
        issues: list = []

        r["language"] = bool(parsed.language)

        total = len(parsed.images)
        missing = sum(1 for img in parsed.images
                      if isinstance(img, dict) and not (img.get("alt") or "").strip())
        r["total_images"] = total
        r["missing_alt"] = missing

        h1s = [h for h in parsed.headings if h["level"] == 1]
        r["has_h1"] = len(h1s) >= 1
        r["heading_count"] = len(parsed.headings)

        levels = [h["level"] for h in parsed.headings]
        skipped, prev = False, 0
        for lvl in levels:
            if prev and lvl > prev + 1:
                skipped = True
                break
            prev = lvl
        r["skipped_heading_levels"] = skipped

        r["forms"] = len(parsed.forms)
        r["inputs"] = len(parsed.inputs)
        r["unlabelled_inputs"] = sum(1 for i in parsed.inputs if not i.get("labelled"))
        lm = parsed.landmarks or {}
        r["has_main"] = bool(lm.get("main"))
        r["landmark_count"] = sum(1 for v in lm.values() if v)
        r["aria_count"] = parsed.aria_count
        r["skip_link"] = parsed.skip_link
        r["links_without_text"] = parsed.links_without_text
        r["buttons_without_text"] = parsed.buttons_without_text

        score = 100
        if not r["language"]:
            score -= 12; issues.append("No lang attribute on <html>")
        if total:
            ratio = missing / total
            if ratio > 0.5:
                score -= 20; issues.append(f"{missing}/{total} images missing alt text")
            elif ratio > 0.2:
                score -= 10; issues.append(f"{missing}/{total} images missing alt text")
            elif missing:
                score -= 4; issues.append(f"{missing} image(s) missing alt text")
        if not r["has_h1"]:
            score -= 8; issues.append("No H1 heading (document structure)")
        if skipped:
            score -= 6; issues.append("Skipped heading levels (hierarchy)")
        if r["unlabelled_inputs"]:
            score -= min(15, 4 * r["unlabelled_inputs"])
            issues.append(f"{r['unlabelled_inputs']} form field(s) without a label")
        if not r["has_main"] and r["landmark_count"] == 0:
            score -= 8; issues.append("No landmark regions (main/nav/header/footer)")
        elif not r["has_main"]:
            score -= 4; issues.append("No <main> landmark")
        if r["links_without_text"]:
            score -= min(10, 3 * r["links_without_text"])
            issues.append(f"{r['links_without_text']} link(s) without discernible text")
        if r["buttons_without_text"]:
            score -= min(8, 3 * r["buttons_without_text"])
            issues.append(f"{r['buttons_without_text']} button(s) without discernible text")

        r["score"] = clamp(score)
        r["grade"] = grade(r["score"])
        r["issues"] = issues
        return r
