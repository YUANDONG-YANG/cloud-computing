"""Authentication helpers for Project 3 (Phase 3).

Provides password hashing (bcrypt, 12 rounds), JWT creation and
verification, and OAuth helpers for Google and GitHub.
"""
import os
import json
import logging
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
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-in-production")
JWT_EXPIRY_HOURS = int(os.environ.get("JWT_EXPIRY_HOURS", "24"))
JWT_ALGORITHM = "HS256"

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

def hash_password(plain: str) -> str:
    """Hash a plaintext password with bcrypt (12 rounds)."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


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


def extract_token(req) -> Optional[str]:
    """Extract the bearer token from an Azure Functions HTTP request."""
    auth_header = req.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return req.params.get("token")


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

        email = user_data.get("email", "")
        if not email:
            emails_resp = requests.get(GITHUB_EMAILS_URL, headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            }, timeout=10)
            if emails_resp.status_code == 200:
                for entry in emails_resp.json():
                    if entry.get("primary"):
                        email = entry.get("email", "")
                        break

        return {
            "provider": "github",
            "provider_id": str(user_data.get("id", "")),
            "email": email,
            "name": user_data.get("name") or user_data.get("login", ""),
        }
    except Exception:
        logger.exception("GitHub OAuth exchange failed")
        return None
