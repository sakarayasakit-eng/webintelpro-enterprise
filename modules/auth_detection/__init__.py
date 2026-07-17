"""
WebIntelPro Enterprise X
Authentication & Identity Intelligence (Phase 2E)

An additive, opt-in detection capability that passively identifies a page's
authentication architecture -- Auth-as-a-Service providers (Auth0, Clerk,
Firebase Auth, AWS Cognito, Supabase Auth, Descope, FusionAuth, Stytch,
Magic.link), enterprise identity providers (Okta, Azure Entra ID, Keycloak),
protocols (OAuth2, OpenID Connect, SAML, JWT, PKCE) and security features
(CSRF protection, refresh tokens, session cookies, token storage, login
popup, silent auth, MFA, passkeys/WebAuthn) -- from the HTML and JavaScript
already fetched for a page, plus response header and cookie *names*.

No browser automation, no login, no credentials, no brute force: every
signal here is read out of material the crawler already fetched. Header and
cookie *values* are never inspected, only the names the server chose to
send/set, so this cannot leak session-token or credential content.

Public surface
--------------
* :class:`AuthDetector`        - the orchestrator; returns an
  :class:`AuthDetectionAnalysis` carrying both
  :class:`technology.models.Technology` detections and the structured
  :class:`AuthDetectionReport`. This is what
  :class:`technology.detector.TechnologyDetector` calls when
  ``detect(analyze_auth=True)``.
* :class:`AuthDetectionConfig` - every limit and switch for the stage
  (network-free, always).
* :mod:`providers`, :mod:`protocols`, :mod:`features` - the per-category
  signature tables; extending detection normally means adding a pattern to
  one of these.

The sub-system introduces no parallel machinery: it emits the project-wide
``Technology`` model and reuses the existing ``RuleEngine``, ``VersionEngine``
and ``ConfidenceEngine`` for all matching, version extraction and scoring --
mirroring :mod:`modules.ai_detection` (Phase 2D) almost exactly, plus one
addition: cookie-*name* scanning (see :mod:`detector`'s ``_scan_cookies``).
"""

from __future__ import annotations

from . import features, protocols, providers
from .detector import AUTH_EVIDENCE_SOURCE, ALL_SIGNATURES, AuthDetector
from .models import (
    AuthCategory,
    AuthDetectionAnalysis,
    AuthDetectionConfig,
    AuthDetectionReport,
    AuthFinding,
    DiscoverySource,
    Signature,
)

__all__ = [
    # orchestration
    "AuthDetector",
    "AuthDetectionAnalysis",
    "AuthDetectionConfig",
    # signature tables
    "providers",
    "protocols",
    "features",
    "ALL_SIGNATURES",
    # models
    "AuthDetectionReport",
    "AuthFinding",
    "Signature",
    "AuthCategory",
    "DiscoverySource",
    # confidence source key
    "AUTH_EVIDENCE_SOURCE",
]
