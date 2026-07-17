"""WebIntelPro Enterprise X - HTTP Security Analyzer"""

from __future__ import annotations

import re

from .grading import grade, clamp
from technology.parser import mixed_content


class SecurityAnalyzer:

    def analyze(self, headers: dict, url: str = "", parsed=None,
                set_cookie: list | None = None) -> dict:
        headers = {k.lower(): v for k, v in headers.items()}
        set_cookie = set_cookie or []
        r: dict = {}
        issues: list = []

        r["https"] = url.lower().startswith("https://") if url else True
        r["hsts"] = "strict-transport-security" in headers
        r["csp"] = "content-security-policy" in headers
        r["x_frame_options"] = "x-frame-options" in headers
        r["x_content_type"] = "x-content-type-options" in headers
        r["referrer_policy"] = "referrer-policy" in headers
        r["permissions_policy"] = "permissions-policy" in headers
        r["server"] = headers.get("server", "")
        r["powered_by"] = headers.get("x-powered-by", "")

        score = 0
        if r["https"]:
            score += 20
        else:
            issues.append("Site not served over HTTPS")
        if r["hsts"]:
            score += 15
        else:
            issues.append("Missing Strict-Transport-Security (HSTS)")
        if r["csp"]:
            score += 20
        else:
            issues.append("Missing Content-Security-Policy")
        if r["x_frame_options"]:
            score += 10
        else:
            issues.append("Missing X-Frame-Options (clickjacking)")
        if r["x_content_type"]:
            score += 10
        else:
            issues.append("Missing X-Content-Type-Options")
        if r["referrer_policy"]:
            score += 10
        else:
            issues.append("Missing Referrer-Policy")
        if r["permissions_policy"]:
            score += 15
        else:
            issues.append("Missing Permissions-Policy")

        # ---- quality deductions ----
        if r["powered_by"]:
            issues.append(f"Leaks stack via X-Powered-By: {r['powered_by']}")

        # HSTS quality
        r["hsts_max_age"] = 0
        r["hsts_subdomains"] = False
        if r["hsts"]:
            hv = headers.get("strict-transport-security", "").lower()
            m = re.search(r"max-age=(\d+)", hv)
            r["hsts_max_age"] = int(m.group(1)) if m else 0
            r["hsts_subdomains"] = "includesubdomains" in hv
            if r["hsts_max_age"] < 15552000:
                score -= 3; issues.append("HSTS max-age below 180 days")

        # CSP quality
        r["csp_unsafe"] = False
        if r["csp"]:
            cv = headers.get("content-security-policy", "").lower()
            unsafe = [t for t in ("unsafe-inline", "unsafe-eval") if t in cv]
            if unsafe:
                r["csp_unsafe"] = True
                score -= 5; issues.append(f"CSP uses {', '.join(unsafe)}")

        # Cookie flags
        insecure = []
        for c in set_cookie:
            cl = c.lower()
            name = c.split("=", 1)[0].strip()
            flags = []
            if "secure" not in cl:
                flags.append("Secure")
            if "httponly" not in cl:
                flags.append("HttpOnly")
            if "samesite" not in cl:
                flags.append("SameSite")
            if flags:
                insecure.append(f"{name} (missing {', '.join(flags)})")
        r["insecure_cookies"] = insecure
        if insecure:
            score -= min(10, 3 * len(insecure))
            issues.append(f"{len(insecure)} cookie(s) missing security flags")

        # Mixed content
        r["mixed_content"] = mixed_content(parsed, url) if parsed and url else 0
        if r["mixed_content"]:
            score -= 8; issues.append(f"{r['mixed_content']} insecure http:// resource(s) on HTTPS page")

        r["score"] = clamp(score)
        r["grade"] = grade(r["score"])
        r["issues"] = issues
        return r
