"""Regression tests for review/audit-2026-11-23.md.

P1  Cosmos configured but unreachable must fail closed (503), not silently
    keep accounts in one process's memory.
P2  Concurrent registrations for one email must produce one account.
P2  The anonymous login/register endpoints are throttled.

bcrypt is replaced by a fast stand-in in most tests: these tests are about
which store is written and which status is returned, not about hashing.
"""
import json
import threading

import pytest

pytest.importorskip("azure.functions", reason="azure-functions is not installed")
pytest.importorskip("azure.cosmos", reason="azure-cosmos is not installed")

import azure.functions as func  # noqa: E402
from azure.cosmos.exceptions import CosmosResourceExistsError  # noqa: E402

import function_app as fa  # noqa: E402
import ratelimit  # noqa: E402
from models import User  # noqa: E402

EMAIL = "person@example.com"
PASSWORD = "correct horse battery"


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    monkeypatch.delenv("COSMOS_ENDPOINT", raising=False)
    monkeypatch.delenv("COSMOS_KEY", raising=False)
    monkeypatch.setattr(fa, "_memory_users", {})
    monkeypatch.setattr(fa, "_users_container", None)
    monkeypatch.setattr(fa, "_users_failed_at", None)
    for limiter in (fa._login_ip_limiter, fa._register_ip_limiter,
                    fa._login_failure_limiter):
        limiter.clear()
    monkeypatch.setattr(fa, "hash_password", lambda p: "h:" + p)
    monkeypatch.setattr(fa, "verify_password", lambda p, h: h == "h:" + p)
    yield
    for limiter in (fa._login_ip_limiter, fa._register_ip_limiter,
                    fa._login_failure_limiter):
        limiter.clear()


def post(handler, body, ip="203.0.113.7"):
    req = func.HttpRequest(
        method="POST", url="/api/x", body=json.dumps(body).encode(),
        headers={"X-Forwarded-For": f"198.51.100.1, {ip}:50123"},
    )
    return handler(req)


def register(email=EMAIL, ip="203.0.113.7"):
    return post(fa.register,
                {"email": email, "password": PASSWORD, "name": "Person"}, ip)


def login(email=EMAIL, password=PASSWORD, ip="203.0.113.7"):
    return post(fa.login, {"email": email, "password": password}, ip)


class FakeContainer:
    """Enough of a Cosmos container: ids are unique within a partition."""

    def __init__(self, fail_queries=False):
        self.docs = {}
        self.fail_queries = fail_queries

    def query_items(self, query, parameters, partition_key=None, **_):
        if self.fail_queries:
            raise RuntimeError("query timed out")
        values = {p["name"]: p["value"] for p in parameters}
        if "@email" in values:
            return [d for d in self.docs.values()
                    if d["email"] == values["@email"]]
        return [d for d in self.docs.values()
                if d["provider"] == values["@p"]
                and d["provider_id"] == values["@pid"]]

    def create_item(self, doc):
        key = (doc["partitionKey"], doc["id"])
        if key in self.docs:
            raise CosmosResourceExistsError(message="Conflict")
        self.docs[key] = dict(doc)

    def upsert_item(self, doc):
        self.docs[(doc["partitionKey"], doc["id"])] = dict(doc)


def configure_broken_cosmos(monkeypatch):
    monkeypatch.setenv("COSMOS_ENDPOINT", "https://unreachable.invalid:443/")
    monkeypatch.setenv("COSMOS_KEY", "bm90LWEta2V5")
    import azure.cosmos

    calls = []

    class Unreachable:
        def __init__(self, *a, **k):
            calls.append(1)
            raise ConnectionError("cannot reach Cosmos DB")

    monkeypatch.setattr(azure.cosmos, "CosmosClient", Unreachable)
    return calls


# ---------------------------------------------------------------------------
# P1: configured-but-unavailable Cosmos fails closed
# ---------------------------------------------------------------------------

def test_register_fails_closed_when_cosmos_is_configured_but_down(monkeypatch):
    configure_broken_cosmos(monkeypatch)

    resp = register()

    assert resp.status_code == 503
    assert fa._memory_users == {}, "nothing may be kept in process memory"


def test_login_fails_closed_when_cosmos_is_configured_but_down(monkeypatch):
    configure_broken_cosmos(monkeypatch)
    # Even an account that somehow sits in memory must not be used.
    fa._memory_users[EMAIL] = User(email=EMAIL, password_hash="h:" + PASSWORD)

    assert login().status_code == 503


def test_failed_init_is_retried_after_the_cooldown(monkeypatch):
    calls = configure_broken_cosmos(monkeypatch)
    clock = [1000.0]
    monkeypatch.setattr(fa.time, "monotonic", lambda: clock[0])

    assert register().status_code == 503
    assert register().status_code == 503
    assert len(calls) == 1, "within the cooldown the connect is not retried"

    clock[0] += fa._USERS_RETRY_SECONDS + 1
    container = FakeContainer()
    import azure.cosmos

    class Recovered:
        def __init__(self, *a, **k):
            pass

        def create_database_if_not_exists(self, *_):
            return self

        def create_container_if_not_exists(self, **_):
            return container

    monkeypatch.setattr(azure.cosmos, "CosmosClient", Recovered)
    assert register().status_code == 201
    assert len(container.docs) == 1


def test_a_failed_cosmos_lookup_is_not_treated_as_no_such_user(monkeypatch):
    """Otherwise registration would write a second account for the email."""
    container = FakeContainer()
    container.upsert_item(User(email=EMAIL).to_dict())
    container.fail_queries = True
    monkeypatch.setattr(fa, "_users_container", container)

    assert register().status_code == 503
    assert len(container.docs) == 1


def test_unconfigured_cosmos_still_uses_memory_for_local_dev():
    assert register().status_code == 201
    assert EMAIL in fa._memory_users
    assert login().status_code == 200


def test_health_reports_an_unavailable_user_store(monkeypatch):
    configure_broken_cosmos(monkeypatch)
    resp = fa.health_check(func.HttpRequest("GET", "/api/health", body=b""))
    data = json.loads(resp.get_body())
    assert data["status"] == "degraded"
    assert data["security"]["user_store"] == "Cosmos DB (unavailable)"


def test_a_failed_durable_update_is_not_copied_into_memory(monkeypatch):
    class Failing(FakeContainer):
        def upsert_item(self, doc):
            raise RuntimeError("503 from Cosmos")

    monkeypatch.setattr(fa, "_users_container", Failing())
    assert fa._save_user(User(email=EMAIL)) is False
    assert fa._memory_users == {}


# ---------------------------------------------------------------------------
# P2: one account per email, even under concurrency
# ---------------------------------------------------------------------------

def test_new_accounts_get_an_id_derived_from_the_email():
    assert User.id_for_email(EMAIL) == User.id_for_email(EMAIL)
    assert User.id_for_email(EMAIL) != User.id_for_email("other@example.com")


def test_racing_registrations_in_cosmos_create_one_document(monkeypatch):
    """Both requests pass the existence check before either writes."""
    container = FakeContainer()
    monkeypatch.setattr(fa, "_users_container", container)
    monkeypatch.setattr(fa, "_find_user_by_email", lambda email: None)

    first, second = register(), register(ip="203.0.113.8")

    assert sorted([first.status_code, second.status_code]) == [201, 409]
    assert len(container.docs) == 1


def test_concurrent_registrations_in_memory_create_one_account(monkeypatch):
    barrier = threading.Barrier(8)
    real_find = fa._find_user_by_email

    def find_then_wait(email):
        result = real_find(email)
        barrier.wait()          # every thread has passed the check
        return result

    monkeypatch.setattr(fa, "_find_user_by_email", find_then_wait)
    statuses = []

    def worker(i):
        statuses.append(register(ip=f"203.0.113.{i}").status_code)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(statuses) == [201] + [409] * 7
    assert len(fa._memory_users) == 1


def test_legacy_duplicate_documents_resolve_to_the_oldest(monkeypatch):
    container = FakeContainer()
    older = User(email=EMAIL, name="Original", created_at="2026-01-01T00:00:00")
    newer = User(email=EMAIL, name="Duplicate", created_at="2026-02-01T00:00:00")
    container.upsert_item(newer.to_dict())
    container.upsert_item(older.to_dict())
    monkeypatch.setattr(fa, "_users_container", container)

    assert fa._find_user_by_email(EMAIL).name == "Original"


def test_oauth_email_is_normalized_and_links_to_the_registered_account(
        monkeypatch):
    container = FakeContainer()
    monkeypatch.setattr(fa, "_users_container", container)
    assert register().status_code == 201

    fa._handle_oauth_user({"provider": "github", "provider_id": "42",
                           "email": "Person@Example.COM",
                           "email_verified": True, "name": "Person"})

    assert len(container.docs) == 1
    (doc,) = container.docs.values()
    assert doc["provider_id"] == "42"
    assert doc["password_hash"] == "h:" + PASSWORD


def test_oauth_sign_in_with_the_store_down_redirects_with_an_error(
        monkeypatch):
    configure_broken_cosmos(monkeypatch)
    resp = fa._handle_oauth_user({"provider": "github", "provider_id": "42",
                                  "email": EMAIL, "email_verified": True})
    assert resp.status_code == 302
    assert "error=account_not_saved" in resp.headers["Location"]


# ---------------------------------------------------------------------------
# P2: throttling of the anonymous auth endpoints
# ---------------------------------------------------------------------------

def test_repeated_wrong_passwords_lock_the_account():
    register()
    for _ in range(fa._login_failure_limiter.limit):
        assert login(password="wrong password").status_code == 401

    resp = login()          # even the right password, from another address
    assert resp.status_code == 429
    assert int(resp.headers["Retry-After"]) > 0


def test_lockout_is_checked_before_bcrypt_runs(monkeypatch):
    register()
    for _ in range(fa._login_failure_limiter.limit):
        login(password="wrong password")
    calls = []
    monkeypatch.setattr(fa, "verify_password",
                        lambda p, h: calls.append(1) or False)

    assert login().status_code == 429
    assert calls == []


def test_a_successful_login_clears_earlier_failures():
    register()
    for _ in range(fa._login_failure_limiter.limit - 1):
        login(password="wrong password")
    assert login().status_code == 200
    assert login(password="wrong password").status_code == 401
    assert login().status_code == 200


def test_login_attempts_are_limited_per_client_address():
    limit = fa._login_ip_limiter.limit
    for i in range(limit):
        login(email=f"user{i}@example.com", password="whatever1")
    assert login(email="new@example.com").status_code == 429
    # A different client is unaffected.
    assert login(email="new@example.com", ip="192.0.2.50").status_code == 401


def test_registrations_are_limited_per_client_address():
    limit = fa._register_ip_limiter.limit
    for i in range(limit):
        assert register(email=f"user{i}@example.com").status_code == 201
    assert register(email="one-more@example.com").status_code == 429


def test_unknown_email_still_spends_a_password_check(monkeypatch):
    burned = []
    monkeypatch.setattr(fa, "_burn_password_check",
                        lambda p: burned.append(p))
    assert login(email="nobody@example.com").status_code == 401
    assert burned == [PASSWORD]


# ---------------------------------------------------------------------------
# ratelimit module
# ---------------------------------------------------------------------------

def test_limiter_window_slides():
    lim = ratelimit.SlidingWindowLimiter(limit=2, window=10)
    assert lim.hit("k", now=0) == 0
    assert lim.hit("k", now=1) == 0
    assert lim.hit("k", now=2) == pytest.approx(8)
    assert lim.hit("k", now=10.5) == 0      # the first event has expired


def test_blocked_attempts_do_not_extend_the_block():
    lim = ratelimit.SlidingWindowLimiter(limit=1, window=10)
    lim.hit("k", now=0)
    for t in range(1, 10):
        lim.hit("k", now=t)
    assert lim.hit("k", now=10.5) == 0


def test_limiter_memory_is_bounded():
    lim = ratelimit.SlidingWindowLimiter(limit=1, window=1000, max_keys=50)
    for i in range(500):
        lim.hit(f"k{i}", now=i)
    assert len(lim._events) <= 50


@pytest.mark.parametrize("header, expected", [
    ("", "unknown"),
    ("203.0.113.7", "203.0.113.7"),
    ("203.0.113.7:51234", "203.0.113.7"),
    ("1.2.3.4, 203.0.113.7:443", "203.0.113.7"),   # forged left entry ignored
    ("[2001:db8::1]:443", "2001:db8::1"),
    ("2001:db8::1", "2001:db8::1"),
])
def test_client_ip_uses_the_rightmost_forwarded_entry(header, expected):
    assert ratelimit.client_ip({"x-forwarded-for": header}) == expected
