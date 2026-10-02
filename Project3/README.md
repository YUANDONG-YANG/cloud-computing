# Project 3 — Phase 3: Improved Cloud Dashboard

CPSY 300 Cloud Computing — Nutritional Insights Application

## Overview

Phase 3 builds on the Phase 2 cloud dashboard with performance optimization
(blob triggers, result caching) and full authentication/security (email/password,
OAuth, encrypted DB, bcrypt password hashing, JWT-gated API and dashboard).

Cosmos DB is the durable cache, not Redis. Azure Cache for Redis has no free
tier (roughly $16/month), and the rubric allows "an external cache (like Redis)
or a database (like Cosmos)", so `deploy.sh` provisions a **serverless** Cosmos
DB account and no Redis at all. Redis remains supported as an optional
read-through layer in front of Cosmos and is skipped entirely unless
`REDIS_HOST` is set.

## Architecture

```
Browser (frontend/)
  |
  |--- login.html        Login / Register / OAuth
  |--- dashboard.html    Protected dashboard (charts, search, pagination)
  |--- index.html        Router (reads the OAuth token from the URL fragment,
  |                      then redirects based on auth state)
  |
  |    All data calls go through authFetch(), which attaches
  |    `Authorization: Bearer <jwt>`.
  v
Azure Functions (backend/)
  |
  |--- Blob Trigger      Fires when raw-data/All_Diets.csv changes
  |--- /api/insights     Cached analytics          — JWT required (401 without)
  |--- /api/recipes      Filter / search / paginate — JWT required (401 without)
  |--- /api/auth/*       Registration, login, me, logout, OAuth (Google/GitHub)
  |--- /api/health       Health check with cache and security status (public)
  |
  v
Azure Services
  |--- Blob Storage      raw-data + clean-data containers; static website
  |--- Cosmos DB         Durable store (serverless, encrypted at rest):
  |                      user accounts + the pre-computed cache
  |--- Redis             OPTIONAL read-through layer; not provisioned
```

### How the cache works

1. Uploading `All_Diets.csv` to the `raw-data` container fires the blob
   trigger, which cleans the data, pre-computes every aggregation, and writes
   the cleaned CSV back to `clean-data`.
2. The pre-computed insights go to Cosmos DB as a single document
   (`insights_cache`).
3. The cleaned recipe records are **chunked across several Cosmos documents**
   (`CHUNK_SIZE = 2000` records each, ids `recipes_chunk_000`, `_001`, …, plus
   a `recipes_meta` document holding the chunk and record counts). A Cosmos
   document may not exceed 2 MB and the full dataset serializes to about
   1.2 MB, so chunking is what makes the dataset readable from *any* function
   instance instead of only the one that happened to handle the blob trigger.
   Stale chunks from a larger previous dataset are deleted before the new
   count is published, so a reader never sees a mixed set.
4. `/api/insights` and `/api/recipes` only ever read. They never recalculate.
   Read order is Redis (if configured) → Cosmos DB → in-process dict.
5. The status pill on the dashboard names the store the response actually came
   from (`Served from Cosmos DB`, `Served from Redis`, `Served from in-process
   cache`), which is the evidence that the result was cached rather than
   recomputed.

If nothing is cached, the endpoints return **503** with an explanatory error
rather than inventing numbers — see `ENABLE_DEMO_FALLBACK` below.

## Local Development

### Prerequisites

- Python 3.11+
- Azure Functions Core Tools v4 (`npm i -g azure-functions-core-tools@4`)
- Docker and Docker Compose (for Azurite)
- Azure CLI (`az`) — used here only to talk to the local Azurite emulator

### What runs locally, and what that proves

With neither `COSMOS_ENDPOINT` nor `REDIS_HOST` set, `cache.py` falls back to
an **in-process Python dict** and users are kept in an in-process dict too.
That is enough for a single `func start` on one machine, because the blob
trigger and the HTTP handlers share one process. It is **not** valid on Azure:
there the trigger and the handlers may run in different processes or on
different instances, so a dict written by the trigger is invisible to the
request that needs it. Treat the local dict as a convenience for UI work, and
set `COSMOS_ENDPOINT`/`COSMOS_KEY` (pointing at the serverless account
`deploy.sh` creates) when you need to exercise the real durable path.

The Cosmos DB emulator is not part of `docker-compose.yml`: the image is
multi-gigabyte, needs its self-signed certificate trusted before the Python SDK
will connect, and frequently fails to start on Windows.

### Quick Start

```bash
# 1. Start Azurite (the only service you need)
docker compose up -d
#    Optional, only if you want to demo the Redis path:
#    docker compose --profile redis up -d

# 2. Create the local settings file (it is gitignored — never commit it)
cd backend
cp local.settings.json.example local.settings.json
#    Then edit it: see "Environment variables" below. For a first run you can
#    delete the COSMOS_*, GITHUB_* and GOOGLE_* entries and keep the rest.

# 3. Install Python dependencies
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 4. Start the Azure Functions host (leave it running)
func start

# 5. In a second terminal: create the blob containers and upload the dataset.
#    This is what fires the blob trigger and fills the cache. Until it runs,
#    /api/insights and /api/recipes answer 503 by design.
export AZURE_STORAGE_CONNECTION_STRING="UseDevelopmentStorage=true"
az storage container create --name raw-data
az storage container create --name clean-data
az storage blob upload \
  --container-name raw-data \
  --file ../Project1/data/All_Diets.csv \
  --name All_Diets.csv --overwrite true

# 6. Confirm the cache filled (watch the func start terminal for the trigger)
curl http://localhost:7071/api/health
#    "recipes_cached" should be true and "recipe_count" 7806.

# 7. Serve the frontend on port 8080 — the origin must match the CORS entry
#    in local.settings.json, and app.js only points at localhost:7071 when the
#    page itself is on localhost.
cd ../frontend
python -m http.server 8080
#    Then visit http://localhost:8080/login.html and register an account.
```

Opening `frontend/login.html` as a `file://` URL does not work: the page would
have a `null` origin, which CORS rejects.

### Environment variables

Set these in `backend/local.settings.json` locally, or as Function App
settings on Azure (`deploy.sh` sets all of the required ones). Copy
`backend/local.settings.json.example` as the starting point —
`local.settings.json` is **gitignored** because it holds account keys and
OAuth client secrets, and a secret pushed to GitHub is a secret that has to be
rotated.

**Required**

| Setting | Notes |
| --- | --- |
| `FUNCTIONS_WORKER_RUNTIME` | `python` |
| `AzureWebJobsStorage` | Blob trigger connection. `UseDevelopmentStorage=true` for Azurite |
| `JWT_SECRET` | Signs JWTs *and* the OAuth `state`. On Azure an unset value is a hard startup failure; locally it falls back to a development key and logs a warning. Generate with `openssl rand -base64 32` |

**Required for the deployed app, optional locally**

| Setting | Notes |
| --- | --- |
| `COSMOS_ENDPOINT`, `COSMOS_KEY` | Without both, `cache.py` logs a warning and the cache will not survive across function instances |
| `COSMOS_DATABASE` | Default `nutritiondb` |
| `COSMOS_USERS_CONTAINER` | Default `users` |
| `COSMOS_CACHE_CONTAINER` | Default `cache` |
| `FRONTEND_URL` | Origin sent in `Access-Control-Allow-Origin`, and the target of the OAuth redirect. Defaults to `*` for CORS and `http://localhost:8080` for the redirect |

**Optional**

| Setting | Default | Notes |
| --- | --- | --- |
| `ENABLE_DEMO_FALLBACK` | `false` | When `true`, `/api/insights` and `/api/recipes` serve hardcoded sample data instead of answering 503. Leave it off: the sample numbers mirror the real result set, so with it on a broken cache is indistinguishable from a working one — which is the one thing Phase 3 has to prove |
| `JWT_EXPIRY_HOURS` | `24` | |
| `BLOB_CONNECTION_STRING` | falls back to `AzureWebJobsStorage` | Used only to write the cleaned CSV |
| `BLOB_CONTAINER_CLEAN` | `clean-data` | Destination for `cleaned_recipes.csv` |
| `REDIS_HOST` | unset | **Unset means Redis is skipped entirely.** Set it only to enable the optional read-through layer |
| `REDIS_PORT` | `6380` | The local container in `docker-compose.yml` listens on `6379` |
| `REDIS_SSL` | `true` | Must be `false` for the local container |
| `REDIS_PASSWORD` | unset | |
| `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `GITHUB_REDIRECT_URI` | unset | GitHub login is simply unavailable without them |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` | unset | Likewise for Google |

`BLOB_CONTAINER_RAW` appears in the example settings and in `deploy.sh` for
documentation, but the trigger path `raw-data/All_Diets.csv` is declared in the
decorator, so changing the setting alone does not move the trigger.

### OAuth locally

Register an OAuth app at the provider and set the callback URL to exactly
`http://localhost:7071/api/auth/oauth/<github|google>/callback`. The callback
verifies a signed, 10-minute `state` value minted by the backend and then
redirects to `FRONTEND_URL/index.html#token=<jwt>` — the token travels in the
URL **fragment**, which browsers do not send to servers and do not record in
referrer headers or access logs. `index.html` reads it, stores it, and cleans
the URL. Without OAuth configured, email/password registration works fine.

## Azure Deployment

```bash
# Log in
az login

# Optional: configure OAuth before deploying, so the app settings are filled in
export GITHUB_CLIENT_ID=...    GITHUB_CLIENT_SECRET=...
export GOOGLE_CLIENT_ID=...    GOOGLE_CLIENT_SECRET=...

# Deploy all resources and both halves of the app
./deploy.sh
```

`deploy.sh` provisions a Resource Group, a Storage Account (blob containers
`raw-data` and `clean-data`, plus the static website), a **serverless** Cosmos
DB account with the `users` and `cache` containers, and a Function App on the
Consumption plan. It then publishes the function code, uploads the frontend to
the static website, adds the frontend origin to the Function App's CORS
allow-list, sets `FRONTEND_URL`, and finally uploads `All_Diets.csv` to
`raw-data` to fire the blob trigger. It generates a random `JWT_SECRET` and
sets `ENABLE_DEMO_FALLBACK=false`.

No Redis is provisioned. Azure Cache for Redis has no free tier, and the code
only uses Redis when `REDIS_HOST` is set.

### Verifying the deployment

```bash
# 1. The cache filled. On the Consumption plan the blob trigger polls, so this
#    can take several minutes after the upload.
curl https://<function-app>.azurewebsites.net/api/health
#    "recipes_cached": true, "recipe_count": 7806

# 2. The API really is gated — this must return 401.
curl -i https://<function-app>.azurewebsites.net/api/insights

# 3. Open the frontend URL, register, and confirm the status pill reads
#    "Served from Cosmos DB".
```

### Tear down when the demo is recorded

```bash
./teardown.sh
```

**Run this as soon as the demo video is recorded.** Azure bills by the hour and
by the request, so a resource group left running over a weekend costs more than
the whole demo did. `teardown.sh` lists the resources, asks you to type the
resource group name to confirm, then deletes the entire group. It is
irreversible: the Cosmos data, the registered users and the uploaded blobs all
go with it. Re-running `deploy.sh` rebuilds the resources but not their
contents.

## Features Implemented

### Performance Optimization
- **Blob Trigger**: an Azure Function fires when `All_Diets.csv` is uploaded or
  modified. Cleaning and aggregation run automatically; results are cached and
  the cleaned CSV is written to the `clean-data` container.
- **Result Caching**: all analytics are pre-computed on file change and stored
  durably in Cosmos DB, with the recipe records chunked across documents to
  stay under the 2 MB document limit. API requests serve cached data and never
  re-compute. Redis can be layered in front by setting `REDIS_HOST`.
- **Honest empty state**: with `ENABLE_DEMO_FALLBACK=false` (the default), an
  empty cache produces a 503 and a visible banner instead of plausible-looking
  sample numbers.

### Data Interaction
- **Diet Type Filter**: dropdown populated from the cached dataset, not a
  hardcoded list
- **Keyword Search**: debounced search across recipe name, cuisine, and diet
- **Pagination**: 20 results per page (max 100) with Previous/Next and page
  numbers

### Authentication & Security
- **Email/Password Auth**: registration and login with server-side validation
  (valid email, 8-character minimum password, name required)
- **OAuth Login**: Google and GitHub OAuth 2.0, with a signed `state` parameter
  and the token returned in the URL fragment. An OAuth identity may only claim
  an existing account when the provider reports the email as verified
- **DB Encryption**: Cosmos DB encrypts all data at rest (AES-256,
  service-managed keys)
- **Password Hashing**: bcrypt with 12 salt rounds — plaintext is never stored
- **API Auth Gate**: `/api/insights` and `/api/recipes` verify the JWT
  themselves and return 401 without a valid one; the dashboard redirect is a
  convenience, not the access control. Tokens are read from the
  `Authorization` header only, never the query string
- **Live security reporting**: the dashboard's security cards are filled from
  `/api/health`, so they report the backend's actual configuration rather than
  a hardcoded claim

## Project Structure

```
Project3/
  backend/
    function_app.py              Main Azure Functions app (all endpoints)
    nutrition.py                 Data cleaning and aggregation (from P1)
    auth.py                      bcrypt, JWT, OAuth state, OAuth helpers
    cache.py                     Cosmos DB cache (+ optional Redis layer)
    models.py                    User model, validation schemas
    host.json                    Azure Functions host configuration
    local.settings.json.example  Template — copy to local.settings.json
    requirements.txt             Python dependencies
  frontend/
    index.html            Router; reads the OAuth token from the fragment
    login.html            Login / Register page with OAuth
    dashboard.html        Protected analytics dashboard
    app.js                Chart rendering, search, pagination, status pill
    auth.js               JWT storage, auth state, authFetch
    styles.css            Custom styles
  docker-compose.yml      Local dev stack (Azurite; optional Redis profile)
  deploy.sh               Azure CLI deployment script
  teardown.sh             Deletes the resource group — run after the demo
  README.md               This file
```

`backend/local.settings.json` is gitignored and is not in the repository.

## Technologies

- **Backend**: Azure Functions (Python v2), Azure Blob Storage, Azure Cosmos DB
  (serverless), optionally Redis
- **Frontend**: HTML5, CSS3, JavaScript, Chart.js
- **Security**: bcrypt, JWT (PyJWT), OAuth 2.0 (Google, GitHub)
- **Data**: pandas, numpy (cleaning and aggregation)
