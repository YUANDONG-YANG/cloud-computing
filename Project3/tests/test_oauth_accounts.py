"""Tests for how an OAuth sign-in maps onto a stored account.

`_handle_oauth_user` is the only place where an identity asserted by a third
party is turned into one of our accounts, and users are keyed by email, so the
rules about which addresses may be trusted are enforced here.

These tests drive the in-memory user store, which is the same code path
`func start` takes when Cosmos DB is not configured.
"""
import pytest

import function_app as fa
from models import User


LOCAL_EMAIL = "person@example.com"
LOCAL_HASH = "$2b$12$a-real-looking-bcrypt-hash"


@pytest.fixture
def local_account(monkeypatch):
    """A password account that already exists, and an empty Cosmos."""
    user = User(email=LOCAL_EMAIL, name="Person",
                password_hash=LOCAL_HASH, provider="local")
    monkeypatch.setattr(fa, "_memory_users", {user.email: user})
    monkeypatch.setattr(fa, "_users_container", None)
    monkeypatch.setattr(fa, "_get_users", lambda: None)
    return user


def github_login(email, verified, provider_id="42", name="Person"):
    return {"provider": "github", "provider_id": provider_id,
            "email": email, "email_verified": verified, "name": name}


# ---------------------------------------------------------------------------
# An unverified address must not reach an existing account
# ---------------------------------------------------------------------------

def test_unverified_email_does_not_overwrite_a_password_account(local_account):
    """The defect this guards: refusing to *link* an unverified address was not
    enough.  The create branch still used that address as the new account's
    email, and because accounts are keyed by email the upsert replaced the
    existing one -- clearing its password hash and locking the owner out."""
    fa._handle_oauth_user(github_login(LOCAL_EMAIL, verified=False))

    survivor = fa._memory_users[LOCAL_EMAIL]
    assert survivor.password_hash == LOCAL_HASH
    assert survivor.provider == "local"
    assert survivor.id == local_account.id
    assert survivor.name == "Person"


def test_unverified_email_gets_a_separate_synthetic_identity(local_account):
    fa._handle_oauth_user(github_login(LOCAL_EMAIL, verified=False))

    assert set(fa._memory_users) == {LOCAL_EMAIL, "github_42@oauth.local"}
    created = fa._memory_users["github_42@oauth.local"]
    assert created.provider == "github"
    assert created.provider_id == "42"
    assert created.password_hash == ""


def test_an_unverified_email_cannot_take_over_another_persons_account(
        local_account):
    """Someone else's verified-looking address, asserted without verification."""
    fa._handle_oauth_user(
        github_login(LOCAL_EMAIL, verified=False, provider_id="99",
                     name="Someone Else"))
    assert fa._memory_users[LOCAL_EMAIL].password_hash == LOCAL_HASH
    assert fa._memory_users[LOCAL_EMAIL].name == "Person"


# ---------------------------------------------------------------------------
# A verified address may link, and must stay findable afterwards
# ---------------------------------------------------------------------------

def test_verified_email_links_to_the_existing_account(local_account):
    fa._handle_oauth_user(github_login(LOCAL_EMAIL, verified=True))

    assert set(fa._memory_users) == {LOCAL_EMAIL}
    linked = fa._memory_users[LOCAL_EMAIL]
    assert linked.id == local_account.id
    # Linking must not discard the password: both sign-in routes stay open.
    assert linked.password_hash == LOCAL_HASH
    assert linked.provider_id == "42"


def test_a_linked_account_is_found_by_provider_next_time(local_account):
    """Storing provider_id is only useful if the provider matches too; while
    `provider` stayed "local" this lookup missed and every later sign-in fell
    back to matching on the email address."""
    fa._handle_oauth_user(github_login(LOCAL_EMAIL, verified=True))

    assert fa._find_user_by_provider("github", "42") is not None
    assert fa._memory_users[LOCAL_EMAIL].provider == "github"


def test_a_second_login_reuses_the_same_account(local_account):
    fa._handle_oauth_user(github_login(LOCAL_EMAIL, verified=True))
    fa._handle_oauth_user(github_login(LOCAL_EMAIL, verified=True))
    assert set(fa._memory_users) == {LOCAL_EMAIL}


def test_a_provider_without_an_email_gets_a_synthetic_identity(monkeypatch):
    monkeypatch.setattr(fa, "_memory_users", {})
    monkeypatch.setattr(fa, "_get_users", lambda: None)

    fa._handle_oauth_user(github_login("", verified=False, provider_id="7"))

    assert set(fa._memory_users) == {"github_7@oauth.local"}
    assert fa._memory_users["github_7@oauth.local"].name == "Person"


def test_the_token_comes_back_in_the_fragment_and_clears_the_state_cookie(
        local_account):
    resp = fa._handle_oauth_user(github_login(LOCAL_EMAIL, verified=True))

    assert resp.status_code == 302
    location = resp.headers["Location"]
    assert "#token=" in location
    assert "?token=" not in location
    assert "Max-Age=0" in resp.headers["Set-Cookie"]
