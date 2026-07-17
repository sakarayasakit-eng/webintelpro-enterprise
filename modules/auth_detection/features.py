"""
WebIntelPro Enterprise X
Authentication & Identity Intelligence (Phase 2E) - Security Features

Signature tables only -- see :mod:`providers` for the shared design notes.

Every named feature is keyed on real, specific vocabulary: a named SDK
method (Auth0's ``getTokenSilently()``, ``loginWithPopup()``), a spec-defined
query-parameter *value* (OIDC's ``prompt=none`` / ``display=popup``), or a
well-known framework session-cookie *name* -- never a generic word like
"session" or "token" on its own.

``Session cookies`` is the one signature here keyed almost entirely on
``cookies`` rather than ``patterns``: a session cookie's *name* (never its
value) is itself strong, direct evidence of the session mechanism in use,
mirroring the project's existing "cookies" matcher-source convention
(see :mod:`technology.matcher`).
"""

from __future__ import annotations

from typing import Tuple

from .models import AuthCategory, Signature

SECURITY_FEATURES: Tuple[Signature, ...] = (
    Signature("CSRF Protection", AuthCategory.SECURITY_FEATURE, patterns=(
        "csrf_token", "csrfmiddlewaretoken", "csrf-token", "csrfToken",
    ), headers=(
        "x-csrf-token", "x-xsrf-token",
    ), cookies=(
        "XSRF-TOKEN", "csrftoken", "_csrf",
    )),

    Signature("Refresh Tokens", AuthCategory.SECURITY_FEATURE, patterns=(
        "refresh_token", "refreshToken(", "grant_type=refresh_token",
        "rotateRefreshToken",
    )),

    # Keyed on well-known framework session-cookie *names* -- see the module
    # docstring for why this is legitimate passive evidence.
    Signature("Session Cookies", AuthCategory.SECURITY_FEATURE,
              cookies=(
                  "connect.sid", "PHPSESSID", "JSESSIONID",
                  "ASP.NET_SessionId", "sessionid", "laravel_session",
              )),

    Signature("Token Storage", AuthCategory.SECURITY_FEATURE, patterns=(
        "localStorage.setItem('access_token", 'localStorage.setItem("access_token',
        "localStorage.setItem('id_token", 'localStorage.setItem("id_token',
        "localStorage.setItem('refresh_token", 'localStorage.setItem("refresh_token',
        "sessionStorage.setItem('token", 'sessionStorage.setItem("token',
        "sessionStorage.setItem('access_token", 'sessionStorage.setItem("access_token',
    )),

    Signature("Login Popup", AuthCategory.SECURITY_FEATURE, patterns=(
        "loginWithPopup(", "signInWithPopup(", "display=popup", "popup=true",
    )),

    Signature("Silent Auth", AuthCategory.SECURITY_FEATURE, patterns=(
        "checkSession(", "getTokenSilently(", "prompt=none", "silent-renew",
        "silent-callback", "signinSilent(", "renewTokenSilently(",
    )),

    Signature("MFA", AuthCategory.SECURITY_FEATURE, patterns=(
        "multi-factor", "multifactor", "mfa_required", "mfa_enrollment",
        "totp", "otpauth://", "two_factor_auth", "enrollFactor(",
    )),

    Signature("Passkeys / WebAuthn", AuthCategory.SECURITY_FEATURE, patterns=(
        "navigator.credentials.create(", "navigator.credentials.get(",
        "webauthn", "PublicKeyCredential", "startAuthentication(",
        "startRegistration(", "@simplewebauthn/browser",
        # Both forms: "passkey" alone is pure-alphanumeric, so the rule
        # engine's word-boundary matcher wouldn't match it inside the far
        # more common plural "passkeys" (the trailing "s" blocks the
        # boundary) -- see the JWT signature's comment for the same trap.
        "passkey", "passkeys",
    )),
)
