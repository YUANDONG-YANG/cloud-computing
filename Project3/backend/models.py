"""Data models and schemas for Project 3 (Phase 3).

Defines User model, data schemas, and validation helpers for
the authentication and caching layers.
"""
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class User:
    """User account stored in Cosmos DB."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    email: str = ""
    name: str = ""
    password_hash: str = ""
    provider: str = "local"          # "local", "google", "github"
    provider_id: str = ""            # OAuth subject identifier
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    last_login: str = ""

    def to_dict(self) -> dict:
        """Serialize for Cosmos DB storage."""
        d = asdict(self)
        d["partitionKey"] = self.email
        return d

    def to_public(self) -> dict:
        """Return only fields safe to send to the client."""
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "provider": self.provider,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        """Reconstruct from Cosmos DB document."""
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)


@dataclass
class CacheEntry:
    """A single cached analytics result stored in Cosmos DB or Redis."""
    id: str = "insights"
    data: dict = field(default_factory=dict)
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    partitionKey: str = "cache"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CacheEntry":
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)


# Validation helpers -------------------------------------------------------

def _text_field(body: dict, key: str) -> str:
    """Return a string field from a request body, or "" when it is not one.

    JSON bodies arrive from the network, so a field may be a number, a list or
    null.  Returning "" lets the checks below reject it as missing instead of
    raising out of the handler, which the host would report as a 500.
    """
    value = body.get(key)
    return value.strip() if isinstance(value, str) else ""


def validate_registration(body: dict) -> tuple[bool, str]:
    """Return (ok, error_message) for a registration request body."""
    # `[]` and `"hi"` are valid JSON; only an object can be a registration.
    if not isinstance(body, dict):
        return False, "A JSON object with email, password and name is required."

    email = _text_field(body, "email")
    password = body.get("password")
    name = _text_field(body, "name")

    if not isinstance(password, str):
        return False, "Password must be text."

    if not email or "@" not in email:
        return False, "A valid email address is required."
    if len(password) < 8:
        return False, "Password must be at least 8 characters."
    # bcrypt hashes at most 72 bytes. Rejecting longer passwords here keeps
    # the register handler from raising out of hash_password, and is honest:
    # silently truncating would make two different passwords equivalent.
    if len(password.encode("utf-8")) > 72:
        return False, "Password must be at most 72 bytes."
    if not name:
        return False, "Name is required."
    return True, ""


def validate_login(body: dict) -> tuple[bool, str]:
    """Return (ok, error_message) for a login request body."""
    if not isinstance(body, dict):
        return False, "A JSON object with email and password is required."

    email = _text_field(body, "email")
    password = body.get("password")

    if not isinstance(password, str):
        return False, "Password must be text."
    if not email:
        return False, "Email is required."
    if not password:
        return False, "Password is required."
    return True, ""
