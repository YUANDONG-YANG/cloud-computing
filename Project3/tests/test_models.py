"""Tests for the request validators and the User document mapping.

The registration validator is what stops a password bcrypt cannot hash from
reaching the register handler, so its bounds are checked in bytes here, next
to the limit they protect.
"""
import json

import pytest

import models


# ---------------------------------------------------------------------------
# validate_registration
# ---------------------------------------------------------------------------

def test_valid_registration_is_accepted():
    ok, msg = models.validate_registration(
        {"email": "ada@example.com", "password": "a-good-password",
         "name": "Ada"})
    assert ok is True
    assert msg == ""


def test_email_must_look_like_an_address():
    for email in ["", "   ", "not-an-email", None]:
        ok, msg = models.validate_registration(
            {"email": email, "password": "a-good-password", "name": "Ada"})
        assert ok is False
        assert "email" in msg.lower()


def test_password_below_the_minimum_is_rejected():
    ok, msg = models.validate_registration(
        {"email": "ada@example.com", "password": "short12", "name": "Ada"})
    assert ok is False
    assert "8 characters" in msg


def test_password_at_the_byte_limit_is_accepted():
    ok, _ = models.validate_registration(
        {"email": "ada@example.com", "password": "p" * 72, "name": "Ada"})
    assert ok is True


def test_password_over_the_byte_limit_is_rejected():
    """Longer than bcrypt can hash, so it must fail validation and never
    reach hash_password, which would raise and return a 500."""
    ok, msg = models.validate_registration(
        {"email": "ada@example.com", "password": "p" * 73, "name": "Ada"})
    assert ok is False
    assert "72 bytes" in msg


def test_password_limit_counts_bytes_not_characters():
    # 30 characters, 90 bytes in UTF-8: within a character limit, over a
    # byte one.
    ok, msg = models.validate_registration(
        {"email": "ada@example.com", "password": "密" * 30, "name": "Ada"})
    assert ok is False
    assert "72 bytes" in msg


def test_name_is_required():
    ok, msg = models.validate_registration(
        {"email": "ada@example.com", "password": "a-good-password",
         "name": "   "})
    assert ok is False
    assert "Name" in msg


def test_missing_body_keys_do_not_raise():
    ok, msg = models.validate_registration({})
    assert ok is False
    assert msg


# ---------------------------------------------------------------------------
# validate_login
# ---------------------------------------------------------------------------

def test_valid_login_is_accepted():
    ok, _ = models.validate_login(
        {"email": "ada@example.com", "password": "anything"})
    assert ok is True


def test_login_requires_both_fields():
    assert models.validate_login({"password": "x"})[0] is False
    assert models.validate_login({"email": "ada@example.com"})[0] is False
    assert models.validate_login({})[0] is False


def test_login_does_not_enforce_password_rules():
    """Login must not leak the password policy: a stored password that
    predates a rule change still has to be able to authenticate."""
    ok, _ = models.validate_login(
        {"email": "ada@example.com", "password": "x"})
    assert ok is True


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

def test_user_document_partitions_on_email_and_is_serializable():
    user = models.User(email="ada@example.com", name="Ada",
                       password_hash="$2b$12$fake")
    doc = user.to_dict()
    assert doc["partitionKey"] == "ada@example.com"
    assert doc["email"] == "ada@example.com"
    json.dumps(doc)


def test_public_view_never_exposes_the_password_hash():
    user = models.User(email="ada@example.com", name="Ada",
                       password_hash="$2b$12$fake")
    public = user.to_public()
    assert "password_hash" not in public
    assert "$2b$12$fake" not in json.dumps(public)


def test_user_round_trips_through_a_cosmos_document():
    original = models.User(email="ada@example.com", name="Ada",
                           password_hash="$2b$12$fake", provider="github",
                           provider_id="12345")
    restored = models.User.from_dict(original.to_dict())
    assert restored == original


def test_from_dict_ignores_unknown_cosmos_fields():
    """Cosmos adds _rid, _etag and friends to every document it returns."""
    doc = models.User(email="ada@example.com", name="Ada").to_dict()
    doc.update({"_rid": "x", "_etag": "y", "_ts": 1, "partitionKey": "z"})
    restored = models.User.from_dict(doc)
    assert restored.email == "ada@example.com"


def test_each_user_gets_a_distinct_id():
    assert models.User().id != models.User().id


# ---------------------------------------------------------------------------
# Malformed request bodies must be rejected, not raise
#
# These bodies are all valid JSON, so they reach the validators intact. Before
# the type checks they raised AttributeError/TypeError out of the handler,
# which the Functions host turns into a 500 -- telling a caller the server
# broke when in fact their request was bad.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("body", [[], "a string", 42, None])
def test_registration_rejects_a_body_that_is_not_an_object(body):
    ok, msg = models.validate_registration(body)
    assert ok is False
    assert "JSON object" in msg


@pytest.mark.parametrize("body", [[], "a string", 42, None])
def test_login_rejects_a_body_that_is_not_an_object(body):
    ok, msg = models.validate_login(body)
    assert ok is False
    assert "JSON object" in msg


@pytest.mark.parametrize("password", [12345678, ["abcdefgh"], {"a": 1}, None])
def test_registration_rejects_a_password_that_is_not_text(password):
    ok, msg = models.validate_registration(
        {"email": "a@b.com", "password": password, "name": "A"})
    assert ok is False
    assert "text" in msg


@pytest.mark.parametrize("password", [12345678, ["x"], None])
def test_login_rejects_a_password_that_is_not_text(password):
    ok, msg = models.validate_login({"email": "a@b.com", "password": password})
    assert ok is False
    assert "text" in msg


@pytest.mark.parametrize("field,value", [
    ("email", 5), ("email", ["a@b.com"]), ("name", 7), ("name", {}),
])
def test_registration_rejects_non_text_email_and_name(field, value):
    body = {"email": "a@b.com", "password": "abcdefgh", "name": "A"}
    body[field] = value
    ok, _ = models.validate_registration(body)
    assert ok is False


def test_a_well_formed_registration_still_passes():
    ok, msg = models.validate_registration(
        {"email": "a@b.com", "password": "abcdefgh", "name": "A"})
    assert (ok, msg) == (True, "")
