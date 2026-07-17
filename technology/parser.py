"""
WebIntelPro Enterprise X
HTML Parser v4

Extracts structured signals for technology fingerprinting AND the analyzer
modules (SEO / security / performance / accessibility).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List
from urllib.parse import urlparse

from bs4 import BeautifulSoup

_LANDMARK_TAGS = ("header", "nav", "main", "footer", "aside")
_LANDMARK_ROLES = ("banner", "navigation", "main", "contentinfo", "complementary", "search")


@dataclass
class ParsedHTML:
    html: str = ""            # raw document, for fingerprints that must scan
                              # signals living outside parsed nodes (asset-CDN
                              # hosts in <img>/srcset, CSP-only tokens, etc.)
    title: str = ""
    meta: dict = field(default_factory=dict)
    scripts: list = field(default_factory=list)
    inline_scripts: list = field(default_factory=list)
    stylesheets: list = field(default_factory=list)
    links: list = field(default_factory=list)
    images: list = field(default_factory=list)          # {src, alt}
    forms: list = field(default_factory=list)
    inputs: list = field(default_factory=list)           # {type,id,labelled,...}
    canonical: str = ""
    language: str = ""
    viewport: str = ""
    favicon: str = ""
    open_graph: dict = field(default_factory=dict)
    twitter: dict = field(default_factory=dict)
    json_ld: list = field(default_factory=list)
    headings: list = field(default_factory=list)
    iframes: list = field(default_factory=list)
    resource_hints: list = field(default_factory=list)
    manifest: str = ""
    theme_color: str = ""
    charset: str = ""
    robots: str = ""
    generator: str = ""
    hreflang: list = field(default_factory=list)
    landmarks: dict = field(default_factory=dict)
    aria_count: int = 0
    skip_link: bool = False
    meta_refresh: str = ""
    links_without_text: int = 0
    buttons_without_text: int = 0
    text_length: int = 0
    dom_attr_text: str = ""

    def meta_text(self) -> str:
        return " ".join(str(x) for x in (list(self.meta.keys()) + list(self.meta.values())))

    def dom_text(self) -> str:
        heading_text = " ".join(h["text"] for h in self.headings)
        return " ".join([self.title, heading_text, " ".join(self.links), self.dom_attr_text])


class HTMLParser:

    ATTR_SIGNALS = ("class", "id", "data-", "ng-", "v-", "x-", "wire:")

    def parse(self, html: str) -> ParsedHTML:
        p = ParsedHTML()
        if not html:
            return p
        p.html = html
        soup = BeautifulSoup(html, "html.parser")

        if soup.title:
            p.title = soup.title.get_text(strip=True)
        html_tag = soup.find("html")
        if html_tag:
            p.language = html_tag.get("lang", "")

        for meta in soup.find_all("meta"):
            name = (meta.get("name") or "").lower()
            if name:
                content = meta.get("content", "")
                p.meta[name] = content
                if name == "generator":
                    p.generator = content
                elif name == "robots":
                    p.robots = content
                elif name == "viewport":
                    p.viewport = content
                elif name == "theme-color":
                    p.theme_color = content
            prop = (meta.get("property") or "").lower()
            if prop.startswith("og:"):
                p.open_graph[prop] = meta.get("content", "")
            if prop.startswith("twitter:") or name.startswith("twitter:"):
                p.twitter[prop or name] = meta.get("content", "")
            if (meta.get("http-equiv") or "").lower() == "refresh":
                p.meta_refresh = meta.get("content", "")
            if meta.get("charset"):
                p.charset = meta.get("charset", "")
        p.viewport = p.viewport or p.meta.get("viewport", "")

        for link in soup.find_all("link"):
            rel = [r.lower() for r in link.get("rel", [])]
            href = link.get("href", "")
            if "stylesheet" in rel and href:
                p.stylesheets.append(href)
            if "icon" in rel and href:
                p.favicon = href
            if "canonical" in rel and href:
                p.canonical = href
            if "manifest" in rel and href:
                p.manifest = href
            if "alternate" in rel and link.get("hreflang"):
                p.hreflang.append(link.get("hreflang"))
            if any(r in rel for r in ("preconnect", "dns-prefetch", "preload", "prefetch", "modulepreload")) and href:
                p.resource_hints.append(href)

        for script in soup.find_all("script"):
            src = script.get("src")
            if src:
                p.scripts.append(src)
            else:
                content = script.get_text(strip=True)
                if content:
                    p.inline_scripts.append(content)
            if (script.get("type") or "").lower() == "application/ld+json":
                data = script.get_text(strip=True)
                if data:
                    p.json_ld.append(data)

        for img in soup.find_all("img"):
            p.images.append({"src": img.get("src", ""), "alt": img.get("alt", None)})

        label_for = {lb.get("for") for lb in soup.find_all("label") if lb.get("for")}
        for form in soup.find_all("form"):
            p.forms.append({"action": form.get("action", ""),
                            "method": (form.get("method", "GET") or "GET").upper()})
        for inp in soup.find_all(["input", "select", "textarea"]):
            itype = (inp.get("type") or "text").lower()
            if itype in ("hidden", "submit", "button", "reset", "image"):
                continue
            labelled = bool(
                (inp.get("id") and inp.get("id") in label_for)
                or inp.get("aria-label") or inp.get("aria-labelledby") or inp.get("title")
            )
            p.inputs.append({"type": itype, "id": inp.get("id", ""), "labelled": labelled})

        for anchor in soup.find_all("a", href=True):
            p.links.append(anchor["href"])
            text = anchor.get_text(strip=True)
            if not text and not (anchor.get("aria-label") or anchor.find("img")):
                p.links_without_text += 1
            href = anchor["href"]
            if href.startswith("#") and "skip" in (anchor.get_text(strip=True).lower()):
                p.skip_link = True

        for btn in soup.find_all("button"):
            if not btn.get_text(strip=True) and not btn.get("aria-label"):
                p.buttons_without_text += 1

        for level in range(1, 7):
            for tag in soup.find_all(f"h{level}"):
                p.headings.append({"level": level, "text": tag.get_text(strip=True)})

        for frame in soup.find_all("iframe"):
            if frame.get("src"):
                p.iframes.append(frame.get("src"))

        # landmarks
        landmarks = {t: bool(soup.find(t)) for t in _LANDMARK_TAGS}
        for role in _LANDMARK_ROLES:
            if soup.find(attrs={"role": role}):
                landmarks[role] = True
        p.landmarks = landmarks

        # aria usage count
        aria = 0
        for tag in soup.find_all(True):
            for k in tag.attrs:
                if k.lower().startswith("aria-") or k.lower() == "role":
                    aria += 1
        p.aria_count = aria

        body = soup.find("body")
        p.text_length = len((body or soup).get_text(" ", strip=True))
        p.dom_attr_text = self._attr_blob(soup)
        return p

    def _attr_blob(self, soup) -> str:
        chunks: List[str] = []
        for tag in soup.find_all(True):
            for key, value in (tag.attrs or {}).items():
                low = key.lower()
                if low.startswith(self.ATTR_SIGNALS) or low in ("class", "id"):
                    if isinstance(value, (list, tuple)):
                        value = " ".join(value)
                    chunks.append(f"{low} {value}")
        return " ".join(chunks)


def resource_hosts(parsed, page_url: str):
    """Return (third_party_count, total_resources) for scripts+styles+images."""
    page_host = urlparse(page_url).netloc.split(":")[0].lower()
    base = page_host[4:] if page_host.startswith("www.") else page_host
    resources = (list(parsed.scripts) + list(parsed.stylesheets)
                 + [i.get("src", "") for i in parsed.images])
    third = 0
    total = 0
    for r in resources:
        if not r or r.startswith(("data:", "#")):
            continue
        total += 1
        host = urlparse(r).netloc.split(":")[0].lower()
        if not host:
            continue  # relative -> first party
        host = host[4:] if host.startswith("www.") else host
        if base and base not in host and host not in base:
            third += 1
    return third, total


def mixed_content(parsed, page_url: str):
    """On an HTTPS page, return count of http:// sub-resources (mixed content)."""
    if not page_url.lower().startswith("https://"):
        return 0
    res = (list(parsed.scripts) + list(parsed.stylesheets)
           + [i.get("src", "") for i in parsed.images])
    return sum(1 for r in res if r and r.lower().startswith("http://"))
