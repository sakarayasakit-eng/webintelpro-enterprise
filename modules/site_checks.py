"""
WebIntelPro Enterprise X
Live Site Checks

Best-effort network probes that go beyond the single fetched page:
robots.txt, sitemap.xml, and the TLS certificate. Every probe is wrapped so
that a failure (or no network) simply yields an empty/derated result.
"""

from __future__ import annotations

import socket
import ssl
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

_TIMEOUT = 8


def _origin(url: str) -> str:
    p = urlparse(url if "://" in url else "https://" + url)
    return f"{p.scheme}://{p.netloc}"


def check_robots(url: str) -> dict:
    out = {"exists": False, "disallow": 0, "sitemaps": []}
    try:
        resp = requests.get(_origin(url) + "/robots.txt", timeout=_TIMEOUT)
        if resp.status_code == 200 and resp.text:
            out["exists"] = True
            for line in resp.text.splitlines():
                ls = line.strip().lower()
                if ls.startswith("disallow:"):
                    out["disallow"] += 1
                elif ls.startswith("sitemap:"):
                    out["sitemaps"].append(line.split(":", 1)[1].strip())
    except Exception:
        pass
    return out


def check_sitemap(url: str, robots: dict | None = None) -> dict:
    out = {"exists": False, "urls": 0}
    candidates = list((robots or {}).get("sitemaps", [])) or [_origin(url) + "/sitemap.xml"]
    for sm in candidates[:2]:
        try:
            resp = requests.get(sm, timeout=_TIMEOUT)
            if resp.status_code == 200 and "<" in resp.text:
                out["exists"] = True
                out["urls"] = resp.text.count("<loc>")
                break
        except Exception:
            continue
    return out


def check_tls(url: str) -> dict:
    out = {"checked": False, "protocol": "", "expires_in_days": None, "issuer": ""}
    p = urlparse(url if "://" in url else "https://" + url)
    if p.scheme != "https":
        return out
    host = p.hostname
    port = p.port or 443
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=_TIMEOUT) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                out["checked"] = True
                out["protocol"] = ssock.version() or ""
                cert = ssock.getpeercert()
                if cert:
                    issuer = dict(x[0] for x in cert.get("issuer", []))
                    out["issuer"] = issuer.get("organizationName", "")
                    na = cert.get("notAfter")
                    if na:
                        exp = datetime.strptime(na, "%b %d %H:%M:%S %Y %Z").replace(
                            tzinfo=timezone.utc)
                        out["expires_in_days"] = (exp - datetime.now(timezone.utc)).days
    except Exception:
        pass
    return out


def run_all(url: str) -> dict:
    robots = check_robots(url)
    return {"robots": robots, "sitemap": check_sitemap(url, robots),
            "tls": check_tls(url)}
