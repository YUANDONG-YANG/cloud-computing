# Project 2: Cloud Dashboard Development

**CPSY 300 -- Cloud Computing**
**Phase 2: Azure Cloud Dashboard for Nutritional Insights**

## Status

**The Azure resources have not been provisioned yet.** There are therefore **no live
URLs and no portal screenshots** in this repository, and nothing here should be read
as deployment evidence.

What *is* done: the backend Function app, the dashboard frontend, the deployment
script and the test suite are complete and consistent with each other. Deployment is
a single `./deploy.sh` run away for anyone with an Azure subscription (see
[Deploy to Azure](#deploy-to-azure)). The screenshots required by the course are
listed as pending placeholders in `docs/Phase2-Documentation.md`.

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

## Project Structure

```
Project2/
  backend/
    function_app.py                # Azure Functions v2 app (3 HTTP endpoints)
    nutrition.py                   # Cleaning + aggregation, shared with Project 1
    host.json                      # Functions host config (route prefix "api")
    requirements.txt               # Runtime dependencies
    local.settings.json.example    # Template for local settings -- copy and fill in
    local.settings.json            # Local secrets; git-ignored, never committed
    .funcignore                    # Files excluded from `func azure functionapp publish`
  frontend/
    index.html                     # Dashboard page (Tailwind CSS via CDN)
    app.js                         # Chart.js visualizations and API integration
    styles.css                     # Custom component styles
  tests/                           # pytest suite for the backend
  docs/
    Phase2-Analysis.md             # Requirements analysis
    Phase2-Documentation.md        # Source for the required Documentation PDF
    reports/                       # Generated HTML overview report
  review/                          # Independent audits of this project
  staticwebapp.config.json         # Static Web App routing / headers config
  deploy.sh                        # Azure CLI deployment script (7 steps)
  requirements-dev.txt             # Test dependencies
  pytest.ini                       # pytest configuration
  .flake8                          # Lint configuration
  UI-for-project2.html             # Provided UI skeleton (reference only)
  README.md                        # This file
```

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

In the sample payloads below, the field names and the dataset figures are real
(verified against `All_Diets.csv`), but the `execution_time_seconds` values are
illustrative placeholders -- nothing has been deployed yet, so no measured timings
exist.

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

1. **Resource group** -- create `cpsy300-nutritional-insights-rg` in `eastus`.
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
  handful of regions and `eastus` is not one of them, so the script creates the
  Static Web App in `eastus2` (`SWA_LOCATION`) while every other resource lives in
  `eastus` (`LOCATION`).
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
