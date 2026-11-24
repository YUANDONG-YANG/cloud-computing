"""Azure Functions app for Project 3 (Phase 3) - Improved Cloud Dashboard.

Provides:
  - Blob trigger for automatic data cleaning when All_Diets.csv changes
  - Cached analytics endpoint (/api/insights)
  - Filtered, searchable, paginated recipe endpoint (/api/recipes)
  - Health check (/api/health)
  - Authentication endpoints (register, login, me, logout)
  - OAuth endpoints (Google, GitHub)

Uses the Python v2 programming model.
"""
import io
import json
import logging
import os
import secrets
import threading
from urllib.parse import quote
import time
from datetime import datetime, timezone

import azure.functions as func
import pandas as pd

from nutrition import clean_data, precompute_all, df_to_records
from auth import (
    hash_password, verify_password,
    create_token, get_current_user,
    create_state, state_cookie, clear_state_cookie,
    verify_state_request,
    google_auth_url, google_exchange_code,
    github_auth_url, github_exchange_code,
)
from cache import (
    store_insights, get_insights,
    store_recipes, get_recipes_with_source,
    get_cache_status,
)
from models import User, validate_registration, validate_login
from ratelimit import RecentKeys, SlidingWindowLimiter, client_ip

app = func.FunctionApp()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cosmos DB users container (lazy init)
# ---------------------------------------------------------------------------
#
# Two situations used to look the same here and must not:
#
#   * Cosmos is *not configured* (no COSMOS_ENDPOINT / COSMOS_KEY).  That is
#     local development, and the in-memory store is the intended store.
#   * Cosmos *is configured* but cannot be reached.  Then there is no durable
#     store, and pretending otherwise registers accounts that exist in one
#     process only and vanish on restart or on the next instance.  The auth
#     handlers fail closed with a 503 instead.


class UserStoreUnavailable(Exception):
    """Cosmos DB is configured for users but cannot be used right now."""


# A failed initialization is retried after this many seconds.  Retrying on
# every request would make each one pay the connect timeout; never retrying
# (the old behaviour) turned one transient failure into an outage for the
# life of the process.
_USERS_RETRY_SECONDS = 30

_users_container = None
_users_failed_at = None       # time.monotonic() of the last failed init
_users_unconfigured_logged = False
_users_partial_logged = False


def _cosmos_users_config() -> str:
    """"configured", "unconfigured" (both unset) or "partial" (one unset).

    Only a complete absence means local development.  One setting without
    the other is a broken deployment and must not quietly become the
    in-memory store.
    """
    has_endpoint = bool(os.environ.get("COSMOS_ENDPOINT", "").strip())
    has_key = bool(os.environ.get("COSMOS_KEY", "").strip())
    if has_endpoint and has_key:
        return "configured"
    if not has_endpoint and not has_key:
        return "unconfigured"
    return "partial"


def _get_users():
    """Return the Cosmos DB users container, or None for local development.

    Returns None only when neither COSMOS_ENDPOINT nor COSMOS_KEY is set.
    Raises UserStoreUnavailable when only one of them is set, or when both
    are set but initialization failed.
    """
    global _users_container, _users_failed_at
    global _users_unconfigured_logged, _users_partial_logged
    if _users_container is not None:
        return _users_container
    config = _cosmos_users_config()
    if config == "unconfigured":
        if not _users_unconfigured_logged:
            logger.warning("Cosmos DB not configured, using in-memory users")
            _users_unconfigured_logged = True
        return None
    if config == "partial":
        if not _users_partial_logged:
            logger.error("Only one of COSMOS_ENDPOINT and COSMOS_KEY is set; "
                         "refusing to fall back to in-memory users")
            _users_partial_logged = True
        raise UserStoreUnavailable("Cosmos DB is only partly configured")

    now = time.monotonic()
    if (_users_failed_at is not None
            and now - _users_failed_at < _USERS_RETRY_SECONDS):
        raise UserStoreUnavailable("Cosmos DB users container unavailable")
    try:
        from azure.cosmos import CosmosClient, PartitionKey
        client = CosmosClient(os.environ["COSMOS_ENDPOINT"].strip(),
                              credential=os.environ["COSMOS_KEY"].strip())
        db = client.create_database_if_not_exists(
            os.environ.get("COSMOS_DATABASE", "nutritiondb")
        )
        _users_container = db.create_container_if_not_exists(
            id=os.environ.get("COSMOS_USERS_CONTAINER", "users"),
            partition_key=PartitionKey(path="/partitionKey"),
        )
        _users_failed_at = None
        return _users_container
    except Exception as exc:
        _users_failed_at = now
        logger.error("Cosmos DB users container unavailable: %s", exc)
        raise UserStoreUnavailable(str(exc)) from exc


# In-memory user store, used only when Cosmos is not configured (local dev).
_memory_users: dict = {}
_memory_lock = threading.Lock()


def _find_user_by_email(email: str):
    """Look up a user by email.

    Raises UserStoreUnavailable when Cosmos is configured but the lookup
    cannot be answered: "unknown" must not be reported as "no such user",
    or registration would create a second account for an existing address.
    """
    container = _get_users()
    if container is None:
        return _memory_users.get(email)
    try:
        items = list(container.query_items(
            query="SELECT * FROM c WHERE c.email = @email",
            parameters=[{"name": "@email", "value": email}],
            partition_key=email,
        ))
    except Exception as exc:
        logger.error("User lookup failed: %s", exc)
        raise UserStoreUnavailable(str(exc)) from exc
    if not items:
        return None
    if len(items) > 1:
        # Possible only for documents written before ids were derived from
        # the email.  Pick the oldest deterministically: it is the original
        # owner of the address.
        logger.warning("%d user documents share one email; using the oldest",
                       len(items))
        items.sort(key=lambda d: (d.get("created_at", ""), d.get("id", "")))
    return User.from_dict(items[0])


def _find_user_by_provider(provider: str, provider_id: str):
    """Look up a user by OAuth provider + provider_id.

    Raises UserStoreUnavailable when Cosmos is configured but unreachable.
    """
    container = _get_users()
    if container is None:
        for u in list(_memory_users.values()):
            if u.provider == provider and u.provider_id == provider_id:
                return u
        return None
    try:
        items = list(container.query_items(
            query="SELECT * FROM c WHERE c.provider = @p AND c.provider_id = @pid",
            parameters=[
                {"name": "@p", "value": provider},
                {"name": "@pid", "value": provider_id},
            ],
            enable_cross_partition_query=True,
        ))
    except Exception as exc:
        logger.error("OAuth user lookup failed: %s", exc)
        raise UserStoreUnavailable(str(exc)) from exc
    if not items:
        return None
    items.sort(key=lambda d: (d.get("created_at", ""), d.get("id", "")))
    return User.from_dict(items[0])


def _save_user(user: User) -> bool:
    """Update an existing user.  Returns False when the write did not happen.

    Nothing is written to memory when Cosmos is configured: a copy that
    exists on this instance alone would make the outcome depend on which
    instance serves the next request.
    """
    try:
        container = _get_users()
    except UserStoreUnavailable:
        return False
    if container is None:
        with _memory_lock:
            _memory_users[user.email] = user
        return True
    try:
        container.upsert_item(user.to_dict())
        return True
    except Exception as exc:
        logger.error("Durable user save failed for %s: %s", user.email, exc)
        return False


USER_CREATED = "created"
USER_EXISTS = "exists"
USER_STORE_DOWN = "unavailable"


def _create_user(user: User) -> str:
    """Create a new user only if no account holds the id/email yet.

    Returns USER_CREATED, USER_EXISTS (another request won the race), or
    USER_STORE_DOWN.  The check and the write are one atomic operation in
    the store, unlike a lookup followed by an upsert.
    """
    try:
        container = _get_users()
    except UserStoreUnavailable:
        return USER_STORE_DOWN
    if container is None:
        with _memory_lock:
            if user.email in _memory_users:
                return USER_EXISTS
            _memory_users[user.email] = user
        return USER_CREATED
    from azure.cosmos.exceptions import CosmosResourceExistsError
    try:
        container.create_item(user.to_dict())
        return USER_CREATED
    except CosmosResourceExistsError:
        return USER_EXISTS
    except Exception as exc:
        logger.error("Durable user create failed for %s: %s", user.email, exc)
        return USER_STORE_DOWN


def _cors_headers():
    """Standard CORS headers for all responses."""
    frontend = os.environ.get("FRONTEND_URL", "*")
    return {
        "Access-Control-Allow-Origin": frontend,
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
        "Access-Control-Max-Age": "86400",
    }


def _json_response(data, status=200):
    """Create an HTTP response with JSON body and CORS headers."""
    return func.HttpResponse(
        body=json.dumps(data),
        status_code=status,
        mimetype="application/json",
        headers=_cors_headers(),
    )


def _error(msg, status=400):
    return _json_response({"error": msg}, status)


def _demo_fallback_enabled() -> bool:
    """Whether to serve hardcoded sample data when the cache is empty.

    Off by default.  The sample data mirrors the real result set, so leaving it
    on makes a broken cache indistinguishable from a working one -- which is
    exactly what the Phase 3 demo has to prove.
    """
    return os.environ.get("ENABLE_DEMO_FALLBACK", "false").lower() == "true"


def _reject_unauthenticated(req: func.HttpRequest):
    """Return a 401 response when the request carries no valid JWT, else None.

    The dashboard is behind a login, so the data endpoints it calls have to
    verify the token themselves; a client-side redirect is not access control.
    """
    if get_current_user(req) is None:
        return _error("Authentication required. Please log in.", 401)
    return None


# ===================================================================
# BLOB TRIGGER: Automatic data cleaning on CSV upload/change
# ===================================================================

@app.blob_trigger(
    arg_name="myblob",
    path="raw-data/All_Diets.csv",
    connection="AzureWebJobsStorage",
)
def blob_trigger_clean(myblob: func.InputStream):
    """Triggered when All_Diets.csv is uploaded/modified in Blob Storage.

    1. Reads and cleans the raw CSV data.
    2. Pre-computes all aggregations (average macros, top recipes, etc.).
    3. Stores results in Cosmos DB (mirrored to Redis when it is in use).
    4. Saves cleaned CSV back to a separate blob container.
    """
    logger.info("Blob trigger fired: %s (%d bytes)", myblob.name, myblob.length or 0)
    start = time.time()

    try:
        raw_bytes = myblob.read()
        raw_df = pd.read_csv(io.BytesIO(raw_bytes))
        logger.info("Loaded %d rows from blob", len(raw_df))

        # Step 1: Clean data
        df = clean_data(raw_df)
        logger.info("Cleaned data: %d rows", len(df))

        # Step 2: Pre-compute all analytics
        insights = precompute_all(df)
        store_insights(insights)
        logger.info("Pre-computed insights cached")

        # Step 3: Store recipe records for search/filter/pagination
        records = df_to_records(df)
        store_recipes(records)
        logger.info("Stored %d recipe records for search", len(records))

        # Step 4: Save cleaned CSV to clean-data container
        try:
            from azure.storage.blob import BlobServiceClient
            conn_str = os.environ.get("BLOB_CONNECTION_STRING",
                                      os.environ.get("AzureWebJobsStorage", ""))
            clean_container = os.environ.get("BLOB_CONTAINER_CLEAN", "clean-data")
            if conn_str:
                blob_service = BlobServiceClient.from_connection_string(conn_str)
                container_client = blob_service.get_container_client(clean_container)
                try:
                    container_client.create_container()
                except Exception:
                    pass  # Container may already exist
                cleaned_csv = df.to_csv(index=False)
                container_client.upload_blob(
                    name="cleaned_recipes.csv",
                    data=cleaned_csv,
                    overwrite=True,
                )
                logger.info("Cleaned CSV saved to %s/cleaned_recipes.csv", clean_container)
        except Exception as exc:
            logger.warning("Could not save cleaned CSV to blob: %s", exc)

        elapsed = time.time() - start
        logger.info("Blob trigger completed in %.2fs", elapsed)

    except Exception as exc:
        logger.exception("Blob trigger failed: %s", exc)
        raise


# ===================================================================
# DATA API: Cached insights
# ===================================================================

@app.route(route="insights", methods=["GET", "OPTIONS"], auth_level=func.AuthLevel.ANONYMOUS)
def get_insights_api(req: func.HttpRequest) -> func.HttpResponse:
    """Return pre-computed visualization data from cache.

    Served from the cache the blob trigger wrote, NOT re-computed per request.
    """
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=204, headers=_cors_headers())

    denied = _reject_unauthenticated(req)
    if denied:
        return denied

    start = time.time()
    cached = get_insights()

    if cached:
        elapsed = round((time.time() - start) * 1000, 1)
        result = {
            "status": "ok",
            "source": cached.get("cache_source", "cache"),
            "updated_at": cached.get("updated_at", ""),
            "response_time_ms": elapsed,
            "data": cached.get("data", {}),
        }
        return _json_response(result)

    if not _demo_fallback_enabled():
        return _json_response({
            "error": "No pre-computed results are cached yet. Upload "
                     "All_Diets.csv to the raw-data container to run the "
                     "blob trigger.",
            "source": "empty",
        }, 503)

    elapsed = round((time.time() - start) * 1000, 1)
    return _json_response({
        "status": "ok",
        "source": "fallback",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "response_time_ms": elapsed,
        "data": _get_fallback_insights(),
    })


def _get_fallback_insights():
    """Sample insights for working on the UI without Azure.

    Only served when ENABLE_DEMO_FALLBACK is on, and the dashboard labels it
    as sample data when it is. The totals and averages below were measured
    from Project1/data/All_Diets.csv; `top_recipes` and `cuisine_types` are
    left empty rather than invented, so those charts render empty instead of
    showing numbers that are not in any dataset.
    """
    return {
        "total_recipes": 7806,
        "diet_types": ["dash", "keto", "mediterranean", "paleo", "vegan"],
        "cuisine_types": [],
        "average_macros": {
            "dash": {"Protein": 69.28, "Carbs": 160.54, "Fat": 101.15},
            "keto": {"Protein": 101.27, "Carbs": 57.97, "Fat": 153.12},
            "mediterranean": {"Protein": 101.11, "Carbs": 152.91, "Fat": 101.42},
            "paleo": {"Protein": 88.67, "Carbs": 129.55, "Fat": 135.67},
            "vegan": {"Protein": 56.16, "Carbs": 254.00, "Fat": 103.30},
        },
        "recipe_counts": {
            "dash": 1745,
            "keto": 1512,
            "mediterranean": 1753,
            "paleo": 1274,
            "vegan": 1522,
        },
        "heatmap": {
            "diets": ["dash", "keto", "mediterranean", "paleo", "vegan"],
            "nutrients": ["Protein(g)", "Carbs(g)", "Fat(g)"],
            "values": [
                [69.28, 160.54, 101.15],
                [101.27, 57.97, 153.12],
                [101.11, 152.91, 101.42],
                [88.67, 129.55, 135.67],
                [56.16, 254.00, 103.30],
            ],
        },
        "top_recipes": [],
        "common_cuisines": {},
    }


# ===================================================================
# DATA API: Recipe search, filter, pagination
# ===================================================================

@app.route(route="recipes", methods=["GET", "OPTIONS"], auth_level=func.AuthLevel.ANONYMOUS)
def get_recipes_api(req: func.HttpRequest) -> func.HttpResponse:
    """Search, filter, and paginate recipes.

    Query params:
      diet     - filter by diet type (exact match, case-insensitive)
      search   - keyword search (recipe name, cuisine, partial match)
      page     - page number (default 1)
      pageSize - results per page (default 20, max 100)
    """
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=204, headers=_cors_headers())

    denied = _reject_unauthenticated(req)
    if denied:
        return denied

    start = time.time()

    # None means nothing is cached; an empty list means the cached dataset is
    # genuinely empty, which is a valid answer rather than a cache miss.
    recipes, source = get_recipes_with_source()
    if recipes is None:
        if not _demo_fallback_enabled():
            return _json_response({
                "error": "No cleaned recipes are cached yet. Upload "
                         "All_Diets.csv to the raw-data container to run the "
                         "blob trigger.",
                "source": "empty",
            }, 503)
        recipes = _get_fallback_recipes()
        source = "fallback"

    # Apply diet filter
    diet = req.params.get("diet", "").strip().lower()
    if diet:
        recipes = [r for r in recipes if r.get("Diet_type", "").lower() == diet]

    # Apply keyword search
    search = req.params.get("search", "").strip().lower()
    if search:
        recipes = [
            r for r in recipes
            if search in r.get("Recipe_name", "").lower()
            or search in r.get("Cuisine_type", "").lower()
            or search in r.get("Diet_type", "").lower()
        ]

    # Pagination
    total = len(recipes)
    try:
        page = max(1, int(req.params.get("page", "1")))
    except ValueError:
        page = 1
    try:
        page_size = min(100, max(1, int(req.params.get("pageSize", "20"))))
    except ValueError:
        page_size = 20

    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, total_pages)
    offset = (page - 1) * page_size
    page_results = recipes[offset: offset + page_size]

    elapsed = round((time.time() - start) * 1000, 1)
    return _json_response({
        "status": "ok",
        "source": source,
        "response_time_ms": elapsed,
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": total_pages,
        "hasNext": page < total_pages,
        "hasPrev": page > 1,
        "results": page_results,
    })


def _get_fallback_recipes():
    """Illustrative recipe rows for working on the table without Azure.

    These are made up, not drawn from the dataset, and are only served when
    ENABLE_DEMO_FALLBACK is on. Fifteen rows also means pagination collapses
    to a single page, so never demo against them.
    """
    demos = [
        {"Diet_type": "keto", "Recipe_name": "Keto Butter Chicken", "Cuisine_type": "indian",
         "Protein(g)": 42.5, "Carbs(g)": 8.3, "Fat(g)": 28.7},
        {"Diet_type": "keto", "Recipe_name": "Bacon Cheese Burger Bowl", "Cuisine_type": "american",
         "Protein(g)": 38.2, "Carbs(g)": 5.1, "Fat(g)": 35.4},
        {"Diet_type": "keto", "Recipe_name": "Grilled Salmon with Avocado", "Cuisine_type": "american",
         "Protein(g)": 45.0, "Carbs(g)": 4.2, "Fat(g)": 32.1},
        {"Diet_type": "paleo", "Recipe_name": "Bone Broth From Nom Nom Paleo", "Cuisine_type": "american",
         "Protein(g)": 5.22, "Carbs(g)": 1.29, "Fat(g)": 3.2},
        {"Diet_type": "paleo", "Recipe_name": "Paleo Pumpkin Pie", "Cuisine_type": "american",
         "Protein(g)": 30.91, "Carbs(g)": 302.59, "Fat(g)": 96.76},
        {"Diet_type": "paleo", "Recipe_name": "Strawberry Guacamole", "Cuisine_type": "mexican",
         "Protein(g)": 9.62, "Carbs(g)": 75.78, "Fat(g)": 59.89},
        {"Diet_type": "vegan", "Recipe_name": "Vegan Black Bean Tacos", "Cuisine_type": "mexican",
         "Protein(g)": 18.5, "Carbs(g)": 45.2, "Fat(g)": 12.3},
        {"Diet_type": "vegan", "Recipe_name": "Tofu Stir Fry", "Cuisine_type": "chinese",
         "Protein(g)": 22.1, "Carbs(g)": 28.5, "Fat(g)": 14.6},
        {"Diet_type": "vegan", "Recipe_name": "Chickpea Curry", "Cuisine_type": "indian",
         "Protein(g)": 15.8, "Carbs(g)": 42.3, "Fat(g)": 18.9},
        {"Diet_type": "dash", "Recipe_name": "Grilled Chicken Salad", "Cuisine_type": "american",
         "Protein(g)": 35.0, "Carbs(g)": 12.5, "Fat(g)": 8.2},
        {"Diet_type": "dash", "Recipe_name": "Salmon with Quinoa", "Cuisine_type": "american",
         "Protein(g)": 40.2, "Carbs(g)": 38.1, "Fat(g)": 15.6},
        {"Diet_type": "dash", "Recipe_name": "Turkey Meatball Soup", "Cuisine_type": "italian",
         "Protein(g)": 28.7, "Carbs(g)": 22.4, "Fat(g)": 11.3},
        {"Diet_type": "mediterranean", "Recipe_name": "Greek Lemon Chicken", "Cuisine_type": "greek",
         "Protein(g)": 38.5, "Carbs(g)": 15.2, "Fat(g)": 22.1},
        {"Diet_type": "mediterranean", "Recipe_name": "Falafel Wrap", "Cuisine_type": "middle eastern",
         "Protein(g)": 18.9, "Carbs(g)": 42.5, "Fat(g)": 16.8},
        {"Diet_type": "mediterranean", "Recipe_name": "Grilled Sea Bass", "Cuisine_type": "greek",
         "Protein(g)": 44.2, "Carbs(g)": 5.8, "Fat(g)": 18.5},
    ]
    return demos


# ===================================================================
# HEALTH CHECK
# ===================================================================

@app.route(route="health", methods=["GET", "OPTIONS"], auth_level=func.AuthLevel.ANONYMOUS)
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Health check endpoint with cache status."""
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=204, headers=_cors_headers())

    try:
        using_cosmos = _get_users() is not None
        user_store = "Cosmos DB" if using_cosmos else "in-memory (dev)"
        users_ok = True
    except UserStoreUnavailable:
        # Configured but unreachable: accounts cannot be created or checked.
        using_cosmos = True
        user_store = "Cosmos DB (unavailable)"
        users_ok = False
    return _json_response({
        "status": "healthy" if users_ok else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cache": get_cache_status(),
        "security": {
            # Reported from live configuration so the dashboard displays what
            # is actually in effect instead of a hardcoded claim.
            "password_hashing": "bcrypt (12 rounds)",
            "user_store": user_store,
            "encryption_at_rest": (
                "AES-256 (Cosmos DB, service-managed)" if using_cosmos
                else "not applicable -- no database configured"
            ),
            "token": f"JWT HS256, {os.environ.get('JWT_EXPIRY_HOURS', '24')}h",
        },
        "version": "3.0.0",
        "phase": "Phase 3 - Improved Cloud Dashboard",
    })


# ===================================================================
# AUTH: Throttling shared by registration and login
# ===================================================================
#
# Both endpoints are anonymous and both run bcrypt, so each request costs
# real CPU and each login is a password guess.  Limits are per worker
# process (see ratelimit.py for what that does and does not cover).

# Any login attempt from one address.
_login_ip_limiter = SlidingWindowLimiter(limit=20, window=300)
# Account creations from one address.
_register_ip_limiter = SlidingWindowLimiter(limit=10, window=3600)
#
# Password attempts are limited per (account, client address) pair rather
# than per account alone.  A per-account lock lets anyone who knows an email
# lock its owner out; keyed on the pair, one source can only exhaust its own
# allowance.  Guessing spread over many addresses is caught by a wider
# per-account cap, which applies only to addresses that have never signed in
# to that account, so the owner's usual address keeps working while
# strangers are refused.
#
# Attempts are *reserved* before bcrypt runs and refunded on success, so the
# check and the count are one atomic step: concurrent requests cannot all
# pass the check before any of them is counted.
_login_pair_limiter = SlidingWindowLimiter(limit=5, window=900)
_login_account_limiter = SlidingWindowLimiter(limit=50, window=900)
# (account, address) pairs that completed a login recently.
_trusted_login_sources = RecentKeys(ttl=30 * 24 * 3600)

_STORE_DOWN_MSG = "Accounts are temporarily unavailable. Please try again in a moment."


def _too_many(retry_after: float) -> func.HttpResponse:
    seconds = max(1, int(retry_after + 0.999))
    return func.HttpResponse(
        body=json.dumps({"error": "Too many attempts. Please try again later.",
                         "retry_after": seconds}),
        status_code=429,
        mimetype="application/json",
        headers={**_cors_headers(), "Retry-After": str(seconds)},
    )


# A 12-round bcrypt hash of a random value nobody knows, made once at import
# (one bcrypt round trip of cold start) rather than on first use, so that
# the first unknown-email login on an instance is not slower than the rest.
_DUMMY_HASH = hash_password(secrets.token_hex(16))


def _burn_password_check(password: str) -> None:
    """Spend one bcrypt verification on nothing.

    Run when there is no hash to check, so an unknown email takes as long to
    reject as a wrong password and response time does not reveal which
    addresses have accounts.
    """
    verify_password(password, _DUMMY_HASH)


# ===================================================================
# AUTH: Registration
# ===================================================================

@app.route(route="auth/register", methods=["POST", "OPTIONS"], auth_level=func.AuthLevel.ANONYMOUS)
def register(req: func.HttpRequest) -> func.HttpResponse:
    """Register a new user with email, password, and name.

    Password is hashed with bcrypt (12 rounds) before storage.
    """
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=204, headers=_cors_headers())

    wait = _register_ip_limiter.hit(client_ip(req.headers))
    if wait:
        return _too_many(wait)

    try:
        body = req.get_json()
    except ValueError:
        return _error("Invalid JSON body")

    ok, msg = validate_registration(body)
    if not ok:
        return _error(msg)

    email = body["email"].strip().lower()
    name = body["name"].strip()
    password = body["password"]

    # Fast path for the common case; the create below is what actually
    # guarantees one account per email.
    try:
        if _find_user_by_email(email):
            return _error("An account with this email already exists.", 409)
    except UserStoreUnavailable:
        return _error(_STORE_DOWN_MSG, 503)

    user = User(
        id=User.id_for_email(email),
        email=email,
        name=name,
        password_hash=hash_password(password),
        provider="local",
        last_login=datetime.now(timezone.utc).isoformat(),
    )
    outcome = _create_user(user)
    if outcome == USER_EXISTS:
        return _error("An account with this email already exists.", 409)
    if outcome != USER_CREATED:
        return _error(
            "Your account could not be saved. Please try again in a moment.",
            503,
        )

    token = create_token(user.id, user.email, user.name)
    return _json_response({
        "status": "ok",
        "message": "Registration successful",
        "token": token,
        "user": user.to_public(),
    }, 201)


# ===================================================================
# AUTH: Login
# ===================================================================

@app.route(route="auth/login", methods=["POST", "OPTIONS"], auth_level=func.AuthLevel.ANONYMOUS)
def login(req: func.HttpRequest) -> func.HttpResponse:
    """Login with email and password. Returns JWT token (24h expiry)."""
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=204, headers=_cors_headers())

    ip = client_ip(req.headers)
    wait = _login_ip_limiter.hit(ip)
    if wait:
        return _too_many(wait)

    try:
        body = req.get_json()
    except ValueError:
        return _error("Invalid JSON body")

    ok, msg = validate_login(body)
    if not ok:
        return _error(msg)

    email = body["email"].strip().lower()
    password = body["password"]
    source = f"{email}|{ip}"

    # Reserve the attempt before bcrypt runs; a failed attempt keeps its
    # reservation, a successful one is refunded below.
    wait, pair_stamp = _login_pair_limiter.reserve(source)
    if wait:
        return _too_many(wait)
    account_stamp = None
    if not _trusted_login_sources.seen(source):
        wait, account_stamp = _login_account_limiter.reserve(email)
        if wait:
            _login_pair_limiter.release(source, pair_stamp)
            return _too_many(wait)

    def refund():
        _login_pair_limiter.release(source, pair_stamp)
        _login_account_limiter.release(email, account_stamp)

    try:
        user = _find_user_by_email(email)
    except UserStoreUnavailable:
        refund()    # no password was checked
        return _error(_STORE_DOWN_MSG, 503)

    if not user or not user.password_hash:
        # No account, or an OAuth-only account with no password to check.
        _burn_password_check(password)
        return _error("Invalid email or password.", 401)

    if not verify_password(password, user.password_hash):
        return _error("Invalid email or password.", 401)

    refund()
    _login_pair_limiter.reset(source)
    _trusted_login_sources.add(source)

    # Update last login (best effort: the password was already verified).
    user.last_login = datetime.now(timezone.utc).isoformat()
    _save_user(user)

    token = create_token(user.id, user.email, user.name)
    return _json_response({
        "status": "ok",
        "message": "Login successful",
        "token": token,
        "user": user.to_public(),
    })


# ===================================================================
# AUTH: Get current user
# ===================================================================

@app.route(route="auth/me", methods=["GET", "OPTIONS"], auth_level=func.AuthLevel.ANONYMOUS)
def get_me(req: func.HttpRequest) -> func.HttpResponse:
    """Return current user info from JWT token."""
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=204, headers=_cors_headers())

    claims = get_current_user(req)
    if not claims:
        return _error("Not authenticated. Please log in.", 401)

    return _json_response({
        "status": "ok",
        "user": {
            "id": claims.get("sub", ""),
            "email": claims.get("email", ""),
            "name": claims.get("name", ""),
        },
    })


# ===================================================================
# AUTH: Logout (client-side token invalidation)
# ===================================================================

@app.route(route="auth/logout", methods=["POST", "OPTIONS"], auth_level=func.AuthLevel.ANONYMOUS)
def logout(req: func.HttpRequest) -> func.HttpResponse:
    """Logout endpoint. Token invalidation is handled client-side."""
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=204, headers=_cors_headers())

    return _json_response({
        "status": "ok",
        "message": "Logged out successfully. Please discard your token.",
    })


# ===================================================================
# AUTH: OAuth - Google
# ===================================================================

@app.route(route="auth/oauth/google", methods=["GET", "OPTIONS"], auth_level=func.AuthLevel.ANONYMOUS)
def oauth_google(req: func.HttpRequest) -> func.HttpResponse:
    """Redirect to Google OAuth consent screen."""
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=204, headers=_cors_headers())

    state = create_state()
    return func.HttpResponse(
        status_code=302,
        headers={
            **_cors_headers(),
            "Location": google_auth_url(state),
            "Set-Cookie": state_cookie(state),
        },
    )


@app.route(
    route="auth/oauth/google/callback",
    methods=["GET", "OPTIONS"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def oauth_google_callback(req: func.HttpRequest) -> func.HttpResponse:
    """Handle Google OAuth callback, create or find user, return JWT."""
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=204, headers=_cors_headers())

    if not verify_state_request(req):
        return _oauth_error("oauth_state")

    code = req.params.get("code", "")
    if not code:
        return _oauth_error("oauth_no_code")

    user_info = google_exchange_code(code)
    if not user_info:
        return _oauth_error("oauth_google_failed")

    return _handle_oauth_user(user_info)


# ===================================================================
# AUTH: OAuth - GitHub
# ===================================================================

@app.route(route="auth/oauth/github", methods=["GET", "OPTIONS"], auth_level=func.AuthLevel.ANONYMOUS)
def oauth_github(req: func.HttpRequest) -> func.HttpResponse:
    """Redirect to GitHub OAuth authorization."""
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=204, headers=_cors_headers())

    state = create_state()
    return func.HttpResponse(
        status_code=302,
        headers={
            **_cors_headers(),
            "Location": github_auth_url(state),
            "Set-Cookie": state_cookie(state),
        },
    )


@app.route(
    route="auth/oauth/github/callback",
    methods=["GET", "OPTIONS"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def oauth_github_callback(req: func.HttpRequest) -> func.HttpResponse:
    """Handle GitHub OAuth callback, create or find user, return JWT."""
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=204, headers=_cors_headers())

    if not verify_state_request(req):
        return _oauth_error("oauth_state")

    code = req.params.get("code", "")
    if not code:
        return _oauth_error("oauth_no_code")

    user_info = github_exchange_code(code)
    if not user_info:
        return _oauth_error("oauth_github_failed")

    return _handle_oauth_user(user_info)


def _oauth_redirect(path: str) -> func.HttpResponse:
    """302 back to the frontend. Used for both success and failure.

    An OAuth failure used to return bare JSON at the Function App's hostname,
    which is a dead end: the visitor is off the dashboard's origin with no link
    back. Sending them to login.html with a reason keeps them in the app.
    """
    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:8080").rstrip("/")
    return func.HttpResponse(
        status_code=302,
        headers={**_cors_headers(), "Location": f"{frontend_url}/{path}"},
    )


def _oauth_error(reason: str) -> func.HttpResponse:
    """Redirect to the login page with a machine-readable failure reason."""
    logger.warning("OAuth callback rejected: %s", reason)
    return _oauth_redirect(f"login.html?error={quote(reason)}")


def _handle_oauth_user(info: dict) -> func.HttpResponse:
    """Create or find an OAuth user and return a JWT in a redirect."""
    provider = info["provider"]
    provider_id = info["provider_id"]
    # Normalized the same way registration and login normalize it, so one
    # address maps to one account (and one derived document id).
    email = (info.get("email") or "").strip().lower()
    name = info.get("name", "")

    # Only an email the provider says it verified may claim an existing
    # account; otherwise anyone able to set an unverified address at the
    # provider could take over that account.
    verified_email = bool(email) and bool(info.get("email_verified"))

    def link(account: User) -> bool:
        # Record the provider too, not just its subject id: the
        # provider+provider_id lookup is how this account is found next
        # time, and it only matches when both agree.
        account.provider = provider
        account.provider_id = provider_id
        account.last_login = datetime.now(timezone.utc).isoformat()
        # Without the saved provider fields the next sign-in cannot find
        # this account by provider, so the link is not done until it is
        # stored.
        return _save_user(account)

    try:
        user = _find_user_by_provider(provider, provider_id)
        if not user and verified_email:
            user = _find_user_by_email(email)
            if user and not link(user):
                return _oauth_error("account_not_saved")

        if not user:
            # An address the provider would not vouch for must not become
            # this account's identity either.  Users are keyed by email, so
            # reusing an unverified address that already belongs to someone
            # would overwrite their account -- clearing its password hash and
            # locking them out -- which is the same takeover refused above.
            address = (email if verified_email
                       else f"{provider}_{provider_id}@oauth.local")
            candidate = User(
                id=User.id_for_email(address),
                email=address,
                name=name or "OAuth User",
                provider=provider,
                provider_id=provider_id,
                last_login=datetime.now(timezone.utc).isoformat(),
            )
            outcome = _create_user(candidate)
            if outcome == USER_CREATED:
                user = candidate
            elif outcome == USER_EXISTS:
                # A concurrent sign-in or registration created it first.
                # The address is either verified or this provider identity's
                # own synthetic one, so the winner may be used.
                user = _find_user_by_email(address)
                if user is None:
                    return _oauth_error("account_not_saved")
                if verified_email and not link(user):
                    return _oauth_error("account_not_saved")
            else:
                return _oauth_error("account_not_saved")
    except UserStoreUnavailable:
        return _oauth_error("account_not_saved")

    token = create_token(user.id, user.email, user.name)
    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:8080")
    # The token goes in the fragment, which browsers do not send to the server
    # and do not record in referrer headers or access logs.
    redirect_url = f"{frontend_url}/index.html#token={token}"
    return func.HttpResponse(
        status_code=302,
        headers={
            **_cors_headers(),
            "Location": redirect_url,
            # The flow is over; the state cookie must not outlive it.
            "Set-Cookie": clear_state_cookie(),
        },
    )
