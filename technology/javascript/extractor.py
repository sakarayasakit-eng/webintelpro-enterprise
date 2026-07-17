"""
WebIntelPro Enterprise X
JavaScript Bundle Intelligence - Version Extraction

Recovers a technology's version from bundle contents, but only when the
evidence is unambiguous. Minified bundles rarely carry reliable version
strings, and a mis-attributed version is worse than none, so extraction is
deliberately conservative: a semver is reported only when it sits directly
next to a package/library anchor token (e.g. ``react-dom@18.2.0``) or in a
recognised banner comment (``/*! Vue.js v3.4.21 */``).
"""

from __future__ import annotations

import re
from typing import List, Optional

# A three-part (or two-part) dotted semver, optionally prefixed by v.
_SEMVER = r"v?(\d+\.\d+(?:\.\d+)?(?:-[0-9A-Za-z.]+)?)"

# Banner style: "<name> v1.2.3" typically emitted at the top of a UMD build.
_BANNER = re.compile(r"[/*!\s]([A-Za-z][\w.\- ]{1,30}?)\s+v(\d+\.\d+\.\d+)")


class VersionExtractor:
    """Extracts high-confidence versions for a technology from bundle text."""

    def extract(self, anchors: List[str], text: str) -> Optional[str]:
        """Return a version string if an anchor is immediately followed by a
        semver, else ``None``. ``anchors`` are package specifiers such as
        ``react-dom@`` or ``@angular/core@``.
        """
        if not text or not anchors:
            return None
        low = text.lower()
        for anchor in anchors:
            token = anchor.lower()
            start = 0
            while True:
                idx = low.find(token, start)
                if idx == -1:
                    break
                tail = text[idx + len(token): idx + len(token) + 24]
                m = re.match(_SEMVER, tail)
                if m:
                    return m.group(1)
                start = idx + len(token)
        return None

    def banner_version(self, name: str, text: str) -> Optional[str]:
        """Return a version parsed from a UMD-style banner naming ``name``."""
        if not text:
            return None
        needle = name.split(".")[0].lower()  # "Vue.js" -> "vue"
        head = text[:4000]  # banners live at the very top of the file
        for match in _BANNER.finditer(head):
            if needle in match.group(1).lower():
                return match.group(2)
        return None
