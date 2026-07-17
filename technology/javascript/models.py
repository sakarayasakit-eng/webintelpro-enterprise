"""
WebIntelPro Enterprise X
JavaScript Bundle Intelligence - Data Models

Value objects shared across the JavaScript bundle intelligence sub-system.

These models deliberately hold only bundle-specific state (download config,
a fetched bundle, a raw content finding). Final detections are emitted as the
project-wide :class:`technology.models.Technology`, so bundle results flow
through exactly the same reporting/merge path as every other detection source.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(slots=True)
class BundleConfig:
    """Tunable limits for JavaScript bundle discovery and downloading.

    Every network-facing knob lives here so the feature can be bounded (and
    disabled) without touching call sites. Defaults are conservative: they cap
    both the number of bundles and the total bytes pulled so a single page can
    never trigger an unbounded download.
    """

    # Hard cap on how many distinct bundle URLs are downloaded per page.
    max_bundles: int = 12
    # Skip any single bundle larger than this (bytes). Big vendor bundles carry
    # the same signatures as smaller ones, so there is little value in paying
    # for multi-megabyte downloads.
    max_bytes_per_bundle: int = 3_000_000
    # Stop downloading once the cumulative byte budget for the page is reached.
    total_budget_bytes: int = 12_000_000
    # Only scan the first N bytes of each bundle for signatures. Framework
    # runtime markers appear near the top (banners, module headers), so this
    # keeps scanning cheap on huge bundles without losing signal.
    max_scan_bytes: int = 1_500_000
    # Per-request network timeout (seconds).
    timeout: float = 8.0
    # User-Agent used for bundle requests; falls back to the crawler default.
    user_agent: str = ""
    # Re-use an in-process content cache so a bundle referenced from several
    # pages (or twice on one page) is only fetched once.
    enable_cache: bool = True
    # Follow bundles hosted on a different origin than the page (common CDNs).
    allow_cross_origin: bool = True


@dataclass(slots=True)
class JSBundle:
    """A single JavaScript resource that was (attempted to be) downloaded.

    ``ok`` distinguishes a usable bundle from one that was skipped or failed;
    ``error`` records why so the analyzer can log a concise reason without
    raising. ``content`` is the decoded, size-capped text used for scanning.
    """

    url: str
    content: str = ""
    size: int = 0
    status: int = 0
    from_cache: bool = False
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error and bool(self.content)


@dataclass(slots=True)
class BundleFinding:
    """One technology's aggregated evidence gathered from bundle contents.

    Signatures are collected across every scanned bundle before a confidence
    score is computed, so this is the accumulator the analyzer fills in and
    then converts into a :class:`technology.models.Technology`.
    """

    name: str
    category: str
    evidence: List[str] = field(default_factory=list)
    version: Optional[str] = None
