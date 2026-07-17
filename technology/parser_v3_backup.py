"""
WebIntelPro Enterprise X
HTML Parser v2
"""

from __future__ import annotations

from dataclasses import dataclass, field
from bs4 import BeautifulSoup


@dataclass
class ParsedHTML:

    title: str = ""

    meta: dict = field(default_factory=dict)

    scripts: list = field(default_factory=list)

    inline_scripts: list = field(default_factory=list)

    stylesheets: list = field(default_factory=list)

    links: list = field(default_factory=list)

    images: list = field(default_factory=list)

    forms: list = field(default_factory=list)

    canonical: str = ""

    language: str = ""

    viewport: str = ""

    favicon: str = ""

    open_graph: dict = field(default_factory=dict)

    twitter: dict = field(default_factory=dict)

    json_ld: list = field(default_factory=list)

    headings: list = field(default_factory=list)

    buttons: list = field(default_factory=list)

    iframes: list = field(default_factory=list)

    videos: list = field(default_factory=list)

    tables: list = field(default_factory=list)

    resource_hints: list = field(default_factory=list)

    manifest: str = ""

    theme_color: str = ""

    charset: str = ""

    robots: str = ""

class HTMLParser:

    def parse(self, html: str) -> ParsedHTML:

        parsed = ParsedHTML()

        if not html:
            return parsed

        soup = BeautifulSoup(html, "html.parser")

        if soup.title:
            parsed.title = soup.title.get_text(strip=True)

        html_tag = soup.find("html")
        if html_tag:
            parsed.language = html_tag.get("lang", "")

        for meta in soup.find_all("meta"):

            if meta.get("name"):
                parsed.meta[meta["name"].lower()] = meta.get(
                    "content",
                    "",
                )

            if meta.get("property"):

                prop = meta["property"].lower()

                if prop.startswith("og:"):
                    parsed.open_graph[prop] = meta.get(
                        "content",
                        "",
                    )

                if prop.startswith("twitter:"):
                    parsed.twitter[prop] = meta.get(
                        "content",
                        "",
                    )

        parsed.viewport = parsed.meta.get("viewport", "")
        # Stylesheets
        for link in soup.find_all("link"):

            rel = link.get("rel", [])

            if any(r.lower() == "stylesheet" for r in rel):
                href = link.get("href")
                if href:
                    parsed.stylesheets.append(href)

            if any(r.lower() == "icon" for r in rel):
                parsed.favicon = link.get("href", "")

            if any(r.lower() == "canonical" for r in rel):
                parsed.canonical = link.get("href", "")

        # External JavaScript
        for script in soup.find_all("script"):

            src = script.get("src")

            if src:
                parsed.scripts.append(src)

            else:
                content = script.get_text(strip=True)

                if content:
                    parsed.inline_scripts.append(content)

            if script.get("type") == "application/ld+json":

                data = script.get_text(strip=True)

                if data:
                    parsed.json_ld.append(data)

        # Images
        for img in soup.find_all("img"):

            src = img.get("src")

            if src:
                parsed.images.append(src)

        # Forms
        for form in soup.find_all("form"):

            parsed.forms.append({

                "action": form.get("action", ""),

                "method": form.get("method", "GET").upper(),

            })

        # Links
        for anchor in soup.find_all("a", href=True):

            parsed.links.append(anchor["href"])

        return parsed