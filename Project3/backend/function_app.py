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
import time
from datetime import datetime, timezone

import azure.functions as func
import pandas as pd

from nutrition import clean_data, precompute_all, df_to_records
from auth import (
    hash_password, verify_password,
    create_token, get_current_user,
    create_state, verify_state,
    google_auth_url, google_exchange_code,
    github_auth_url, github_exchange_code,
)
from cache import (
    store_insights, get_insights,
    store_recipes, get_recipes,
    get_cache_status,
)
from models import User, validate_registration, validate_login

app = func.FunctionApp()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cosmos DB users container (lazy init)
# ---------------------------------------------------------------------------

_users_container = None


def _get_users():
    """Get or initialize the Cosmos DB users container."""
    global _users_container
    if _users_container is not None:
        return _users_container
    try:
        from azure.cosmos import CosmosClient, PartitionKey
        endpoint = os.environ.get("COSMOS_ENDPOINT", "")
        key = os.environ.get("COSMOS_KEY", "")
        if not endpoint or not key:
            logger.warning("Cosmos DB not configured, using in-memory users")
            return None
        client = CosmosClient(endpoint, credential=key)
        db = client.create_database_if_not_exists(
            os.environ.get("COSMOS_DATABASE", "nutritiondb")
        )
        _users_container = db.create_container_if_not_exists(
            id=os.environ.get("COSMOS_USERS_CONTAINER", "users"),
            partition_key=PartitionKey(path="/partitionKey"),
        )
        return _users_container
    except Exception as exc:
        logger.warning("Cosmos DB users unavailable: %s", exc)
        return None


# In-memory user store for local dev when Cosmos is not available
_memory_users: dict = {}


def _find_user_by_email(email: str):
    """Look up a user by email in Cosmos DB or the memory fallback."""
    container = _get_users()
    if container:
        try:
            items = list(container.query_items(
                query="SELECT * FROM c WHERE c.email = @email",
                parameters=[{"name": "@email", "value": email}],
                partition_key=email,
            ))
            if items:
                return User.from_dict(items[0])
        except Exception as exc:
            logger.warning("User lookup failed: %s", exc)
    return _memory_users.get(email)


def _find_user_by_provider(provider: str, provider_id: str):
    """Look up a user by OAuth provider + provider_id."""
    container = _get_users()
    if container:
        try:
            items = list(container.query_items(
                query="SELECT * FROM c WHERE c.provider = @p AND c.provider_id = @pid",
                parameters=[
                    {"name": "@p", "value": provider},
                    {"name": "@pid", "value": provider_id},
                ],
                enable_cross_partition_query=True,
            ))
            if items:
                return User.from_dict(items[0])
        except Exception as exc:
            logger.warning("OAuth user lookup failed: %s", exc)
    for u in _memory_users.values():
        if u.provider == provider and u.provider_id == provider_id:
            return u
    return None


def _save_user(user: User):
    """Persist a user to Cosmos DB or the memory fallback."""
    container = _get_users()
    if container:
        try:
            container.upsert_item(user.to_dict())
            return
        except Exception as exc:
            logger.warning("User save failed: %s", exc)
    _memory_users[user.email] = user


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
    recipes = get_recipes()
    source = "cache"
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
        {"Diet_type": "keto", "Recipe_name": "Keto Butter Chicken", "Cuisine_type": "indian", "Protein(g)": 42.5, "Carbs(g)": 8.3, "Fat(g)": 28.7},
        {"Diet_type": "keto", "Recipe_name": "Bacon Cheese Burger Bowl", "Cuisine_type": "american", "Protein(g)": 38.2, "Carbs(g)": 5.1, "Fat(g)": 35.4},
        {"Diet_type": "keto", "Recipe_name": "Grilled Salmon with Avocado", "Cuisine_type": "american", "Protein(g)": 45.0, "Carbs(g)": 4.2, "Fat(g)": 32.1},
        {"Diet_type": "paleo", "Recipe_name": "Bone Broth From Nom Nom Paleo", "Cuisine_type": "american", "Protein(g)": 5.22, "Carbs(g)": 1.29, "Fat(g)": 3.2},
        {"Diet_type": "paleo", "Recipe_name": "Paleo Pumpkin Pie", "Cuisine_type": "american", "Protein(g)": 30.91, "Carbs(g)": 302.59, "Fat(g)": 96.76},
        {"Diet_type": "paleo", "Recipe_name": "Strawberry Guacamole", "Cuisine_type": "mexican", "Protein(g)": 9.62, "Carbs(g)": 75.78, "Fat(g)": 59.89},
        {"Diet_type": "vegan", "Recipe_name": "Vegan Black Bean Tacos", "Cuisine_type": "mexican", "Protein(g)": 18.5, "Carbs(g)": 45.2, "Fat(g)": 12.3},
        {"Diet_type": "vegan", "Recipe_name": "Tofu Stir Fry", "Cuisine_type": "chinese", "Protein(g)": 22.1, "Carbs(g)": 28.5, "Fat(g)": 14.6},
        {"Diet_type": "vegan", "Recipe_name": "Chickpea Curry", "Cuisine_type": "indian", "Protein(g)": 15.8, "Carbs(g)": 42.3, "Fat(g)": 18.9},
        {"Diet_type": "dash", "Recipe_name": "Grilled Chicken Salad", "Cuisine_type": "american", "Protein(g)": 35.0, "Carbs(g)": 12.5, "Fat(g)": 8.2},
        {"Diet_type": "dash", "Recipe_name": "Salmon with Quinoa", "Cuisine_type": "american", "Protein(g)": 40.2, "Carbs(g)": 38.1, "Fat(g)": 15.6},
        {"Diet_type": "dash", "Recipe_name": "Turkey Meatball Soup", "Cuisine_type": "italian", "Protein(g)": 28.7, "Carbs(g)": 22.4, "Fat(g)": 11.3},
        {"Diet_type": "mediterranean", "Recipe_name": "Greek Lemon Chicken", "Cuisine_type": "greek", "Protein(g)": 38.5, "Carbs(g)": 15.2, "Fat(g)": 22.1},
        {"Diet_type": "mediterranean", "Recipe_name": "Falafel Wrap", "Cuisine_type": "middle eastern", "Protein(g)": 18.9, "Carbs(g)": 42.5, "Fat(g)": 16.8},
        {"Diet_type": "mediterranean", "Recipe_name": "Grilled Sea Bass", "Cuisine_type": "greek", "Protein(g)": 44.2, "Carbs(g)": 5.8, "Fat(g)": 18.5},
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

    using_cosmos = _get_users() is not None
    return _json_response({
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cache": get_cache_status(),
        "security": {
            # Reported from live configuration so the dashboard displays what
            # is actually in effect instead of a hardcoded claim.
            "password_hashing": "bcrypt (12 rounds)",
            "user_store": "Cosmos DB" if using_cosmos else "in-memory (dev)",
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
# AUTH: Registration
# ===================================================================

@app.route(route="auth/register", methods=["POST", "OPTIONS"], auth_level=func.AuthLevel.ANONYMOUS)
def register(req: func.HttpRequest) -> func.HttpResponse:
    """Register a new user with email, password, and name.

    Password is hashed with bcrypt (12 rounds) before storage.
    """
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=204, headers=_cors_headers())

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

    # Check if user already exists
    existing = _find_user_by_email(email)
    if existing:
        return _error("An account with this email already exists.", 409)

    # Create user with bcrypt-hashed password
    user = User(
        email=email,
        name=name,
        password_hash=hash_password(password),
        provider="local",
        last_login=datetime.now(timezone.utc).isoformat(),
    )
    _save_user(user)

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

    try:
        body = req.get_json()
    except ValueError:
        return _error("Invalid JSON body")

    ok, msg = validate_login(body)
    if not ok:
        return _error(msg)

    email = body["email"].strip().lower()
    password = body["password"]

    user = _find_user_by_email(email)
    if not user:
        return _error("Invalid email or password.", 401)

    if not verify_password(password, user.password_hash):
        return _error("Invalid email or password.", 401)

    # Update last login
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

    url = google_auth_url(create_state())
    return func.HttpResponse(
        status_code=302,
        headers={**_cors_headers(), "Location": url},
    )


@app.route(route="auth/oauth/google/callback", methods=["GET", "OPTIONS"], auth_level=func.AuthLevel.ANONYMOUS)
def oauth_google_callback(req: func.HttpRequest) -> func.HttpResponse:
    """Handle Google OAuth callback, create or find user, return JWT."""
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=204, headers=_cors_headers())

    if not verify_state(req.params.get("state", "")):
        return _error("Invalid or expired OAuth state", 400)

    code = req.params.get("code", "")
    if not code:
        return _error("Missing authorization code", 400)

    user_info = google_exchange_code(code)
    if not user_info:
        return _error("Google authentication failed", 401)

    return _handle_oauth_user(user_info)


# ===================================================================
# AUTH: OAuth - GitHub
# ===================================================================

@app.route(route="auth/oauth/github", methods=["GET", "OPTIONS"], auth_level=func.AuthLevel.ANONYMOUS)
def oauth_github(req: func.HttpRequest) -> func.HttpResponse:
    """Redirect to GitHub OAuth authorization."""
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=204, headers=_cors_headers())

    url = github_auth_url(create_state())
    return func.HttpResponse(
        status_code=302,
        headers={**_cors_headers(), "Location": url},
    )


@app.route(route="auth/oauth/github/callback", methods=["GET", "OPTIONS"], auth_level=func.AuthLevel.ANONYMOUS)
def oauth_github_callback(req: func.HttpRequest) -> func.HttpResponse:
    """Handle GitHub OAuth callback, create or find user, return JWT."""
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=204, headers=_cors_headers())

    if not verify_state(req.params.get("state", "")):
        return _error("Invalid or expired OAuth state", 400)

    code = req.params.get("code", "")
    if not code:
        return _error("Missing authorization code", 400)

    user_info = github_exchange_code(code)
    if not user_info:
        return _error("GitHub authentication failed", 401)

    return _handle_oauth_user(user_info)


def _handle_oauth_user(info: dict) -> func.HttpResponse:
    """Create or find an OAuth user and return a JWT in a redirect."""
    provider = info["provider"]
    provider_id = info["provider_id"]
    email = info.get("email", "")
    name = info.get("name", "")

    # Check if user exists by provider + provider_id
    user = _find_user_by_provider(provider, provider_id)

    # Only an email the provider says it verified may claim an existing
    # account; otherwise anyone able to set an unverified address at the
    # provider could take over that account.
    if not user and email and info.get("email_verified"):
        user = _find_user_by_email(email)
        if user:
            user.provider_id = provider_id
            user.last_login = datetime.now(timezone.utc).isoformat()
            _save_user(user)

    if not user:
        # Create new user
        user = User(
            email=email or f"{provider}_{provider_id}@oauth.local",
            name=name or "OAuth User",
            provider=provider,
            provider_id=provider_id,
            last_login=datetime.now(timezone.utc).isoformat(),
        )
        _save_user(user)

    token = create_token(user.id, user.email, user.name)
    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:8080")
    # The token goes in the fragment, which browsers do not send to the server
    # and do not record in referrer headers or access logs.
    redirect_url = f"{frontend_url}/index.html#token={token}"
    return func.HttpResponse(
        status_code=302,
        headers={**_cors_headers(), "Location": redirect_url},
    )
