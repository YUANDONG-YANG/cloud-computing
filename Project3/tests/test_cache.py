"""Tests for the Cosmos-backed cache: chunking round-trips and Redis opt-out.

A dict-backed stub stands in for the Cosmos container.  It copies documents on
the way in and out (the real SDK serializes them) and raises on a missing item
from both read_item and delete_item, which is what azure.cosmos does.
"""
import copy
import json
import sys
import types

import pytest

import cache


# ---------------------------------------------------------------------------
# Cosmos container stub
# ---------------------------------------------------------------------------

class FakeCosmosNotFound(Exception):
    """Stands in for azure.cosmos.exceptions.CosmosResourceNotFoundError."""


class FakeContainer:
    def __init__(self):
        self.items: dict = {}
        self.read_calls: list = []
        self.write_calls: list = []
        self.delete_calls: list = []
        self.fail_writes_from = None  # index of first upsert that should fail

    # -- real-SDK-shaped surface -------------------------------------------
    def read_item(self, item, partition_key):
        self.read_calls.append(item)
        key = (partition_key, item)
        if key not in self.items:
            raise FakeCosmosNotFound(f"Entity with id {item} does not exist")
        return copy.deepcopy(self.items[key])

    def upsert_item(self, body):
        if not isinstance(body, dict):
            raise TypeError("Cosmos documents must be dicts")
        if "id" not in body or "partitionKey" not in body:
            raise FakeCosmosNotFound("document needs id and partitionKey")
        json.dumps(body)  # Cosmos rejects anything it cannot serialize.
        self.write_calls.append(body["id"])
        if (self.fail_writes_from is not None
                and len(self.write_calls) > self.fail_writes_from):
            raise FakeCosmosNotFound("simulated write failure")
        self.items[(body["partitionKey"], body["id"])] = copy.deepcopy(body)
        return copy.deepcopy(body)

    def delete_item(self, item, partition_key):
        self.delete_calls.append(item)
        key = (partition_key, item)
        if key not in self.items:
            raise FakeCosmosNotFound(f"Entity with id {item} does not exist")
        del self.items[key]

    # -- test helpers ------------------------------------------------------
    def ids(self):
        return sorted(doc_id for _, doc_id in self.items)


@pytest.fixture
def container(monkeypatch):
    """Point cache.py at the stub and isolate its module-level state."""
    fake = FakeContainer()
    monkeypatch.setattr(cache, "_get_cosmos", lambda: fake)
    monkeypatch.setattr(cache, "_cosmos_container", fake)
    monkeypatch.setattr(cache, "_cosmos_tried", True)
    # Redis must be out of the picture and must never be dialled.
    monkeypatch.setattr(cache, "_redis_client", None)
    monkeypatch.setattr(cache, "_redis_tried", True)
    # Fresh in-process fallback for every test.
    monkeypatch.setattr(cache, "_memory_store", {})
    return fake


def records(n, tag="a"):
    return [
        {
            "Diet_type": "vegan" if i % 2 else "keto",
            "Recipe_name": f"{tag}-recipe-{i}",
            "Cuisine_type": "indian",
            "Protein(g)": float(i),
            "Carbs(g)": 10.0,
            "Fat(g)": 2.5,
        }
        for i in range(n)
    ]


def drop_memory(monkeypatch):
    """Force reads to come from the stubbed Cosmos, not the local dict."""
    monkeypatch.setattr(cache, "_memory_store", {})


# ---------------------------------------------------------------------------
# Insights round-trip
# ---------------------------------------------------------------------------

def test_store_and_get_insights(container, monkeypatch):
    assert cache.store_insights({"total_recipes": 3}) is True
    drop_memory(monkeypatch)
    got = cache.get_insights()
    assert got["data"] == {"total_recipes": 3}
    assert got["cache_source"] == "cosmosdb"
    assert got["updated_at"]


def test_get_insights_returns_none_when_empty(container):
    assert cache.get_insights() is None


# ---------------------------------------------------------------------------
# Recipe chunking
# ---------------------------------------------------------------------------

def test_small_dataset_round_trips(container, monkeypatch):
    data = records(5)
    assert cache.store_recipes(data) is True
    drop_memory(monkeypatch)
    assert cache.get_recipes() == data
    assert container.ids() == ["recipes_chunk_000", "recipes_meta"]


def test_dataset_larger_than_chunk_size_round_trips_exactly(
        container, monkeypatch):
    total = cache.CHUNK_SIZE * 2 + 37
    data = records(total)
    assert cache.store_recipes(data) is True

    expected_chunks = 3
    assert container.ids() == [
        f"recipes_chunk_{i:03d}" for i in range(expected_chunks)
    ] + ["recipes_meta"]
    meta = container.items[("cache", "recipes_meta")]
    assert meta["chunk_count"] == expected_chunks
    assert meta["record_count"] == total

    drop_memory(monkeypatch)
    got = cache.get_recipes()
    assert got is not None
    assert len(got) == total
    assert got == data            # order and content preserved end to end
    assert got[0]["Recipe_name"] == "a-recipe-0"
    assert got[-1]["Recipe_name"] == f"a-recipe-{total - 1}"


def test_chunk_boundaries_are_exact(container):
    total = cache.CHUNK_SIZE + 1
    cache.store_recipes(records(total))
    first = container.items[("cache", "recipes_chunk_000")]["records"]
    second = container.items[("cache", "recipes_chunk_001")]["records"]
    assert len(first) == cache.CHUNK_SIZE
    assert len(second) == 1


def test_restoring_a_smaller_dataset_deletes_stale_chunks(
        container, monkeypatch):
    big = records(cache.CHUNK_SIZE * 3, tag="old")
    assert cache.store_recipes(big) is True
    assert container.items[("cache", "recipes_meta")]["chunk_count"] == 3

    small = records(5, tag="new")
    assert cache.store_recipes(small) is True

    # Stale trailing chunk documents are gone, not merely unreferenced.
    assert container.ids() == ["recipes_chunk_000", "recipes_meta"]
    assert container.items[("cache", "recipes_meta")]["chunk_count"] == 1
    assert container.items[("cache", "recipes_meta")]["record_count"] == 5

    drop_memory(monkeypatch)
    got = cache.get_recipes()
    assert got == small
    assert len(got) == 5
    # No record from the previous, larger dataset leaked through.
    assert not any(r["Recipe_name"].startswith("old-") for r in got)


def test_restoring_a_larger_dataset_overwrites_cleanly(
        container, monkeypatch):
    assert cache.store_recipes(records(5, tag="old")) is True
    big = records(cache.CHUNK_SIZE * 2, tag="new")
    assert cache.store_recipes(big) is True
    drop_memory(monkeypatch)
    got = cache.get_recipes()
    assert got == big
    assert not any(r["Recipe_name"].startswith("old-") for r in got)


def test_missing_middle_chunk_does_not_yield_a_partial_set(
        container, monkeypatch):
    total = cache.CHUNK_SIZE * 3
    data = records(total)
    cache.store_recipes(data)
    drop_memory(monkeypatch)

    # Lose the middle chunk, as a partial write or an eviction would.
    del container.items[("cache", "recipes_chunk_001")]

    got = cache.get_recipes()
    assert got is None or len(got) == total, (
        f"get_recipes returned a partial set of {len(got)} records"
    )
    # Observed behaviour: the chunk loop aborts and reports a miss rather
    # than handing back the chunks it did manage to read.
    assert got is None
    assert container.read_calls[-1] == "recipes_chunk_001"


def test_missing_first_chunk_does_not_yield_a_partial_set(
        container, monkeypatch):
    total = cache.CHUNK_SIZE * 2
    data = records(total)
    cache.store_recipes(data)
    drop_memory(monkeypatch)
    del container.items[("cache", "recipes_chunk_000")]

    got = cache.get_recipes()
    assert got is None or len(got) == total


def test_missing_last_chunk_does_not_yield_a_partial_set(
        container, monkeypatch):
    total = cache.CHUNK_SIZE * 2 + 10
    data = records(total)
    cache.store_recipes(data)
    drop_memory(monkeypatch)
    del container.items[("cache", "recipes_chunk_002")]

    got = cache.get_recipes()
    assert got is None or len(got) == total


def test_missing_chunk_does_not_fall_back_to_the_memory_copy(container):
    """A durable cache inconsistent with its metadata reports a miss.

    The in-process copy is not consulted: it can hold a different dataset
    than the metadata describes, which would be served as though it were the
    cached one.
    """
    total = cache.CHUNK_SIZE * 2
    cache.store_recipes(records(total))   # memory store intentionally kept
    del container.items[("cache", "recipes_chunk_001")]

    assert cache.get_recipes() is None


def test_get_recipes_returns_none_when_nothing_cached(container):
    assert cache.get_recipes() is None


def test_empty_dataset_reads_back_as_empty_not_as_a_miss(
        container, monkeypatch):
    """An empty dataset was still cached on purpose, so it reads back as [].

    None is reserved for nothing having been cached, which is what makes the
    recipes endpoint able to tell a real empty result from a cold cache.
    """
    assert cache.store_recipes([]) is True
    assert container.items[("cache", "recipes_meta")]["record_count"] == 0
    assert container.items[("cache", "recipes_meta")]["chunk_count"] == 1
    drop_memory(monkeypatch)
    assert cache.get_recipes() == []


def test_meta_is_written_last(container):
    cache.store_recipes(records(cache.CHUNK_SIZE + 1))
    assert container.write_calls[-1] == cache.RECIPES_META_KEY
    assert container.write_calls[:-1] == ["recipes_chunk_000",
                                          "recipes_chunk_001"]


def test_failed_chunk_write_reads_back_as_a_miss(container, monkeypatch):
    """A rewrite that dies partway must leave the cache reading as empty.

    The metadata is retired before the chunks are touched, so there is no
    moment where it describes a set that is only half replaced.
    """
    good = records(5, tag="good")
    cache.store_recipes(good)

    container.fail_writes_from = len(container.write_calls)
    cache.store_recipes(records(cache.CHUNK_SIZE * 2, tag="bad"))
    container.fail_writes_from = None

    assert ("cache", "recipes_meta") not in container.items
    drop_memory(monkeypatch)
    assert cache.get_recipes() is None


def test_failed_chunk_rewrite_never_serves_a_spliced_dataset(
        container, monkeypatch):
    """The defect this guards: chunks are replaced one at a time, so a failure
    on a later chunk used to leave chunk 0 holding the new dataset and chunk 1
    the old one, with metadata that still vouched for the pair.  get_recipes
    then returned half of each as though it were a single valid dataset."""
    cache.store_recipes(records(cache.CHUNK_SIZE * 2, tag="GOOD"))

    # First replacement chunk succeeds, the second fails.
    container.fail_writes_from = len(container.write_calls) + 1
    cache.store_recipes(records(cache.CHUNK_SIZE * 2, tag="BAD"))
    container.fail_writes_from = None

    drop_memory(monkeypatch)
    got = cache.get_recipes()
    if got is not None:
        tags = {r["Recipe_name"].split("-")[0] for r in got}
        assert len(tags) == 1, f"spliced two datasets together: {sorted(tags)}"


def test_stored_records_are_json_serializable(container):
    cache.store_recipes(records(3))
    # The stub already calls json.dumps on every document; assert explicitly.
    for key, doc in container.items.items():
        assert json.dumps(doc)


# ---------------------------------------------------------------------------
# Cache status
# ---------------------------------------------------------------------------

def test_cache_status_reports_counts(container):
    cache.store_insights({"total_recipes": 7})
    cache.store_recipes(records(7))
    status = cache.get_cache_status()
    assert status["redis"] == "not in use"
    assert status["cosmosdb"] == "connected"
    assert status["insights_cached"] is True
    assert status["recipes_cached"] is True
    assert status["recipe_count"] == 7


# ---------------------------------------------------------------------------
# Redis opt-out
# ---------------------------------------------------------------------------

class _CountingRedisModule(types.ModuleType):
    """Fake `redis` module recording every client construction."""

    def __init__(self, ping_ok=True):
        super().__init__("redis")
        self.constructions = 0
        self.pings = 0
        self._ping_ok = ping_ok
        module = self

        class Redis:
            def __init__(self, **kwargs):
                module.constructions += 1
                self.kwargs = kwargs

            def ping(self):
                module.pings += 1
                if not module._ping_ok:
                    raise OSError("connection refused")
                return True

        self.Redis = Redis


@pytest.fixture
def redis_reset(monkeypatch):
    monkeypatch.setattr(cache, "_redis_client", None)
    monkeypatch.setattr(cache, "_redis_tried", False)
    monkeypatch.delenv("REDIS_HOST", raising=False)
    return monkeypatch


def test_get_redis_returns_none_and_never_dials_when_host_unset(redis_reset):
    fake = _CountingRedisModule()
    redis_reset.setitem(sys.modules, "redis", fake)

    results = [cache._get_redis() for _ in range(5)]

    assert results == [None] * 5
    # At most one connection attempt across repeated calls -- in fact zero,
    # because an unset REDIS_HOST short-circuits before importing redis.
    assert fake.constructions <= 1
    assert fake.constructions == 0
    assert fake.pings == 0
    assert cache._redis_tried is True


def test_get_redis_blank_host_is_treated_as_unset(redis_reset):
    fake = _CountingRedisModule()
    redis_reset.setitem(sys.modules, "redis", fake)
    redis_reset.setenv("REDIS_HOST", "   ")

    assert cache._get_redis() is None
    assert cache._get_redis() is None
    assert fake.constructions == 0


def test_failed_connection_is_attempted_only_once(redis_reset):
    """A dead Redis must not be redialled on every request."""
    fake = _CountingRedisModule(ping_ok=False)
    redis_reset.setitem(sys.modules, "redis", fake)
    redis_reset.setenv("REDIS_HOST", "redis.invalid")

    results = [cache._get_redis() for _ in range(5)]

    assert results == [None] * 5
    assert fake.constructions == 1
    assert fake.pings == 1


def test_successful_connection_is_reused(redis_reset):
    fake = _CountingRedisModule(ping_ok=True)
    redis_reset.setitem(sys.modules, "redis", fake)
    redis_reset.setenv("REDIS_HOST", "redis.example")

    first = cache._get_redis()
    assert first is not None
    for _ in range(4):
        assert cache._get_redis() is first
    assert fake.constructions == 1


# ---------------------------------------------------------------------------
# "Cached but empty" is not the same as "nothing cached"
# ---------------------------------------------------------------------------

def test_health_reports_an_empty_cached_dataset_as_cached(container,
                                                          monkeypatch):
    """/api/recipes answers 200 with zero results for an empty cached dataset,
    so the health check must not call the same state uncached."""
    monkeypatch.setattr(cache, "_memory_store", {"recipes_cache": []})
    status = cache.get_cache_status()
    assert cache.get_recipes() == []
    assert status["recipes_cached"] is True
    assert status["recipe_count"] == 0


def test_health_reports_nothing_cached_when_nothing_is(container):
    status = cache.get_cache_status()
    assert cache.get_recipes() is None
    assert status["recipes_cached"] is False
    assert status["recipe_count"] == 0


def test_health_count_comes_from_metadata_not_a_stale_local_copy(
        container, monkeypatch):
    """Cosmos holds an empty dataset while this instance still has the old
    list in memory; the reported count must follow Cosmos."""
    cache.store_recipes([])
    monkeypatch.setitem(cache._memory_store, "recipes_cache", records(7806))
    assert cache.get_cache_status()["recipe_count"] == 0


# ---------------------------------------------------------------------------
# A Redis mirror that cannot be refreshed must not keep serving
# ---------------------------------------------------------------------------

class FailingWriteRedis:
    """Reads fine, refuses writes -- a transient Azure Cache error."""

    def __init__(self, seeded):
        self.store = dict(seeded)
        self.deleted: list = []

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value):
        raise RuntimeError("simulated transient Redis write error")

    def delete(self, key):
        self.deleted.append(key)
        self.store.pop(key, None)

    def ping(self):
        return True


def test_stale_recipes_are_dropped_when_the_redis_mirror_fails(
        container, monkeypatch):
    """Redis is read before Cosmos and the keys carry no TTL, so a value that
    cannot be refreshed would be served ahead of the fresh Cosmos copy for as
    long as the cache lived."""
    stale = FailingWriteRedis({"recipes_cache": json.dumps(
        [{"Recipe_name": "OLD-recipe-0"}])})
    monkeypatch.setattr(cache, "_redis_client", stale)
    monkeypatch.setattr(cache, "_redis_tried", True)

    cache.store_recipes(records(3, tag="NEW"))

    assert "recipes_cache" in stale.deleted
    drop_memory(monkeypatch)
    got = cache.get_recipes()
    assert [r["Recipe_name"].split("-")[0] for r in got] == ["NEW"] * 3


def test_stale_insights_are_dropped_when_the_redis_mirror_fails(
        container, monkeypatch):
    stale = FailingWriteRedis({cache.CACHE_KEY: json.dumps(
        {"data": {"total_recipes": 1}, "updated_at": "old"})})
    monkeypatch.setattr(cache, "_redis_client", stale)
    monkeypatch.setattr(cache, "_redis_tried", True)

    cache.store_insights({"total_recipes": 7806})

    assert cache.CACHE_KEY in stale.deleted
    drop_memory(monkeypatch)
    assert cache.get_insights()["data"]["total_recipes"] == 7806
