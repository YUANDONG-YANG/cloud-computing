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
    def __init__(self, headers=None, params=None):
        self.headers = headers or {}
        self.params = params or {}


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


# ---------------------------------------------------------------------------
# Binding the OAuth state to the browser that started the flow
#
# verify_state alone only proves we signed the value, and the consent endpoint
# hands a signed state to anyone who asks.  These tests pin the extra check.
# ---------------------------------------------------------------------------

def _callback(state_param, state_cookie_value):
    """A callback request carrying a state parameter and a state cookie."""
    headers = {}
    if state_cookie_value is not None:
        headers["Cookie"] = f"{auth.OAUTH_STATE_COOKIE}={state_cookie_value}"
    return FakeRequest(headers, {"state": state_param})


def test_state_cookie_is_http_only_and_lax():
    cookie = auth.state_cookie("abc")
    assert cookie.startswith(f"{auth.OAUTH_STATE_COOKIE}=abc")
    assert "HttpOnly" in cookie
    # Lax, not Strict: the provider redirects back cross-site by top-level
    # navigation, and Strict would withhold the cookie on that hop.
    assert "SameSite=Lax" in cookie
    assert f"Max-Age={auth.OAUTH_STATE_MAX_AGE}" in cookie


def test_state_cookie_is_secure_only_on_azure(monkeypatch):
    monkeypatch.delenv("WEBSITE_INSTANCE_ID", raising=False)
    assert "Secure" not in auth.state_cookie("abc")
    monkeypatch.setenv("WEBSITE_INSTANCE_ID", "instance-1")
    assert "Secure" in auth.state_cookie("abc")


def test_clear_state_cookie_expires_it():
    assert "Max-Age=0" in auth.clear_state_cookie()


def test_read_cookie_picks_the_named_value():
    req = FakeRequest({"Cookie": "other=1; p3_oauth_state=wanted; third=3"})
    assert auth.read_cookie(req, "p3_oauth_state") == "wanted"
    assert auth.read_cookie(req, "absent") == ""
    assert auth.read_cookie(FakeRequest(), "p3_oauth_state") == ""


def test_matching_state_and_cookie_is_accepted():
    state = auth.create_state()
    assert auth.verify_state_request(_callback(state, state)) is True


def test_state_without_a_cookie_is_rejected():
    """The attack verify_state alone allows: a valid state, someone else's browser."""
    state = auth.create_state()
    assert auth.verify_state_request(_callback(state, None)) is False


def test_state_not_matching_the_cookie_is_rejected():
    attacker_state = auth.create_state()
    victim_state = auth.create_state()
    assert auth.verify_state_request(
        _callback(attacker_state, victim_state)) is False


def test_unsigned_state_is_rejected_even_when_the_cookie_agrees():
    assert auth.verify_state_request(_callback("forged", "forged")) is False


def test_missing_state_parameter_is_rejected():
    assert auth.verify_state_request(_callback("", "")) is False


def test_each_state_is_unique():
    """Without a nonce the payload is just iat/exp, so two flows starting in
    the same second produced byte-identical states and the cookie check above
    would accept one flow's state in another flow's browser."""
    states = {auth.create_state() for _ in range(20)}
    assert len(states) == 20
