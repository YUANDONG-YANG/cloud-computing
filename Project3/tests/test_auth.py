"""Tests for password hashing, JWT issuance and the signed OAuth state.

JWT_SECRET is set in conftest.py, which pytest imports before this module, so
`auth` reads the test key at import time.
"""
import datetime as dt

import pytest

bcrypt = pytest.importorskip("bcrypt", reason="bcrypt is not installed")
jwt = pytest.importorskip("jwt", reason="PyJWT is not installed")
pytest.importorskip("requests", reason="requests is not installed")

import auth  # noqa: E402  (must follow the importorskip guards)
from conftest import TEST_JWT_SECRET  # noqa: E402

OTHER_SECRET = "a-completely-different-signing-key"

PASSWORD = "correct horse battery"


def test_module_picked_up_the_test_secret():
    assert auth.JWT_SECRET == TEST_JWT_SECRET
    assert auth.JWT_ALGORITHM == "HS256"


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def test_hash_and_verify_round_trip():
    hashed = auth.hash_password(PASSWORD)
    assert auth.verify_password(PASSWORD, hashed) is True


def test_wrong_password_is_rejected():
    hashed = auth.hash_password(PASSWORD)
    assert auth.verify_password("not the password", hashed) is False
    assert auth.verify_password(PASSWORD + "x", hashed) is False
    assert auth.verify_password(PASSWORD.upper(), hashed) is False
    assert auth.verify_password("", hashed) is False


def test_stored_hash_is_never_the_plaintext():
    hashed = auth.hash_password(PASSWORD)
    assert hashed != PASSWORD
    assert PASSWORD not in hashed
    assert "horse" not in hashed
    assert isinstance(hashed, str)


def test_hash_is_bcrypt_with_twelve_rounds():
    hashed = auth.hash_password(PASSWORD)
    assert hashed.startswith("$2b$12$")
    assert len(hashed) == 60


def test_each_hash_is_salted_differently():
    first = auth.hash_password(PASSWORD)
    second = auth.hash_password(PASSWORD)
    assert first != second
    # Both still verify.
    assert auth.verify_password(PASSWORD, first)
    assert auth.verify_password(PASSWORD, second)


def test_verify_password_handles_a_malformed_hash():
    assert auth.verify_password(PASSWORD, "not-a-bcrypt-hash") is False
    assert auth.verify_password(PASSWORD, "") is False


def test_unicode_password_round_trips():
    secret = "pässwörd-日本語-🔐"
    hashed = auth.hash_password(secret)
    assert auth.verify_password(secret, hashed) is True
    assert auth.verify_password("passwrd", hashed) is False


def test_password_at_the_bcrypt_limit_round_trips():
    at_limit = "p" * auth.MAX_PASSWORD_BYTES
    hashed = auth.hash_password(at_limit)
    assert auth.verify_password(at_limit, hashed) is True


def test_password_over_the_bcrypt_limit_is_rejected_clearly():
    """bcrypt accepts 72 bytes. Version 4 truncated silently and version 5
    raises, so hash_password refuses rather than depending on which is
    installed. Registration rejects the same input with a 400 first."""
    with pytest.raises(ValueError, match="72-byte"):
        auth.hash_password("p" * 100)


def test_multibyte_password_is_measured_in_bytes_not_characters():
    # 30 characters, 90 bytes in UTF-8.
    with pytest.raises(ValueError, match="72-byte"):
        auth.hash_password("密" * 30)


# ---------------------------------------------------------------------------
# JWT creation / verification
# ---------------------------------------------------------------------------

def test_create_and_verify_token_round_trip():
    token = auth.create_token("user-1", "a@b.com", "Ada")
    assert isinstance(token, str)
    claims = auth.verify_token(token)
    assert claims is not None
    assert claims["sub"] == "user-1"
    assert claims["email"] == "a@b.com"
    assert claims["name"] == "Ada"
    assert "iat" in claims and "exp" in claims


def test_token_expiry_matches_configured_hours():
    token = auth.create_token("user-1", "a@b.com", "Ada")
    claims = auth.verify_token(token)
    delta = claims["exp"] - claims["iat"]
    assert delta == auth.JWT_EXPIRY_HOURS * 3600


def test_token_signed_with_a_different_secret_is_rejected():
    now = dt.datetime.now(dt.timezone.utc)
    forged = jwt.encode(
        {"sub": "attacker", "email": "e@v.il", "name": "Eve",
         "iat": now, "exp": now + dt.timedelta(hours=1)},
        OTHER_SECRET, algorithm="HS256",
    )
    assert auth.verify_token(forged) is None


def test_tampered_token_is_rejected():
    token = auth.create_token("user-1", "a@b.com", "Ada")
    header, payload, signature = token.split(".")
    tampered = f"{header}.{payload}.{signature[:-4]}AAAA"
    assert auth.verify_token(tampered) is None


def test_unsigned_alg_none_token_is_rejected():
    now = dt.datetime.now(dt.timezone.utc)
    unsigned = jwt.encode(
        {"sub": "attacker", "exp": now + dt.timedelta(hours=1)},
        key="", algorithm="none",
    )
    assert auth.verify_token(unsigned) is None


def test_expired_token_is_rejected():
    now = dt.datetime.now(dt.timezone.utc)
    expired = jwt.encode(
        {"sub": "user-1", "email": "a@b.com", "name": "Ada",
         "iat": now - dt.timedelta(hours=48),
         "exp": now - dt.timedelta(hours=1)},
        TEST_JWT_SECRET, algorithm="HS256",
    )
    assert auth.verify_token(expired) is None


def test_garbage_token_is_rejected():
    for bad in ("", "garbage", "a.b.c", "....", "null"):
        assert auth.verify_token(bad) is None


# ---------------------------------------------------------------------------
# OAuth state
# ---------------------------------------------------------------------------

def test_create_and_verify_state_round_trip():
    state = auth.create_state()
    assert isinstance(state, str)
    assert auth.verify_state(state) is True


def test_garbage_state_is_rejected():
    for bad in ("", "garbage", "a.b.c", "x" * 50):
        assert auth.verify_state(bad) is False


def test_state_signed_with_a_different_secret_is_rejected():
    now = dt.datetime.now(dt.timezone.utc)
    forged = jwt.encode(
        {"purpose": "oauth_state", "iat": now,
         "exp": now + dt.timedelta(minutes=5)},
        OTHER_SECRET, algorithm="HS256",
    )
    assert auth.verify_state(forged) is False


def test_expired_state_is_rejected():
    now = dt.datetime.now(dt.timezone.utc)
    stale = jwt.encode(
        {"purpose": "oauth_state", "iat": now - dt.timedelta(minutes=30),
         "exp": now - dt.timedelta(minutes=1)},
        TEST_JWT_SECRET, algorithm="HS256",
    )
    assert auth.verify_state(stale) is False


def test_a_session_token_is_not_a_valid_state():
    """A user JWT must not double as an OAuth state value."""
    token = auth.create_token("user-1", "a@b.com", "Ada")
    assert auth.verify_state(token) is False


def test_state_without_the_expected_purpose_is_rejected():
    now = dt.datetime.now(dt.timezone.utc)
    wrong = jwt.encode(
        {"purpose": "something_else", "iat": now,
         "exp": now + dt.timedelta(minutes=5)},
        TEST_JWT_SECRET, algorithm="HS256",
    )
    assert auth.verify_state(wrong) is False


# ---------------------------------------------------------------------------
# Bearer extraction
# ---------------------------------------------------------------------------

class FakeRequest:
    def __init__(self, headers=None):
        self.headers = headers or {}


def test_extract_token_reads_the_bearer_header():
    req = FakeRequest({"Authorization": "Bearer abc.def.ghi"})
    assert auth.extract_token(req) == "abc.def.ghi"


def test_extract_token_ignores_other_schemes_and_absence():
    assert auth.extract_token(FakeRequest()) is None
    assert auth.extract_token(FakeRequest({"Authorization": ""})) is None
    assert auth.extract_token(
        FakeRequest({"Authorization": "Basic abc"})) is None
    assert auth.extract_token(
        FakeRequest({"Authorization": "bearer abc"})) is None


def test_get_current_user_round_trip():
    token = auth.create_token("user-9", "z@b.com", "Zed")
    req = FakeRequest({"Authorization": f"Bearer {token}"})
    user = auth.get_current_user(req)
    assert user["sub"] == "user-9"
    assert auth.get_current_user(FakeRequest()) is None
    assert auth.get_current_user(
        FakeRequest({"Authorization": "Bearer garbage"})) is None
