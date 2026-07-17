"""
WebIntelPro Enterprise X
Authentication & Identity Intelligence (Phase 2E) - Protocols

Signature tables only -- see :mod:`providers` for the shared design notes
(precision-first patterns, generic scanning lives in :mod:`detector`).

Every pattern is protocol-specific vocabulary (an RFC/spec-defined query
parameter value, a well-known discovery-document path, a SAML XML
namespace/element name, the fixed base64 prefix every JWT header starts
with) rather than a generic word, so a match is meaningful evidence even on
its own.
"""

from __future__ import annotations

from typing import Tuple

from .models import AuthCategory, Signature

PROTOCOLS: Tuple[Signature, ...] = (
    Signature("OAuth2", AuthCategory.PROTOCOL, patterns=(
        "response_type=code", "response_type=token",
        "grant_type=authorization_code", "grant_type=client_credentials",
        "grant_type=refresh_token", "/oauth2/authorize", "/oauth/authorize",
        "/oauth2/token", "/oauth/token", "/.well-known/oauth-authorization-server",
    )),

    Signature("OpenID Connect", AuthCategory.PROTOCOL, patterns=(
        "/.well-known/openid-configuration", "openid-configuration",
        "scope=openid", "response_type=id_token", "openid_connect",
        "oidc-client",
    )),

    Signature("SAML", AuthCategory.PROTOCOL, patterns=(
        "urn:oasis:names:tc:saml", "samlrequest", "samlresponse",
        "/saml/metadata", "/saml2/acs", "assertionconsumerservice",
        "entitydescriptor",
    )),

    Signature("JWT", AuthCategory.PROTOCOL, patterns=(
        # base64 of '{"alg":"' -- the fixed 11-char start of every alg-first
        # JWT header (the near-universal ordering RFC 7515's own examples
        # and most libraries -- jsonwebtoken, PyJWT -- use). A typ-first
        # header wouldn't match this; accepted as a recall gap in favor of
        # avoiding a shorter, collision-prone prefix.
        #
        # Anchored to the quote/space that virtually always precedes an
        # embedded token (JSON string value, JS literal, "Bearer <jwt>")
        # rather than the bare prefix: the bare form is pure alphanumeric,
        # so the rule engine's word-boundary matcher would require a
        # non-alphanumeric character immediately *after* it too -- which
        # never happens, since a real JWT always continues with more
        # base64url characters right after this prefix.
        '"eyJhbGciOiJ', "'eyJhbGciOiJ", " eyJhbGciOiJ",
        "jwt.io", "jsonwebtoken", "jwt_decode(", "jwtdecode(",
    )),

    Signature("PKCE", AuthCategory.PROTOCOL, patterns=(
        "code_verifier", "code_challenge", "code_challenge_method=s256",
        "code_challenge_method",
    )),
)
