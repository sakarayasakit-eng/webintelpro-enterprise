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