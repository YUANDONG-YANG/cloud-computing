"""Caching layer for Project 3 (Phase 3).

Stores the results that the blob trigger pre-computes so that HTTP requests
never recalculate them.

Cosmos DB is the durable store: on Azure Functions the blob trigger and the
HTTP handlers are not guaranteed to share a process, so anything kept only in
module state is invisible to the request that needs it.  Redis is supported as
an optional read-through layer in front of Cosmos and is skipped entirely when
REDIS_HOST is unset, which is the default -- Azure Cache for Redis has no free
tier, and the rubric allows "an external cache (like Redis) or a database
(like Cosmos)".

The in-memory dict is a convenience for `func start` on one machine only.  It
is never a substitute for Cosmos in a deployed app.
"""
import json
import os
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

CACHE_KEY = "insights_cache"
RECIPES_META_KEY = "recipes_meta"

# Nothing is ever queried inside the cached payloads: chunk documents are read
# by id and the only queries filter on `id`.  Indexing every path inside a
# 2,000-element `records` array would charge write RUs for an index no read
# uses, so both payload subtrees are excluded.  deploy.sh applies the same
# policy when it creates the container.
CACHE_INDEXING_POLICY = {
    "indexingMode": "consistent",
    "automatic": True,
    "includedPaths": [{"path": "/*"}],
    "excludedPaths": [{"path": "/records/*"}, {"path": "/data/*"}],
}

# A Cosmos document may not exceed 2 MB.  The full cleaned dataset serializes
# to roughly 1.2 MB, so it is split across documents of this many records.
CHUNK_SIZE = 2000


# ---------------------------------------------------------------------------
# Redis (optional read-through layer)
# ---------------------------------------------------------------------------

_redis_client = None
_redis_tried = False


def _get_redis():
    """Return a connected Redis client, or None when Redis is not in use.

    A failed connection is remembered: without that, every call pays the
    connect timeout again and a single page load can stall for tens of
    seconds.
    """
    global _redis_client, _redis_tried
    if _redis_tried:
        return _redis_client
    _redis_tried = True

    host = os.environ.get("REDIS_HOST", "").strip()
    if not host:
        logger.info("REDIS_HOST unset; using Cosmos DB only")
        return None

    try:
        import redis as _redis
        _redis_client = _redis.Redis(
            host=host,
            port=int(os.environ.get("REDIS_PORT", "6380")),
            password=os.environ.get("REDIS_PASSWORD", "") or None,
            ssl=os.environ.get("REDIS_SSL", "true").lower() == "true",
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        _redis_client.ping()
        logger.info("Redis connected at %s", host)
    except Exception as exc:
        logger.warning("Redis unavailable (%s); using Cosmos DB only", exc)
        _redis_client = None
    return _redis_client


# ---------------------------------------------------------------------------
# Cosmos DB (durable store)
# ---------------------------------------------------------------------------

_cosmos_container = None
_cosmos_tried = False


def _get_cosmos():
    """Return the Cosmos cache container, or None when it is not configured."""
    global _cosmos_container, _cosmos_tried
    if _cosmos_tried:
        return _cosmos_container
    _cosmos_tried = True

    endpoint = os.environ.get("COSMOS_ENDPOINT", "").strip()
    key = os.environ.get("COSMOS_KEY", "").strip()
    if not endpoint or not key:
        logger.warning("Cosmos DB not configured; cache will not survive "
                       "across function instances")
        return None

    try:
        from azure.cosmos import CosmosClient, PartitionKey
        client = CosmosClient(endpoint, credential=key)
        db = client.create_database_if_not_exists(
            os.environ.get("COSMOS_DATABASE", "nutritiondb")
        )
        _cosmos_container = db.create_container_if_not_exists(
            id=os.environ.get("COSMOS_CACHE_CONTAINER", "cache"),
            partition_key=PartitionKey(path="/partitionKey"),
            indexing_policy=CACHE_INDEXING_POLICY,
        )
        logger.info("Cosmos DB cache container ready")
    except Exception as exc:
        logger.warning("Cosmos DB cache unavailable (%s)", exc)
        _cosmos_container = None
    return _cosmos_container


def _cosmos_read(doc_id: str) -> Optional[dict]:
    container = _get_cosmos()
    if not container:
        return None
    try:
        return container.read_item(item=doc_id, partition_key="cache")
    except Exception as exc:
        logger.info("Cosmos read miss for %s (%s)", doc_id, exc)
        return None


def _cosmos_write(doc: dict) -> bool:
    container = _get_cosmos()
    if not container:
        return False
    try:
        container.upsert_item(doc)
        return True
    except Exception as exc:
        logger.warning("Cosmos write failed for %s: %s", doc.get("id"), exc)
        return False


def _cosmos_delete(doc_id: str) -> None:
    container = _get_cosmos()
    if not container:
        return
    try:
        container.delete_item(item=doc_id, partition_key="cache")
    except Exception:
        pass  # Already gone, which is the desired state.


def _redis_discard(client, key: str) -> None:
    """Delete a Redis key, ignoring failures.

    Used after a failed mirror write: a key that cannot be refreshed must not
    stay behind, because reads prefer Redis and nothing here sets a TTL.
    """
    try:
        client.delete(key)
    except Exception as exc:
        logger.warning("Could not drop stale Redis key %s: %s", key, exc)


# ---------------------------------------------------------------------------
# Local-only fallback
# ---------------------------------------------------------------------------

_memory_store: dict = {}


# ---------------------------------------------------------------------------
# Insights
# ---------------------------------------------------------------------------

def store_insights(data: dict) -> bool:
    """Persist the pre-computed analytics.  Called only by the blob trigger."""
    updated_at = datetime.now(timezone.utc).isoformat()
    payload = {"data": data, "updated_at": updated_at}

    wrote = _cosmos_write({
        "id": CACHE_KEY,
        "partitionKey": "cache",
        **payload,
    })
    if wrote:
        logger.info("Insights stored in Cosmos DB")

    r = _get_redis()
    if r:
        try:
            r.set(CACHE_KEY, json.dumps(payload))
            logger.info("Insights mirrored to Redis")
        except Exception as exc:
            # Redis is read first and the keys carry no TTL, so leaving the
            # previous value in place would serve it indefinitely over the
            # fresh copy in Cosmos.  Drop the key and let reads fall through.
            logger.warning("Redis write failed (%s); dropping the stale key", exc)
            _redis_discard(r, CACHE_KEY)

    _memory_store[CACHE_KEY] = payload
    return wrote or bool(r)


def get_insights() -> Optional[dict]:
    """Read the pre-computed analytics.  Never recalculates."""
    r = _get_redis()
    if r:
        try:
            raw = r.get(CACHE_KEY)
            if raw:
                parsed = json.loads(raw)
                parsed["cache_source"] = "redis"
                return parsed
        except Exception as exc:
            logger.warning("Redis read failed: %s", exc)

    doc = _cosmos_read(CACHE_KEY)
    if doc:
        return {
            "data": doc.get("data", {}),
            "updated_at": doc.get("updated_at", ""),
            "cache_source": "cosmosdb",
        }

    payload = _memory_store.get(CACHE_KEY)
    if payload:
        return {**payload, "cache_source": "memory"}
    return None


# ---------------------------------------------------------------------------
# Recipes
# ---------------------------------------------------------------------------

def store_recipes(recipes_list: list) -> bool:
    """Persist the cleaned recipe records for search, filter and pagination.

    Written to Cosmos in chunks so the dataset is readable from any function
    instance, not just the one that handled the blob trigger.
    """
    updated_at = datetime.now(timezone.utc).isoformat()
    total = len(recipes_list)
    chunks = [recipes_list[i:i + CHUNK_SIZE]
              for i in range(0, total, CHUNK_SIZE)] or [[]]

    previous = _cosmos_read(RECIPES_META_KEY) or {}
    previous_count = int(previous.get("chunk_count", 0))

    # Retire the metadata before touching the chunks.  The chunk documents are
    # replaced one at a time, so mid-rewrite the set is a mixture of the new
    # dataset and the old one; a reader that still trusted the old metadata
    # would splice the two and serve the result as if it were valid.  With the
    # metadata gone the cache reads as empty until the new set is complete,
    # which is the honest answer and the one the endpoints turn into a 503.
    if previous:
        _cosmos_delete(RECIPES_META_KEY)

    wrote = True
    for index, chunk in enumerate(chunks):
        if not _cosmos_write({
            "id": f"recipes_chunk_{index:03d}",
            "partitionKey": "cache",
            "records": chunk,
        }):
            wrote = False
            break

    if wrote:
        # Drop chunks left over from a larger previous dataset before
        # publishing the new count.
        for index in range(len(chunks), previous_count):
            _cosmos_delete(f"recipes_chunk_{index:03d}")

        wrote = _cosmos_write({
            "id": RECIPES_META_KEY,
            "partitionKey": "cache",
            "chunk_count": len(chunks),
            "record_count": total,
            "updated_at": updated_at,
        })
        if wrote:
            logger.info("Stored %d recipes across %d Cosmos documents",
                        total, len(chunks))

    r = _get_redis()
    if r:
        try:
            r.set("recipes_cache", json.dumps(recipes_list))
            logger.info("Recipes mirrored to Redis (%d records)", total)
        except Exception as exc:
            logger.warning("Redis recipe write failed (%s); dropping the "
                           "stale key", exc)
            _redis_discard(r, "recipes_cache")

    _memory_store["recipes_cache"] = recipes_list
    return wrote or bool(r)


def get_recipes() -> Optional[list]:
    """Read the cleaned recipe records, or None when nothing is cached."""
    r = _get_redis()
    if r:
        try:
            raw = r.get("recipes_cache")
            if raw:
                return json.loads(raw)
        except Exception as exc:
            logger.warning("Redis recipe read failed: %s", exc)

    meta = _cosmos_read(RECIPES_META_KEY)
    if meta:
        records: list = []
        for index in range(int(meta.get("chunk_count", 0))):
            doc = _cosmos_read(f"recipes_chunk_{index:03d}")
            if doc is None:
                # The durable cache disagrees with its own metadata. Report a
                # miss instead of falling through to the process-local copy,
                # which may hold an entirely different dataset.
                logger.warning(
                    "Recipe chunk %d is missing; reporting the cache as empty "
                    "rather than serving a copy that may be stale", index)
                return None
            records.extend(doc.get("records", []))
        # An empty dataset that was cached on purpose returns []; None is
        # reserved for nothing having been cached at all.
        return records

    return _memory_store.get("recipes_cache")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

def get_cache_status() -> dict:
    """Report cache health for /api/health.

    Recipe state comes from the metadata document rather than from
    `get_recipes`, so a health check does not pull the whole dataset back out
    of Cosmos just to report a count.
    """
    insights = get_insights()
    meta = _cosmos_read(RECIPES_META_KEY) or {}
    local = _memory_store.get("recipes_cache")

    # A cached dataset that happens to be empty is still a cached dataset, so
    # these test for presence rather than truthiness.  Reporting it as absent
    # would contradict /api/recipes, which answers 200 with zero results.
    if meta:
        recipes_cached = True
        recipe_count = int(meta.get("record_count", 0))
    else:
        recipes_cached = local is not None
        recipe_count = len(local) if local is not None else 0

    return {
        "redis": "connected" if _get_redis() else "not in use",
        "cosmosdb": "connected" if _get_cosmos() else "not configured",
        "insights_cached": insights is not None,
        "insights_updated_at": (insights or {}).get("updated_at", ""),
        "recipes_cached": recipes_cached,
        "recipe_count": recipe_count,
        "recipes_updated_at": meta.get("updated_at", ""),
        "source": (insights or {}).get("cache_source", "none"),
    }
