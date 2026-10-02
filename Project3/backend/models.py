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

def validate_registration(body: dict) -> tuple[bool, str]:
    """Return (ok, error_message) for a registration request body."""
    email = (body.get("email") or "").strip()
    password = body.get("password", "")
    name = (body.get("name") or "").strip()

    if not email or "@" not in email:
        return False, "A valid email address is required."
    if len(password) < 8:
        return False, "Password must be at least 8 characters."
    if not name:
        return False, "Name is required."
    return True, ""


def validate_login(body: dict) -> tuple[bool, str]:
    """Return (ok, error_message) for a login request body."""
    email = (body.get("email") or "").strip()
    password = body.get("password", "")

    if not email:
        return False, "Email is required."
    if not password:
        return False, "Password is required."
    return True, ""
