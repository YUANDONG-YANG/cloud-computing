"""Caching layer for Project 3 (Phase 3).

Provides a unified interface for storing and retrieving pre-computed
analytics results.  Supports Redis (primary) with Cosmos DB fallback.
When neither is available, falls back to an in-memory dict for local
development.
"""
import json
import os
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Redis connection
# ---------------------------------------------------------------------------

_redis_client = None


def _get_redis():
    """Lazy-init Redis client."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis as _redis
        host = os.environ.get("REDIS_HOST", "localhost")
        port = int(os.environ.get("REDIS_PORT", "6379"))
        password = os.environ.get("REDIS_PASSWORD", "") or None
        use_ssl = os.environ.get("REDIS_SSL", "false").lower() == "true"
        _redis_client = _redis.Redis(
            host=host, port=port, password=password,
            ssl=use_ssl, decode_responses=True,
            socket_connect_timeout=5, socket_timeout=5,
        )
        _redis_client.ping()
        logger.info("Redis connected at %s:%s", host, port)
        return _redis_client
    except Exception as exc:
        logger.warning("Redis unavailable (%s), using fallback", exc)
        _redis_client = None
        return None


# ---------------------------------------------------------------------------
# Cosmos DB connection (fallback cache store)
# ---------------------------------------------------------------------------

_cosmos_container = None


def _get_cosmos_cache():
    """Lazy-init Cosmos DB cache container."""
    global _cosmos_container
    if _cosmos_container is not None:
        return _cosmos_container
    try:
        from azure.cosmos import CosmosClient, PartitionKey
        endpoint = os.environ.get("COSMOS_ENDPOINT", "")
        key = os.environ.get("COSMOS_KEY", "")
        if not endpoint or not key:
            return None
        client = CosmosClient(endpoint, credential=key)
        db = client.create_database_if_not_exists(
            os.environ.get("COSMOS_DATABASE", "nutritiondb")
        )
        _cosmos_container = db.create_container_if_not_exists(
            id=os.environ.get("COSMOS_CACHE_CONTAINER", "cache"),
            partition_key=PartitionKey(path="/partitionKey"),
        )
        logger.info("Cosmos DB cache container ready")
        return _cosmos_container
    except Exception as exc:
        logger.warning("Cosmos DB cache unavailable (%s)", exc)
        return None


# ---------------------------------------------------------------------------
# In-memory fallback for local development
# ---------------------------------------------------------------------------

_memory_store: dict = {}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

CACHE_KEY = "insights_cache"
RECIPES_KEY = "recipes_cache"


def store_insights(data: dict) -> bool:
    """Store pre-computed analytics insights."""
    payload = json.dumps({
        "data": data,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })

    # Try Redis first
    r = _get_redis()
    if r:
        try:
            r.set(CACHE_KEY, payload)
            logger.info("Insights cached in Redis (%d bytes)", len(payload))
            return True
        except Exception as exc:
            logger.warning("Redis write failed: %s", exc)

    # Try Cosmos DB
    cosmos = _get_cosmos_cache()
    if cosmos:
        try:
            doc = {
                "id": CACHE_KEY,
                "partitionKey": "cache",
                "data": data,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            cosmos.upsert_item(doc)
            logger.info("Insights cached in Cosmos DB")
            return True
        except Exception as exc:
            logger.warning("Cosmos write failed: %s", exc)

    # In-memory fallback
    _memory_store[CACHE_KEY] = payload
    logger.info("Insights cached in memory")
    return True


def get_insights() -> Optional[dict]:
    """Retrieve pre-computed analytics insights."""
    # Try Redis
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

    # Try Cosmos DB
    cosmos = _get_cosmos_cache()
    if cosmos:
        try:
            doc = cosmos.read_item(item=CACHE_KEY, partition_key="cache")
            result = {
                "data": doc.get("data", {}),
                "updated_at": doc.get("updated_at", ""),
                "cache_source": "cosmosdb",
            }
            return result
        except Exception as exc:
            logger.warning("Cosmos read failed: %s", exc)

    # In-memory fallback
    raw = _memory_store.get(CACHE_KEY)
    if raw:
        parsed = json.loads(raw)
        parsed["cache_source"] = "memory"
        return parsed
    return None


def store_recipes(recipes_list: list) -> bool:
    """Store the full cleaned recipes list for search/filter/pagination."""
    payload = json.dumps(recipes_list)

    r = _get_redis()
    if r:
        try:
            r.set(RECIPES_KEY, payload)
            logger.info("Recipes cached in Redis (%d records)", len(recipes_list))
            return True
        except Exception as exc:
            logger.warning("Redis recipe write failed: %s", exc)

    _memory_store[RECIPES_KEY] = payload
    logger.info("Recipes cached in memory (%d records)", len(recipes_list))
    return True


def get_recipes() -> Optional[list]:
    """Retrieve the full cleaned recipes list."""
    r = _get_redis()
    if r:
        try:
            raw = r.get(RECIPES_KEY)
            if raw:
                return json.loads(raw)
        except Exception as exc:
            logger.warning("Redis recipe read failed: %s", exc)

    raw = _memory_store.get(RECIPES_KEY)
    if raw:
        return json.loads(raw)
    return None


def get_cache_status() -> dict:
    """Return current cache health for the /api/health endpoint."""
    status = {
        "redis": "disconnected",
        "cosmosdb": "disconnected",
        "memory_keys": len(_memory_store),
        "insights_cached": False,
        "recipes_cached": False,
    }
    r = _get_redis()
    if r:
        try:
            r.ping()
            status["redis"] = "connected"
        except Exception:
            pass

    cosmos = _get_cosmos_cache()
    if cosmos:
        status["cosmosdb"] = "connected"

    if get_insights() is not None:
        status["insights_cached"] = True
    if get_recipes() is not None:
        status["recipes_cached"] = True

    return status
