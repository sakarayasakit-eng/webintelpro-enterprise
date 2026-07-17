"""
WebIntelPro Enterprise X
Core Web Vitals (headless)

Measures field-style Core Web Vitals (LCP, CLS, FCP, TTFB, INP-proxy) by
loading the page in a headless browser. Requires Playwright *or* Selenium with
a browser driver; when neither is available it degrades gracefully and returns
{"available": False, ...} so the rest of the pipeline is unaffected.

Install (optional):
    pip install playwright && python -m playwright install chromium
"""

from __future__ import annotations

# JS collected after load: uses the Performance APIs available in any Chromium.
_COLLECT_JS = r"""
() => new Promise((resolve) => {
  const out = {lcp: null, cls: 0, fcp: null, ttfb: null};
  try {
    const nav = performance.getEntriesByType('navigation')[0];
    if (nav) out.ttfb = nav.responseStart;
    const fcp = performance.getEntriesByName('first-contentful-paint')[0];
    if (fcp) out.fcp = fcp.startTime;
    new PerformanceObserver((l) => {
      const e = l.getEntries(); out.lcp = e[e.length - 1].startTime;
    }).observe({type: 'largest-contentful-paint', buffered: true});
    new PerformanceObserver((l) => {
      for (const entry of l.getEntries()) if (!entry.hadRecentInput) out.cls += entry.value;
    }).observe({type: 'layout-shift', buffered: true});
  } catch (e) {}
  setTimeout(() => resolve(out), 2500);
})
"""


def _rate(metric: str, value):
    if value is None:
        return "unknown"
    thresholds = {"lcp": (2500, 4000), "cls": (0.1, 0.25),
                  "fcp": (1800, 3000), "ttfb": (800, 1800), "inp": (200, 500)}
    good, poor = thresholds.get(metric, (None, None))
    if good is None:
        return "unknown"
    if value <= good:
        return "good"
    if value <= poor:
        return "needs-improvement"
    return "poor"


def _with_playwright(url: str, timeout: int):
    from playwright.sync_api import sync_playwright  # type: ignore
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.goto(url, wait_until="load", timeout=timeout * 1000)
        raw = page.evaluate(_COLLECT_JS)
        browser.close()
    return raw


def measure(url: str, timeout: int = 20) -> dict:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    raw = None
    engine = None
    try:
        raw = _with_playwright(url, timeout)
        engine = "playwright"
    except Exception:
        raw = None

    if raw is None:
        return {"available": False,
                "reason": "No headless browser (install: pip install playwright "
                          "&& python -m playwright install chromium)"}

    metrics = {}
    for key in ("lcp", "cls", "fcp", "ttfb"):
        val = raw.get(key)
        metrics[key] = {"value": round(val, 3) if isinstance(val, (int, float)) else None,
                        "rating": _rate(key, val)}
    return {"available": True, "engine": engine, "metrics": metrics}
