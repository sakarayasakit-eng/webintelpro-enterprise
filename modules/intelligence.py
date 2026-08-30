"""
WebIntelPro Enterprise X
Intelligence Layer

Turns raw analyzer output into a prioritized, severity-ranked list of
recommendations with concrete remediation guidance.
"""

from __future__ import annotations

SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}

# Confidence levels for the false-positive-control policy (see modules docs):
#   confirmed - directly observed in a response header, DOM attribute, or
#               other unambiguous machine-readable signal.
#   likely    - inferred from strong but indirect evidence.
#   possible  - a heuristic signal that correlates with the issue but can
#               have legitimate explanations (e.g. templated content).
#   unknown   - cannot be determined with the data this tool has access to;
#               listed for completeness, not as a finding.
CONFIDENCE_RANK = {"confirmed": 0, "likely": 1, "possible": 2, "unknown": 3}


class IntelligenceEngine:

    def recommend(self, seo, security, performance, accessibility,
                  technology=None) -> list:
        recs: list = []

        def add(sev, area, issue, fix, confidence="confirmed"):
            recs.append({"severity": sev, "area": area, "issue": issue,
                         "recommendation": fix, "confidence": confidence})

        # ---- Security ----
        if not security.get("https"):
            add("critical", "Security", "Site not served over HTTPS",
                "Install a TLS certificate and redirect all HTTP traffic to HTTPS.")
        if security.get("mixed_content"):
            add("high", "Security", f"{security['mixed_content']} insecure http:// resources",
                "Serve every sub-resource over HTTPS to avoid mixed-content blocking.")
        if not security.get("csp"):
            add("high", "Security", "No Content-Security-Policy",
                "Add a CSP header to mitigate XSS and data-injection attacks.")
        elif security.get("csp_unsafe"):
            add("medium", "Security", "CSP allows unsafe-inline / unsafe-eval",
                "Tighten the CSP; remove unsafe-inline/unsafe-eval and use nonces or hashes.")
        if not security.get("hsts"):
            add("high", "Security", "No HSTS header",
                "Send Strict-Transport-Security to force HTTPS on repeat visits.")
        elif security.get("hsts_max_age", 0) and security["hsts_max_age"] < 15552000:
            add("low", "Security", "HSTS max-age below 180 days",
                "Increase HSTS max-age to at least 15552000 (180 days).")
        if security.get("insecure_cookies"):
            add("medium", "Security",
                f"{len(security['insecure_cookies'])} cookie(s) missing security flags",
                "Set Secure, HttpOnly and SameSite on session/sensitive cookies.")
        if not security.get("x_frame_options"):
            add("medium", "Security", "No X-Frame-Options",
                "Set X-Frame-Options: SAMEORIGIN to prevent clickjacking.")
        if not security.get("x_content_type"):
            add("medium", "Security", "No X-Content-Type-Options",
                "Set X-Content-Type-Options: nosniff to block MIME sniffing.")
        if not security.get("referrer_policy"):
            add("low", "Security", "No Referrer-Policy",
                "Add a Referrer-Policy header to limit referrer leakage.")
        if not security.get("permissions_policy"):
            add("low", "Security", "No Permissions-Policy",
                "Add a Permissions-Policy header to restrict powerful browser features.")
        if security.get("powered_by"):
            add("low", "Security", f"Stack disclosed via X-Powered-By: {security['powered_by']}",
                "Remove or obscure the X-Powered-By header to reduce fingerprinting.")

        # ---- SEO ----
        if seo.get("noindex"):
            add("high", "SEO", "Page is set to noindex",
                "Remove the noindex directive if this page should appear in search.")
        if not seo.get("title"):
            add("high", "SEO", "Missing <title> tag",
                "Add a unique, descriptive 30-60 character title.")
        elif not seo.get("title_ok"):
            add("low", "SEO", f"Title length {seo.get('title_length')} chars",
                "Aim for a 30-60 character title.")
        if not seo.get("meta_description"):
            add("medium", "SEO", "Missing meta description",
                "Add a 120-160 character meta description for better SERP snippets.")
        if not seo.get("has_h1"):
            add("medium", "SEO", "No H1 heading",
                "Add exactly one H1 that describes the page.")
        elif seo.get("multiple_h1"):
            add("low", "SEO", f"Multiple H1 headings ({seo.get('h1_count')})",
                "Use a single H1 per page for a clear document outline.")
        if not seo.get("has_canonical"):
            add("low", "SEO", "No canonical URL",
                "Add a rel=canonical link to avoid duplicate-content issues.")
        elif not seo.get("canonical_absolute"):
            add("low", "SEO", "Canonical URL is not absolute",
                "Use an absolute canonical URL (https://...).")
        if not seo.get("has_viewport"):
            add("medium", "SEO", "No viewport meta tag",
                "Add a responsive viewport meta tag for mobile ranking.")
        if seo.get("open_graph") == 0:
            add("low", "SEO", "No Open Graph tags",
                "Add Open Graph tags for better social sharing.")
        elif not seo.get("og_complete"):
            add("low", "SEO", "Incomplete Open Graph tags",
                "Provide og:title, og:description and og:image.")
        if seo.get("json_ld") == 0:
            add("low", "SEO", "No structured data",
                "Add JSON-LD structured data to enable rich results.")
        if seo.get("thin_content"):
            add("low", "SEO", "Thin page content (low word count)",
                "Add more substantive text content for search relevance.",
                confidence="possible")

        # ---- Performance ----
        if not performance.get("gzip") and not performance.get("brotli"):
            add("high", "Performance", "No text compression",
                "Enable gzip or brotli compression on the server/CDN.")
        if not performance.get("cache_control"):
            add("medium", "Performance", "No Cache-Control header",
                "Add Cache-Control headers so browsers/CDNs can cache assets.")
        if performance.get("ttfb", 0) and performance["ttfb"] > 1.2:
            add("medium", "Performance", f"Slow TTFB ({performance['ttfb']:.2f}s)",
                "Reduce server response time (caching, DB tuning, edge rendering).")
        if performance.get("scripts", 0) > 40:
            add("medium", "Performance", f"High script count ({performance['scripts']})",
                "Bundle, defer, or code-split scripts to reduce blocking requests.")
        if performance.get("third_party", 0) > 20:
            add("low", "Performance", f"Many third-party resources ({performance['third_party']})",
                "Audit third-party scripts; lazy-load or remove non-essential ones.")
        if performance.get("redirects", 0) >= 2:
            add("low", "Performance", f"Redirect chain ({performance['redirects']} hops)",
                "Point links directly at the final URL to avoid redirect latency.")
        if performance.get("http_version_reliable") and performance.get("http_version") in ("1.0", "1.1"):
            add("low", "Performance", f"Legacy HTTP/{performance['http_version']}",
                "Enable HTTP/2 or HTTP/3 for multiplexed, faster delivery.")

        # ---- Accessibility ----
        total = accessibility.get("total_images", 0)
        missing = accessibility.get("missing_alt", 0)
        if total and missing:
            ratio = missing / total
            sev = "high" if ratio > 0.5 else "medium" if ratio > 0.2 else "low"
            add(sev, "Accessibility", f"{missing}/{total} images missing alt text",
                "Add descriptive alt attributes (empty alt for decorative images).")
        if accessibility.get("unlabelled_inputs"):
            add("medium", "Accessibility",
                f"{accessibility['unlabelled_inputs']} form field(s) without a label",
                "Associate a <label> (or aria-label) with every form control.")
        if not accessibility.get("language"):
            add("medium", "Accessibility", "No lang attribute",
                "Set <html lang=\"...\"> so assistive tech announces the language.")
        if not accessibility.get("has_main") and accessibility.get("landmark_count", 0) == 0:
            add("low", "Accessibility", "No landmark regions",
                "Use <main>, <nav>, <header>, <footer> for screen-reader navigation.")
        if accessibility.get("links_without_text"):
            add("low", "Accessibility",
                f"{accessibility['links_without_text']} link(s) without text",
                "Give every link discernible text or an aria-label.")
        if accessibility.get("skipped_heading_levels"):
            add("low", "Accessibility", "Skipped heading levels",
                "Keep headings sequential (h1 -> h2 -> h3) for screen readers.")

        recs.sort(key=lambda r: SEVERITY_RANK.get(r["severity"], 9))
        return recs

    def site_recommendations(self, site: dict) -> list:
        """Recommendations derived from live site checks (robots/sitemap/TLS)."""
        recs = []
        def add(sev, area, issue, fix, confidence="confirmed"):
            recs.append({"severity": sev, "area": area, "issue": issue,
                         "recommendation": fix, "confidence": confidence})
        robots = site.get("robots", {})
        sitemap = site.get("sitemap", {})
        tls = site.get("tls", {})
        if robots and not robots.get("exists"):
            add("low", "SEO", "No robots.txt",
                "Add a robots.txt to guide crawlers and reference your sitemap.",
                confidence="confirmed")
        if sitemap and not sitemap.get("exists"):
            add("low", "SEO", "No sitemap.xml (not found at the discovered location)",
                "Publish an XML sitemap and reference it from robots.txt.",
                confidence="likely")
        if tls.get("checked"):
            days = tls.get("expires_in_days")
            if days is not None:
                if days < 0:
                    add("critical", "Security", "TLS certificate has expired",
                        "Renew the TLS certificate immediately.")
                elif days < 15:
                    add("high", "Security", f"TLS certificate expires in {days} days",
                        "Renew the certificate before it expires.")
                elif days < 30:
                    add("medium", "Security", f"TLS certificate expires in {days} days",
                        "Schedule certificate renewal soon.")
            if tls.get("protocol") in ("TLSv1", "TLSv1.1"):
                add("high", "Security", f"Outdated TLS protocol ({tls['protocol']})",
                    "Disable TLS 1.0/1.1 and require TLS 1.2+.")
        recs.sort(key=lambda r: SEVERITY_RANK.get(r["severity"], 9))
        return recs

    def summarize(self, recs: list) -> dict:
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for r in recs:
            counts[r["severity"]] = counts.get(r["severity"], 0) + 1
        return {"total": len(recs), "by_severity": counts}
