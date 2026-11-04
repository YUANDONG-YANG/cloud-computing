# Project 2: Cloud Dashboard Development

**CPSY 300 -- Cloud Computing**
**Phase 2: Azure Cloud Dashboard for Nutritional Insights**

## Status

**Deployed to Azure on 2026-10-20** (resource group `cpsy300-nutritional-insights-rg`,
region canadacentral, Static Web App in eastus2) with `./deploy.sh`.

- Function App: https://cpsy300-nutrition-api.azurewebsites.net/api/health
- Dashboard: https://salmon-ocean-0ce94150f.4.azurestaticapps.net

Date-stamped screenshots of the live dashboard, API responses, resources and CORS
settings are in `docs/reports/project2-master-overview.html` (section 7, Deployment
Evidence; image files in `docs/screenshots/`).

## Deliverables

The four items the Phase 2 brief asks for, and where each one lives.

| # | Deliverable | Where |
|---|-------------|-------|
| 1 | Deployed Azure Function URL | <https://cpsy300-nutrition-api.azurewebsites.net/api/insights> (also `/api/health`, `/api/recipes`) |
| 2 | Static Web App link | <https://salmon-ocean-0ce94150f.4.azurestaticapps.net> |
| 3 | GitHub repository (frontend + backend) | <https://github.com/YUANDONG-YANG/cloud-computing> -- this `Project2/` folder |
| 4 | Documentation PDF | [`docs/reports/project2-master-overview.pdf`](docs/reports/project2-master-overview.pdf) (36 pages, exported from the HTML report) |

Rubric mapping, deployment evidence (Figures 1-7) and the challenges log are all in
[`docs/reports/project2-master-overview.html`](docs/reports/project2-master-overview.html).

## Overview

This project moves the Nutritional Insights application from Project 1 to Azure
Cloud and adds a web-based dashboard with interactive visualizations. The backend
runs as an Azure Function App (Python v2 programming model, HTTP triggers) that
reads the recipe dataset from a private Azure Blob Storage container; the frontend
is a responsive HTML/CSS/JS dashboard served by Azure Static Web Apps.

## Architecture

```
Browser (dashboard)
    |
    |  HTTPS GET /api/health, /api/insights, /api/recipes
    v
Azure Static Web App  (static hosting for index.html / app.js / styles.css)
    |
    |  cross-origin fetch() to the Function App host
    v
Azure Function App  (Python 3.11, Functions v4, consumption plan)
    |
    |  azure-storage-blob SDK, connection string from app settings
    v
Azure Blob Storage  (private container "datasets")
    |
    datasets/All_Diets.csv  --  7,806 recipes across 5 diet types
```

## Repository Map

Every tracked file in `Project2/`, grouped by role. Nothing here is generated at
build time except `build/`, which is git-ignored and recreated by `deploy.sh`.

```
Project2/
├── README.md                              # This file -- index and entry point
│
├── backend/                               # Azure Function App (deployed unit)
│   ├── function_app.py                    #   v2 programming model, 3 HTTP routes
│   ├── nutrition.py                       #   Cleaning + aggregation, shared with Project 1
│   ├── host.json                          #   Functions host config (route prefix "api")
│   ├── requirements.txt                   #   Runtime dependencies
│   ├── local.settings.json.example        #   Template -- copy to local.settings.json
│   └── .funcignore                        #   Excluded from `func azure functionapp publish`
│
├── frontend/                              # Static Web App payload (deployed unit)
│   ├── index.html                         #   Dashboard page, Tailwind via CDN
│   ├── app.js                             #   Chart.js charts, fetch() integration, paging
│   └── styles.css                         #   Component styles
│
├── tests/                                 # pytest suite (37 tests, run in CI)
│   ├── test_function_app.py               #   HTTP handlers, paging, error paths, secrets
│   ├── test_nutrition.py                  #   Cleaning and aggregation
│   └── test_frontend_demo_data.py         #   Offline fallback matches Project 1 output
│
├── stage1/                                # Stage 1 hand-in -- self-contained local backend
│   ├── README.md                          #   Run instructions + full API contract
│   ├── summary.html                       #   Stage 1 summary for marking (images embedded)
│   ├── function_app.py                    #   4 HTTP routes: health, insights, recipes, clusters
│   ├── nutrition.py                       #   Cleaning + aggregation + correlation matrix
│   ├── clustering.py                      #   k-means written from scratch with NumPy
│   ├── verify_http.py                     #   10 real HTTP checks against a running `func start`
│   ├── data/All_Diets.csv                 #   Local dataset (Stage 3 switches this to Blob)
│   ├── tests/                             #   44 pytest tests
│   └── docs/                              #   verification.txt, api-results.json, http-results.json,
│                                          #   screenshots/ (7 local-run images)
│
├── deploy.sh                              # Azure CLI provisioning + deploy, 7 idempotent steps
├── teardown.sh                            # Deletes the resource group
├── staticwebapp.config.json               # SWA routing + security headers
├── pytest.ini / .flake8                   # Test and lint configuration
├── requirements-dev.txt                   # Test dependencies
│
├── spec/                                  # Course-provided material -- read-only reference
│   ├── phase2-requirements.docx           #   The Phase 2 brief and rubric
│   ├── ui-skeleton.html                   #   Provided dashboard skeleton
│   └── submission-requirements.md         #   Submission instructions for this phase
│
└── docs/
    ├── phase2-analysis.md                 # Requirements analysis (what the brief asks for)
    ├── phase2-documentation.md            # Architecture / services / workflow write-up
    ├── phase2-deployment-walkthrough.html # Step-by-step runbook used for the deployment
    ├── reports/
    │   ├── project2-master-overview.html  #   Master report -- rubric, evidence, challenges
    │   ├── project2-master-overview.pdf   #   Submission PDF, exported from the HTML above
    │   ├── evidence-dashboard-print.pdf   #   Printed live dashboard (5 pages)
    │   └── evidence-api-insights.pdf      #   Printed /api/insights JSON response (5 pages)
    ├── screenshots/                       # All deployment evidence images (16 files)
    │   ├── dashboard-full-page.png        #   Figure 1 -- whole dashboard, live
    │   ├── dashboard-live.png             #   Live dashboard, above the fold
    │   ├── portal-function-app.png        #   Figure 2 -- Function App + the 3 enabled functions
    │   ├── portal-function-app-essentials.png
    │   ├── portal-static-web-app.png      #   Figure 3 -- Static Web App, status Ready
    │   ├── portal-static-web-app-essentials.png
    │   ├── portal-resource-group.png      #   Resource group contents
    │   ├── portal-storage-containers.png  #   Figure 5 -- containers, all Private
    │   ├── portal-storage-container.png   #   datasets container with All_Diets.csv
    │   ├── cli-resource-inventory.png     #   Figure 4 -- az resource list + app settings
    │   ├── cli-cors-and-timing.png        #   Figure 7 -- CORS scope + timed API call
    │   ├── api-insights-browser.png       #   Figure 6 -- /api/insights in the browser
    │   ├── api-insights-response.png      #   /api/insights response body
    │   ├── api-health-browser.png         #   /api/health response
    │   ├── api-health-curl.png            #   /api/health via curl
    │   └── api-recipes-response.png       #   /api/recipes response with paging fields
    └── reviews/                           # Point-in-time audits, kept as a record
        ├── gap-review-2026-10-02.md       #   Pre-deployment gap analysis (historical)
        └── score-review-2026-10-02.md     #   Rubric scoring review (historical)
```

Git-ignored, so not listed above: `backend/local.settings.json` and
`stage1/local.settings.json` (local settings), `stage1/.venv311/` (local virtualenv),
`build/` (the frontend copy `deploy.sh` injects the live API URL into), `__pycache__/`
and `.pytest_cache/`.

### Where to start

| If you want to... | Open |
|---|---|
| Grade the work against the rubric | [`docs/reports/project2-master-overview.html`](docs/reports/project2-master-overview.html), section 7 |
| Read the architecture write-up | [`docs/phase2-documentation.md`](docs/phase2-documentation.md) |
| See the deployment evidence | [`docs/screenshots/`](docs/screenshots/), cited as Figures 1-7 in the master overview |
| Reproduce the deployment | [`deploy.sh`](deploy.sh), narrated in [`docs/phase2-deployment-walkthrough.html`](docs/phase2-deployment-walkthrough.html) |
| Read the API code | [`backend/function_app.py`](backend/function_app.py) |
| Review the Stage 1 local backend hand-in | [`stage1/README.md`](stage1/README.md), summary in [`stage1/summary.html`](stage1/summary.html) |
| Read the dashboard code | [`frontend/app.js`](frontend/app.js) |

### File naming conventions

- **Code** keeps the conventions of its language: `snake_case.py`, `camelCase` inside
  JavaScript, lowercase `index.html` / `app.js` / `styles.css`.
- **Documents, reports and images** are lowercase `kebab-case` with no spaces, so they
  stay safe in URLs, shell commands and `swa deploy` uploads.
- **Screenshots** are named for what they show, prefixed by where the shot was taken:
  `portal-*` (Azure Portal), `cli-*` (Azure CLI / Cloud Shell), `api-*` (an API
  response), `dashboard-*` (the deployed dashboard). There are deliberately no numeric
  prefixes: figure numbers belong to the documents that cite the images, so reordering
  a report never forces a file rename.
- **Point-in-time documents** carry an ISO date suffix, e.g. `gap-review-2026-10-02.md`.
- One directory, one job: `backend/` and `frontend/` are the two deployed units,
  `spec/` is read-only course material, `tests/` mirrors `backend/`, and everything the
  team wrote about the project lives under `docs/`.

## API Endpoints

The host route prefix is `api` (`backend/host.json`), so every route is served under
`https://<function-app>.azurewebsites.net/api/...`. All endpoints are `GET`, use
anonymous auth, and return `application/json`.

| Endpoint | Query parameters | Description |
|----------|------------------|-------------|
| `/api/health` | -- | Liveness probe. Makes **no storage call**, so it stays fast and cheap; reports `dataset_cached` so you can tell whether a warm copy of the dataset is in memory. |
| `/api/insights` | -- | Aggregates: average macros per diet, top 5 highest-protein recipes per diet, most common cuisine per diet, total protein per diet, and summary statistics. |
| `/api/recipes` | `diet_type`, `page`, `limit` | One page of recipe rows. `diet_type` filters to a single diet (omitted or `all` returns every diet); `page` is 1-based and defaults to `1`; `limit` defaults to `50` and is hard-capped at `500`. |

Every data response carries a `metadata` block with
`execution_time_seconds`, `source`, `dataset` and `dataset_from_cache`.
Invalid pagination parameters return `400`; an unknown `diet_type` returns `404`.
Internal exception text is logged, never returned.

The sample payloads below are abbreviated for readability. The field names and the
dataset figures are real (verified against `All_Diets.csv`), and the
`execution_time_seconds` values are representative of the deployed app: the live API
reported 0.042 s warm and 0.51 s on a cold start on 2026-10-20
(`docs/screenshots/cli-cors-and-timing.png`).

### `GET /api/health`

```json
{
  "status": "healthy",
  "service": "nutritional-insights-api",
  "version": "2.0.0",
  "dataset_cached": true
}
```

### `GET /api/insights`

```json
{
  "average_macros": [
    { "Diet_type": "dash", "Protein(g)": 69.28, "Carbs(g)": 160.54, "Fat(g)": 101.15 }
  ],
  "top_recipes": [
    {
      "Diet_type": "dash",
      "Recipe_name": "Salmon Mousse",
      "Cuisine_type": "nordic",
      "Protein(g)": 1239.47,
      "Carbs(g)": 22.4,
      "Fat(g)": 983.36
    }
  ],
  "common_cuisines": [
    { "Diet_type": "dash", "Cuisine_type": "american", "count": 639 }
  ],
  "total_protein_by_diet": [
    { "Diet_type": "dash", "Total_Protein(g)": 120897.57 }
  ],
  "summary": {
    "total_recipes": 7806,
    "diet_types": ["dash", "keto", "mediterranean", "paleo", "vegan"],
    "diet_counts": {
      "mediterranean": 1753,
      "dash": 1745,
      "vegan": 1522,
      "keto": 1512,
      "paleo": 1274
    },
    "highest_mean_protein_diet": "keto",
    "highest_mean_protein_g": 101.27,
    "highest_total_protein_diet": "mediterranean",
    "highest_total_protein_g": 177249.89
  },
  "metadata": {
    "execution_time_seconds": 0.412,
    "source": "Azure Blob Storage",
    "dataset": "All_Diets.csv",
    "dataset_from_cache": true
  }
}
```

(`average_macros`, `top_recipes`, `common_cuisines` and `total_protein_by_diet` are
abbreviated above to one row each; the real payload holds one row per diet, five rows
per diet for `top_recipes`, and one row per cuisine tie for `common_cuisines`.)

### `GET /api/recipes?diet_type=keto&page=1&limit=50`

```json
{
  "recipes": [
    {
      "Diet_type": "keto",
      "Recipe_name": "Keto Fat Bombs",
      "Cuisine_type": "american",
      "Protein(g)": 49.19,
      "Carbs(g)": 79.78,
      "Fat(g)": 264.4
    }
  ],
  "count": 50,
  "total": 1512,
  "page": 1,
  "limit": 50,
  "total_pages": 31,
  "diet_type_filter": "keto",
  "metadata": {
    "execution_time_seconds": 0.058,
    "source": "Azure Blob Storage",
    "dataset": "All_Diets.csv",
    "dataset_from_cache": true
  }
}
```

`count` is the number of rows in this page, `total` the number of rows matching the
filter. A `page` beyond `total_pages` is clamped to the last page.

## Dashboard Features

- **Four visualizations**
  - **Grouped bar chart** -- average protein, carbs and fat per diet (Chart.js).
  - **Doughnut chart** -- recipe distribution across the five diets (Chart.js).
  - **Heatmap** -- colour-coded macronutrient intensity, rendered as a CSS grid
    rather than a chart library.
  - **Scatter plot** -- average protein against average carbs per diet (Chart.js).
- **Interaction controls** -- a diet-type dropdown, a **Refresh Data** button, and
  the pagination controls under the recipe table. That is the complete set; there is
  no free-text search box and no clustering control.
- **Execution-time badge** -- shows the `execution_time_seconds` reported by
  `/api/insights`.
- **Summary stat tiles** -- total recipes, diet-type count, and the highest mean and
  total protein diets.
- **Top 5 Highest-Protein Recipes per Diet** table -- 25 rows when no diet filter is
  applied. **This table is not paginated**; it scrolls.
- **Most Common Cuisines** table -- the most frequent cuisine per diet, ties preserved.
- **Recipe Data table with server-side pagination** -- pagination applies to this
  table only, and it is genuinely server-side: each page click issues a fresh
  `/api/recipes?page=N&limit=50` request rather than slicing a payload already held
  in the browser. This was a deliberate change; the full unpaged payload for all
  7,806 rows is about **1.21 MB**, which is too much to ship on every load.

### Offline fallback (not a demo mode)

When the Azure Function cannot be reached, the dashboard does **not** quietly show
invented numbers:

- A **prominent offline banner** appears at the top of the content area, stating that
  the page is showing Project 1 batch results rather than live cloud data, and naming
  the endpoint that could not be reached. The header status pill also switches to
  "Offline - fallback data".
- The figures rendered in that state are the **real Project 1 batch output**,
  committed under `Project1/docs/results/` (`average_macros.csv`,
  `total_protein.csv`, `common_cuisines.csv`, `top5_protein_recipes.csv`). They are
  genuine output of the Project 1 pipeline over `All_Diets.csv` -- **not invented
  placeholder values**.
- Live and fallback data are **never mixed**. The whole dashboard is either fully
  live or fully offline; a failure in either `/api/insights` or `/api/recipes`
  switches the entire view to the fallback.

## Configuration

The dashboard reads its API base URL from `window.NUTRITIONAL_API_URL`, which
`frontend/index.html` sets from the placeholder `__FUNCTION_API_URL__`.

- **Deployed:** `deploy.sh` copies `frontend/` into a throwaway `build/` directory
  and replaces `__FUNCTION_API_URL__` there with the real Function App URL
  (`https://<function-app>.azurewebsites.net/api`). Only `build/` is deployed, so the
  committed sources keep the placeholder and the repository stays clean. The script
  verifies the substitution actually happened and aborts if it did not. `build/` is
  git-ignored and recreated from scratch on every run.
- **Local:** either edit `index.html` and set `window.NUTRITIONAL_API_URL` to
  `http://localhost:7071/api`, or leave the placeholder in place. An unreplaced
  placeholder is detected in `index.html` and deleted, so the dashboard falls back to
  the same-origin `/api` base path -- which is what you want when the page and the
  Function are served from the same host.

Backend configuration comes entirely from app settings / environment variables:

| Setting | Default | Purpose |
|---------|---------|---------|
| `AZURE_STORAGE_CONNECTION_STRING` | falls back to `AzureWebJobsStorage`, then `UseDevelopmentStorage=true` | Blob Storage connection |
| `BLOB_CONTAINER_NAME` | `datasets` | Container holding the dataset |
| `BLOB_NAME` | `All_Diets.csv` | Dataset blob name |

### CORS

**CORS is handled only at the Function App host level**, and `deploy.sh` scopes it to
the Static Web App origin (`az functionapp cors add --allowed-origins
https://<swa-hostname>`); any leftover `*` entry from an earlier run is removed first.

**The function code deliberately emits no `Access-Control-Allow-*` headers.** This is
a design decision, not an omission: when host-level CORS is enabled *and* the handler
writes its own CORS headers, the response carries duplicate
`Access-Control-Allow-Origin` headers, which browsers reject outright. Exactly one
layer must own CORS, and here that layer is the host configuration -- so it can be
scoped at deploy time without a code change.

### Dataset caching

`_load_dataset()` caches the cleaned pandas DataFrame in module memory **keyed by the
blob's ETag**. Every request makes one cheap blob-properties call to read the current
ETag; the CSV is re-downloaded and re-cleaned only when that ETag has changed, so
re-uploading the dataset is picked up automatically without a restart. The cache is
guarded by a lock because a worker serves requests concurrently. Each response's
`metadata.dataset_from_cache` tells you which path the request took, and
`/api/health`'s `dataset_cached` tells you whether any warm copy exists.

### Secrets

- `backend/local.settings.json` is **git-ignored and must never be committed**. Copy
  `backend/local.settings.json.example` and fill in your own values locally.
- Never commit connection strings, storage keys or publish profiles. Use Function App
  settings in Azure and repository secrets in CI.
- `deploy.sh` writes the storage connection string straight into the Function App
  settings and **never prints it** -- so it cannot leak into terminal scrollback,
  screenshots or a screen recording. The summary at the end of the script shows the
  `az` command to retrieve it on demand instead.

## Local Development

### Prerequisites

- Python 3.11 (matching the deployed runtime)
- Azure Functions Core Tools v4 (`npm install -g azure-functions-core-tools@4`)
- Azure CLI (for deployment)
- Azure Static Web Apps CLI (`npm install -g @azure/static-web-apps-cli`), for the
  frontend deployment step

### Run the Backend Locally

```bash
cd backend
cp local.settings.json.example local.settings.json   # then fill in your values
pip install -r requirements.txt
func start
```

The API is then available at `http://localhost:7071/api/`.

### Run the Frontend Locally

Open `frontend/index.html` in a browser. If the backend is not running, the dashboard
shows the offline banner and renders the committed Project 1 results.

To point the page at the local backend, set the API URL in `index.html` before
`app.js` loads:

```html
<script>window.NUTRITIONAL_API_URL = "http://localhost:7071/api";</script>
```

Leaving the `__FUNCTION_API_URL__` placeholder in place instead makes the page use
the same-origin `/api` path.

### Using Azurite for Local Blob Storage

```bash
# Install and start Azurite
npm install -g azurite
azurite --silent --location ./azurite-data

# Create the container and upload the dataset
az storage container create --name datasets --connection-string "UseDevelopmentStorage=true"
az storage blob upload --container-name datasets --file ../Project1/data/All_Diets.csv \
    --name All_Diets.csv --connection-string "UseDevelopmentStorage=true"
```

## Testing

The backend test suite lives under `Project2/tests/`. From the `Project2` directory:

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

## Deploy to Azure

```bash
az login
chmod +x deploy.sh
./deploy.sh
```

`deploy.sh` is idempotent -- re-running it updates the existing resources rather than
creating duplicates -- and it runs relative to its own directory, so the dataset path
resolves regardless of where you invoke it from. The seven steps are:

1. **Resource group** -- create `cpsy300-nutritional-insights-rg` in `canadacentral`.
2. **Storage account + dataset upload** -- create a `StorageV2` / `Standard_LRS`
   account named `cpsy300nutrition<random-hex>` (names are globally unique, so an
   existing matching account in the group is reused on a re-run) with
   `--min-tls-version TLS1_2` and `--allow-blob-public-access false`; create the
   **private** container `datasets`; upload `All_Diets.csv` into it.
3. **Function App + app settings** -- create `cpsy300-nutrition-api` on a Linux
   consumption plan, Python **3.11**, Functions v4; set
   `AZURE_STORAGE_CONNECTION_STRING`, `BLOB_CONTAINER_NAME` and `BLOB_NAME`.
4. **Publish the backend** -- `func azure functionapp publish cpsy300-nutrition-api`
   from `backend/`.
5. **Create the Static Web App unlinked** -- create `cpsy300-nutrition-dashboard`
   (Free SKU) with no linked GitHub repository, so no GitHub token is needed, then
   read back its default hostname.
6. **Build and deploy the frontend** -- copy `frontend/` plus
   `staticwebapp.config.json` into a throwaway `build/`, inject the live Function URL
   in place of `__FUNCTION_API_URL__`, verify the substitution, then
   `swa deploy build --deployment-token <token> --env production` using a deployment
   token read from `az staticwebapp secrets list`.
7. **Scope CORS and smoke-test** -- remove any wildcard origin, allow only the
   dashboard origin, then `curl` `/api/health`, `/api/insights` and
   `/api/recipes?page=1&limit=5`, reporting OK/FAILED for each. The first call pays
   the cold start, hence the generous timeout.

Notes:

- **Region split is intentional.** Azure Static Web Apps is available only in a
  handful of regions and `canadacentral` is not one of them, so the script creates
  the Static Web App in `eastus2` (`SWA_LOCATION`) while every other resource lives
  in `canadacentral` (`LOCATION`).
- **`swa` is required for step 6.** Install it with
  `npm install -g @azure/static-web-apps-cli`. If it is missing, the script warns,
  skips the frontend deployment, and prints the exact `swa deploy` command to run
  manually -- the rest of the deployment still completes.
- Every name, region and runtime version above can be overridden by environment
  variable (`RESOURCE_GROUP`, `LOCATION`, `SWA_LOCATION`, `STORAGE_ACCOUNT`,
  `FUNCTION_APP_NAME`, `STATIC_WEB_APP_NAME`, `BLOB_CONTAINER`, `CSV_FILE`,
  `PYTHON_VERSION`).

## Dataset

- **Source**: `All_Diets.csv` -- 7,806 recipes across 5 diet types
- **Diet types and counts**: mediterranean 1,753 (22.5%), dash 1,745 (22.4%),
  vegan 1,522 (19.5%), keto 1,512 (19.4%), paleo 1,274 (16.3%)
- **Columns**: `Diet_type`, `Recipe_name`, `Cuisine_type`, `Protein(g)`, `Carbs(g)`,
  `Fat(g)`

## Key Findings

| Diet | Avg Protein (g) | Avg Carbs (g) | Avg Fat (g) |
|------|-----------------|----------------|-------------|
| Dash | 69.28 | 160.54 | 101.15 |
| Keto | 101.27 | 57.97 | 153.12 |
| Mediterranean | 101.11 | 152.91 | 101.42 |
| Paleo | 88.67 | 129.55 | 135.67 |
| Vegan | 56.16 | 254.00 | 103.30 |

- **Highest mean protein**: Keto (101.27g)
- **Highest total protein**: Mediterranean (177,249.89g)

## Technologies

- **Backend**: Azure Functions (Python v2 model, Python 3.11), Azure Blob Storage,
  pandas, numpy
- **Frontend**: HTML5, Tailwind CSS (CDN), Chart.js (CDN), vanilla JavaScript
- **Deployment**: Azure CLI, Azure Functions Core Tools, Azure Static Web Apps CLI
