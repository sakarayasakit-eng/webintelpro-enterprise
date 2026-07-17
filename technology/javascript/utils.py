"""
WebIntelPro Enterprise X
JavaScript Bundle Intelligence - Utilities

Small, dependency-light helpers shared by the fetcher, parser and analyzer:
URL resolution/normalisation, JavaScript-URL heuristics, and detection of
whether an optional Brotli decoder is available in this environment.
"""

from __future__ import annotations

from typing import Iterable, List
from urllib.parse import urldefrag, urljoin, urlparse


def brotli_available() -> bool:
    """True if urllib3/requests can transparently decode a ``br`` response.

    The project does not hard-depend on a Brotli library, so we only advertise
    ``br`` in the Accept-Encoding header when a decoder is importable. Otherwise
    a Brotli-encoded body would arrive undecodable and the download would be
    wasted. gzip/deflate are always handled by the standard library.
    """
    for module in ("brotli", "brotlicffi"):
        try:
            __import__(module)
            return True
        except ImportError:
            continue
    return False


def accept_encoding() -> str:
    """Accept-Encoding value matching the decoders available locally."""
    return "gzip, deflate, br" if brotli_available() else "gzip, deflate"


def same_origin(url_a: str, url_b: str) -> bool:
    """Whether two absolute URLs share scheme+host (port ignored)."""
    a, b = urlparse(url_a), urlparse(url_b)
    return (a.scheme, a.hostname) == (b.scheme, b.hostname)


def resolve_url(base_url: str, ref: str) -> str:
    """Resolve a (possibly relative, possibly fragment-bearing) ref to absolute.

    Returns an empty string for refs that can never be a fetchable bundle
    (empty, data:, blob:, javascript:, or an anchor-only fragment).
    """
    if not ref:
        return ""
    ref = ref.strip()
    low = ref.lower()
    if low.startswith(("data:", "blob:", "javascript:", "mailto:", "#")):
        return ""
    absolute = urljoin(base_url, ref)
    absolute, _ = urldefrag(absolute)
    scheme = urlparse(absolute).scheme
    if scheme not in ("http", "https"):
        return ""
    return absolute


def looks_like_js(url: str) -> bool:
    """Heuristic: does this URL point at a JavaScript resource?

    Matches the obvious ``.js``/``.mjs`` (with or without a cache-busting query
    string) as well as the hashed, extension-less chunk names that modern
    bundlers emit under ``/assets/`` or ``/_next/`` style paths.
    """
    path = urlparse(url).path.lower()
    if path.endswith((".js", ".mjs", ".cjs")):
        return True
    # Hashed bundle chunks sometimes drop the extension but live in tell-tale
    # asset directories.
    return any(marker in path for marker in ("/_next/static/", "/assets/", "/_nuxt/", "/build/"))


def dedupe(urls: Iterable[str]) -> List[str]:
    """Order-preserving de-duplication of an iterable of URLs."""
    seen = set()
    out: List[str] = []
    for u in urls:
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def clamp_text(data: bytes, encoding: str, max_bytes: int) -> str:
    """Decode at most ``max_bytes`` of ``data`` to text, never raising."""
    if not data:
        return ""
    chunk = data[:max_bytes] if max_bytes and len(data) > max_bytes else data
    for enc in (encoding, "utf-8", "latin-1"):
        if not enc:
            continue
        try:
            return chunk.decode(enc, errors="ignore")
        except (LookupError, UnicodeDecodeError):
            continue
    return chunk.decode("utf-8", errors="ignore")
