"""
WebIntelPro Enterprise X
Authentication & Identity Intelligence (Phase 2E) - Providers & Identity Providers

Signature tables only -- matching happens once, generically, in
:mod:`detector`. Each :class:`~modules.auth_detection.models.Signature`
pairs a display name with the patterns that identify it in page text (client
SDK imports/npm package names, API host names, environment-variable names,
SDK class/method names), response header *names*, or cookie *names*.

Precision over recall, mirroring :mod:`modules.ai_detection.providers`:
every pattern here is a multi-character, brand- or host-specific token --
never a bare dictionary word -- so a single stray match is still meaningful
evidence.

Two buckets, matching the reporter's requested grouping:

* ``PROVIDERS`` -- Auth-as-a-Service / CIAM platforms a site integrates as a
  client (Auth0, Clerk, Firebase Auth, AWS Cognito, Supabase Auth, Descope,
  FusionAuth, Stytch, Magic.link).
* ``IDENTITY_PROVIDERS`` -- enterprise SSO/IdP systems (Okta, Azure Entra
  ID, Keycloak) -- the classic "Identity Provider" role in SAML/OIDC
  federation.

Cookie-name evidence is used sparingly and only where the name is both
well-documented and distinctive enough to avoid collisions with unrelated
frameworks (e.g. Clerk's ``__client_uat`` is used, but Clerk's ``__session``
is deliberately skipped -- Remix.run's own session-cookie convention is also
literally named ``__session``, which would misattribute Remix apps as
Clerk).
"""

from __future__ import annotations

from typing import Tuple

from .models import AuthCategory, Signature

# ---------------------------------------------------------------------------
# Providers -- Auth-as-a-Service / CIAM platforms.
# ---------------------------------------------------------------------------
PROVIDERS: Tuple[Signature, ...] = (
    Signature("Auth0", AuthCategory.PROVIDER, patterns=(
        ".auth0.com", "auth0-js", "auth0-spa-js", "@auth0/auth0-react",
        "@auth0/nextjs-auth0", "@auth0/auth0-angular", "@auth0/auth0-spa-js",
        "Auth0Client(", "new auth0.WebAuth(", "AUTH0_DOMAIN", "AUTH0_CLIENT_ID",
        "loginWithRedirect(", "auth0.authorize(",
    )),

    Signature("Clerk", AuthCategory.PROVIDER, patterns=(
        "clerk.dev", "clerk.accounts.dev", "@clerk/nextjs", "@clerk/clerk-react",
        "@clerk/clerk-js", "@clerk/clerk-sdk-node", "ClerkProvider",
        "window.Clerk", "clerk-frontend-api", "CLERK_PUBLISHABLE_KEY",
        "CLERK_SECRET_KEY",
    ), headers=(
        "x-clerk-auth-status", "x-clerk-auth-reason", "x-clerk-auth-message",
    ), cookies=("__client_uat",)),

    Signature("Firebase Auth", AuthCategory.PROVIDER, patterns=(
        "identitytoolkit.googleapis.com", "securetoken.googleapis.com",
        "firebase/auth", "signInWithEmailAndPassword(", "signInWithPopup(",
        "onAuthStateChanged(", "firebaseui-auth", "FIREBASE_API_KEY",
        "getAuth(firebase",
    )),

    Signature("AWS Cognito", AuthCategory.PROVIDER, patterns=(
        "cognito-idp.", "cognito-identity.amazonaws.com",
        "amazon-cognito-identity-js", "aws-amplify/auth", "CognitoUserPool(",
        "CognitoUser(", "COGNITO_USER_POOL_ID", "COGNITO_CLIENT_ID",
        "userPoolWebClientId",
    )),

    Signature("Supabase Auth", AuthCategory.PROVIDER, patterns=(
        "@supabase/auth-js", "@supabase/gotrue-js", "supabase.auth.getSession(",
        "supabase.auth.signInWithOAuth(", "supabase.auth.onAuthStateChange(",
        "supabase.auth.signInWithPassword(", "supabase.auth.signInWithOtp(",
    )),

    Signature("Descope", AuthCategory.PROVIDER, patterns=(
        "descope.com", "@descope/react-sdk", "@descope/node-sdk",
        "@descope/web-component", "<descope-wc", "DESCOPE_PROJECT_ID",
    )),

    Signature("FusionAuth", AuthCategory.PROVIDER, patterns=(
        "fusionauth.io", "@fusionauth/typescript-client", "FusionAuthClient(",
        "FUSIONAUTH_API_KEY",
    )),

    Signature("Stytch", AuthCategory.PROVIDER, patterns=(
        "stytch.com", "api.stytch.com", "@stytch/vanilla-js", "@stytch/nextjs",
        "@stytch/react", "StytchClient(", "STYTCH_PROJECT_ID", "STYTCH_SECRET",
    )),

    Signature("Magic.link", AuthCategory.PROVIDER, patterns=(
        "magic.link", "magic-sdk", "@magic-sdk/", "new Magic(",
        "magic.auth.loginWithMagicLink(", "MAGIC_PUBLISHABLE_KEY",
        "MAGIC_SECRET_KEY",
    )),
)

# ---------------------------------------------------------------------------
# Identity Providers -- enterprise SSO/IdP systems.
# ---------------------------------------------------------------------------
IDENTITY_PROVIDERS: Tuple[Signature, ...] = (
    Signature("Okta", AuthCategory.IDENTITY_PROVIDER, patterns=(
        ".okta.com", ".oktapreview.com", "@okta/okta-auth-js",
        "@okta/okta-react", "@okta/okta-signin-widget", "new OktaAuth(",
        "okta-signin-widget", "OKTA_DOMAIN", "OKTA_CLIENT_ID",
    )),

    Signature("Azure Entra ID", AuthCategory.IDENTITY_PROVIDER, patterns=(
        "login.microsoftonline.com", "login.microsoft.com",
        "@azure/msal-browser", "@azure/msal-react", "@azure/msal-node",
        "msal-angular", "new PublicClientApplication(", "msalInstance",
        "AZURE_AD_CLIENT_ID", "AZURE_TENANT_ID",
    )),

    Signature("Keycloak", AuthCategory.IDENTITY_PROVIDER, patterns=(
        "keycloak-js", "new Keycloak(", "KeycloakConfig", "/auth/realms/",
        "/realms/", "protocol/openid-connect/token",
        "protocol/openid-connect/auth",
    ), cookies=("KEYCLOAK_SESSION", "KEYCLOAK_IDENTITY")),
)
