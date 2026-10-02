"""Authentication helpers for Project 3 (Phase 3).

Provides password hashing (bcrypt, 12 rounds), JWT creation and
verification, and OAuth helpers for Google and GitHub.
"""
import os
import logging
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.parse import urlencode

import bcrypt
import jwt
import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
JWT_SECRET = os.environ.get("JWT_SECRET", "")
JWT_EXPIRY_HOURS = int(os.environ.get("JWT_EXPIRY_HOURS", "24"))
JWT_ALGORITHM = "HS256"

# WEBSITE_INSTANCE_ID is set by the Functions host on Azure and absent under
# `func start`, so an unset secret is a hard failure in a deployment and only a
# warning locally.  A known default signing key would let anyone mint a token.
if not JWT_SECRET:
    if os.environ.get("WEBSITE_INSTANCE_ID"):
        raise RuntimeError(
            "JWT_SECRET app setting is required. Generate one with "
            "`openssl rand -base64 32` and set it on the Function App."
        )
    JWT_SECRET = "local-development-only-do-not-deploy"
    logger.warning("JWT_SECRET unset; using the local development key")

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.environ.get(
    "GOOGLE_REDIRECT_URI",
    "http://localhost:7071/api/auth/oauth/google/callback",
)
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
GITHUB_REDIRECT_URI = os.environ.get(
    "GITHUB_REDIRECT_URI",
    "http://localhost:7071/api/auth/oauth/github/callback",
)
GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_EMAILS_URL = "https://api.github.com/user/emails"


# ---------------------------------------------------------------------------
# Password hashing (bcrypt, 12 rounds)
# ---------------------------------------------------------------------------

MAX_PASSWORD_BYTES = 72


def hash_password(plain: str) -> str:
    """Hash a plaintext password with bcrypt (12 rounds).

    bcrypt itself accepts at most 72 bytes. Version 4 truncated anything
    longer in silence, version 5 raises, and neither is a good outcome: the
    first makes two different passwords interchangeable, the second turns a
    long password into a 500. Callers validate the length first; this is the
    backstop.
    """
    encoded = plain.encode("utf-8")
    if len(encoded) > MAX_PASSWORD_BYTES:
        raise ValueError(
            f"Password exceeds bcrypt's {MAX_PASSWORD_BYTES}-byte limit"
        )
    return bcrypt.hashpw(encoded, bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        logger.exception("Password verification error")
        return False


# ---------------------------------------------------------------------------
# JWT creation and verification
# ---------------------------------------------------------------------------

def create_token(user_id: str, email: str, name: str) -> str:
    """Create a JWT token with user claims, valid for JWT_EXPIRY_HOURS."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "name": name,
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> Optional[dict]:
    """Verify and decode a JWT token.  Returns claims dict or None."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
        return None
    except jwt.InvalidTokenError as exc:
        logger.warning("Invalid token: %s", exc)
        return None


def create_state() -> str:
    """Mint a short-lived signed OAuth `state` value.

    Signing it keeps the check stateless: the callback can tell its own
    redirect apart from one a third party initiated, without a session store.
    """
    now = datetime.now(timezone.utc)
    return jwt.encode(
        # `jti` makes every state unique.  Without it the payload is just
        # iat/exp, so two flows starting in the same second get byte-identical
        # states and the cookie check below would accept one flow's state in
        # another flow's browser.
        {"purpose": "oauth_state", "jti": secrets.token_urlsafe(16),
         "iat": now, "exp": now + timedelta(minutes=10)},
        JWT_SECRET, algorithm=JWT_ALGORITHM,
    )


def verify_state(state: str) -> bool:
    """Check that a `state` value was signed by us and has not expired."""
    if not state:
        return False
    try:
        claims = jwt.decode(state, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return claims.get("purpose") == "oauth_state"
    except jwt.InvalidTokenError as exc:
        logger.warning("Rejected OAuth state: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Binding the state to the browser that started the flow
#
# A signed state proves only that *we* minted it, and /auth/oauth/<provider>
# hands one to anybody who asks.  An attacker can therefore fetch a valid state
# and feed their own authorization code to the callback in a victim's browser,
# logging the victim into the attacker's account.  Echoing the same value in an
# HttpOnly cookie closes that: the callback requires the query parameter and
# the cookie to match, and an attacker cannot set a cookie on our domain.
# ---------------------------------------------------------------------------

OAUTH_STATE_COOKIE = "p3_oauth_state"
OAUTH_STATE_MAX_AGE = 600


def state_cookie(state: str) -> str:
    """Set-Cookie value binding `state` to the browser starting the flow."""
    parts = [
        f"{OAUTH_STATE_COOKIE}={state}",
        "Path=/",
        "HttpOnly",
        # Lax, not Strict: the provider redirects back by top-level navigation,
        # and Strict would withhold the cookie on that cross-site hop.
        "SameSite=Lax",
        f"Max-Age={OAUTH_STATE_MAX_AGE}",
    ]
    if os.environ.get("WEBSITE_INSTANCE_ID"):
        # Azure serves HTTPS; `func start` is plain HTTP, where Secure would
        # stop the cookie being stored at all.
        parts.append("Secure")
    return "; ".join(parts)


def clear_state_cookie() -> str:
    """Set-Cookie value expiring the state cookie once the flow completes."""
    return f"{OAUTH_STATE_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"


def read_cookie(req, name: str) -> str:
    """Read one cookie from an Azure Functions HTTP request."""
    for item in (req.headers.get("Cookie", "") or "").split(";"):
        key, _, value = item.strip().partition("=")
        if key == name:
            return value
    return ""


def verify_state_request(req) -> bool:
    """Check the OAuth `state`: signed by us, unexpired, and this browser's."""
    from_provider = req.params.get("state", "")
    if not verify_state(from_provider):
        return False
    from_cookie = read_cookie(req, OAUTH_STATE_COOKIE)
    if not from_cookie:
        logger.warning("OAuth callback carried no state cookie")
        return False
    if not secrets.compare_digest(from_provider, from_cookie):
        logger.warning("OAuth state did not match the state cookie")
        return False
    return True


def extract_token(req) -> Optional[str]:
    """Extract the bearer token from an Azure Functions HTTP request.

    Header only: a token in the query string would end up in browser history,
    referrer headers and server access logs.
    """
    auth_header = req.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


def get_current_user(req) -> Optional[dict]:
    """Convenience: extract and verify the JWT from the request."""
    token = extract_token(req)
    if not token:
        return None
    return verify_token(token)


# ---------------------------------------------------------------------------
# OAuth: Google
# ---------------------------------------------------------------------------

def google_auth_url(state: str = "") -> str:
    """Build the Google OAuth consent URL."""
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def google_exchange_code(code: str) -> Optional[dict]:
    """Exchange a Google authorization code for user info."""
    try:
        token_resp = requests.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        }, timeout=10)
        token_resp.raise_for_status()
        tokens = token_resp.json()
        access_token = tokens.get("access_token")
        if not access_token:
            return None

        user_resp = requests.get(GOOGLE_USERINFO_URL, headers={
            "Authorization": f"Bearer {access_token}",
        }, timeout=10)
        user_resp.raise_for_status()
        info = user_resp.json()
        return {
            "provider": "google",
            "provider_id": info.get("sub", ""),
            "email": info.get("email", ""),
            "email_verified": bool(info.get("email_verified")),
            "name": info.get("name", ""),
        }
    except Exception:
        logger.exception("Google OAuth exchange failed")
        return None


# ---------------------------------------------------------------------------
# OAuth: GitHub
# ---------------------------------------------------------------------------

def github_auth_url(state: str = "") -> str:
    """Build the GitHub OAuth authorization URL."""
    params = {
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": GITHUB_REDIRECT_URI,
        "scope": "read:user user:email",
        "state": state,
    }
    return f"{GITHUB_AUTH_URL}?{urlencode(params)}"


def github_exchange_code(code: str) -> Optional[dict]:
    """Exchange a GitHub authorization code for user info."""
    try:
        token_resp = requests.post(GITHUB_TOKEN_URL, data={
            "client_id": GITHUB_CLIENT_ID,
            "client_secret": GITHUB_CLIENT_SECRET,
            "code": code,
            "redirect_uri": GITHUB_REDIRECT_URI,
        }, headers={"Accept": "application/json"}, timeout=10)
        token_resp.raise_for_status()
        access_token = token_resp.json().get("access_token")
        if not access_token:
            return None

        user_resp = requests.get(GITHUB_USER_URL, headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }, timeout=10)
        user_resp.raise_for_status()
        user_data = user_resp.json()

        # The profile email is whatever the user chose to make public, and it
        # carries no verification status, so always ask for the primary one.
        email = ""
        email_verified = False
        emails_resp = requests.get(GITHUB_EMAILS_URL, headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }, timeout=10)
        if emails_resp.status_code == 200:
            for entry in emails_resp.json():
                if entry.get("primary"):
                    email = entry.get("email", "")
                    email_verified = bool(entry.get("verified"))
                    break
        if not email:
            email = user_data.get("email", "") or ""

        return {
            "provider": "github",
            "provider_id": str(user_data.get("id", "")),
            "email": email,
            "email_verified": email_verified,
            "name": user_data.get("name") or user_data.get("login", ""),
        }
    except Exception:
        logger.exception("GitHub OAuth exchange failed")
        return None
