# Stage 1 — Local Backend Delivery

This is Person 1's working folder from `../division.md`. It builds on the existing
`../backend/` and its tests, and adds local CSV loading, text search, a correlation
matrix and a k-means written from scratch with NumPy. The original deployment folder
is untouched. This folder runs on its own and carries the full
`data/All_Diets.csv` (from Project 1).

- Summary for marking: [summary.html](summary.html) — offline, prints to PDF from the browser.
- In-process API results: [docs/api-results.json](docs/api-results.json).
- Real HTTP results: [docs/http-results.json](docs/http-results.json).
- Test and verification record: [docs/verification.txt](docs/verification.txt).
- Run screenshots: [docs/screenshots/](docs/screenshots/), 7 images.

## Files and Responsibilities

| File | Purpose |
|---|---|
| function_app.py | Azure Functions v2 HTTP entry point, 4 GET routes |
| nutrition.py | Text cleaning, missing-value imputation and the aggregations |
| clustering.py | k-means written from scratch with NumPy, fixed random seed |
| data/All_Diets.csv | The full local dataset, 7,806 recipes |
| tests/ | Cleaning, endpoint, edge-case, clustering and local-cache tests |
| host.json / local.settings.json.example | Functions host config and a key-free local settings template |
| verify_http.py | Sends 10 real HTTP requests to a running Functions host and asserts the results |
| requirements*.txt / pytest.ini / .flake8 | Dependency, test and lint configuration |

## Running Locally

Run these from `Project2/stage1` on Python 3.11, the version the team's project already
uses. The sequence below was verified on Python 3.11.18 with Azure Functions Core Tools
4.16.0. If Core Tools is not installed yet: `npm i -g azure-functions-core-tools@4`.

```bash
python3.11 -m venv .venv311
source .venv311/bin/activate
python -m pip install -r requirements-dev.txt
cp local.settings.json.example local.settings.json
python -m pytest -q
python -m flake8 . --exclude=.venv,.venv311
func start --port 7071
# once the host is up, in a second terminal:
python verify_http.py
```

Stage 1 only reads the local CSV, so it needs no Azure account, Blob key or Azurite.
`DATASET_PATH` points the loader at a different CSV; a relative path resolves against the
working directory, so an absolute path is safer. The default is `data/All_Diets.csv` in
this folder. The cache is keyed on file path, modification time and size.
Local CORS allows `http://localhost:5500` and `http://127.0.0.1:5500` for the front end.

## API Contract

Base URL `http://localhost:7071/api`. Every route is GET and returns `application/json`.
The `metadata` block on each data endpoint carries the execution time in seconds, the data
source and whether the dataset came from cache. Failures return `{"error": "..."}`;
internal exception text never reaches the HTTP response.

| Endpoint | Parameters | Returns |
|---|---|---|
| /health | none | Service status; does not read the CSV |
| /insights | none | average_macros, correlation, summary.diet_counts, top_recipes, common_cuisines, total_protein_by_diet, metadata |
| /recipes | diet_type, search, page, limit | recipes, count, total, page, limit, total_pages, diet_type_filter, search, metadata |
| /clusters | k (default 3, range 1–10) | points, centroids, cluster_counts, features, k, seed, iterations, inertia, standardized, metadata |

- `diet_type` is case-insensitive; omitting it or passing `all` returns every type, and an
  unknown type returns 404.
- `search` is a case-insensitive literal match over recipe name, diet type and cuisine, and
  combines with the diet filter; no match returns an empty list.
- `page` is 1-based and defaults to 1; `limit` defaults to 50 and is capped at 500; invalid
  parameters return 400. A page past the end returns the last page.
- `correlation` is the Pearson correlation matrix over protein, carbs and fat; values that
  are undefined for a constant column come back as null.
- `clusters` uses every recipe and returns every point for the scatter chart. Clusters are
  numbered from 0, and both centroids and points are in grams.
- k-means z-score standardizes first, fixes seed=42 and runs at most 100 iterations; an
  empty cluster keeps its previous centroid. `inertia` is the sum of squared distances in
  the standardized space. The clustering is exploratory grouping, not dietary advice.
- A `k` larger than the number of distinct nutrient vectors returns 400.

## Data Cleaning

Whitespace is stripped from column names and text; diet types and cuisines are lowercased
and missing ones become `unknown`; a missing recipe name becomes `Unnamed recipe`. Nutrient
values are converted to numbers, and negatives, infinities, invalid text and missing values
are filled with the mean of that column's valid values. A missing required column, empty
data, or a column with no valid value at all is rejected.

## Measured JSON Examples

These come from in-process handler calls over the full CSV, not from network requests.
The insights example omits the extra statistics lists and the clusters example shows only
the first two points; the complete payloads are in docs/api-results.json.

### GET /api/health

```json
{
  "status": "healthy",
  "service": "nutritional-insights-api",
  "version": "2.0.0",
  "dataset_cached": false
}
```

### GET /api/insights

```json
{
  "average_macros": [
    {
      "Diet_type": "dash",
      "Protein(g)": 69.28,
      "Carbs(g)": 160.54,
      "Fat(g)": 101.15
    },
    {
      "Diet_type": "keto",
      "Protein(g)": 101.27,
      "Carbs(g)": 57.97,
      "Fat(g)": 153.12
    },
    {
      "Diet_type": "mediterranean",
      "Protein(g)": 101.11,
      "Carbs(g)": 152.91,
      "Fat(g)": 101.42
    },
    {
      "Diet_type": "paleo",
      "Protein(g)": 88.67,
      "Carbs(g)": 129.55,
      "Fat(g)": 135.67
    },
    {
      "Diet_type": "vegan",
      "Protein(g)": 56.16,
      "Carbs(g)": 254.0,
      "Fat(g)": 103.3
    }
  ],
  "correlation": {
    "Protein(g)": {
      "Protein(g)": 1.0,
      "Carbs(g)": 0.155682,
      "Fat(g)": 0.478012
    },
    "Carbs(g)": {
      "Protein(g)": 0.155682,
      "Carbs(g)": 1.0,
      "Fat(g)": 0.269059
    },
    "Fat(g)": {
      "Protein(g)": 0.478012,
      "Carbs(g)": 0.269059,
      "Fat(g)": 1.0
    }
  },
  "summary": {
    "total_recipes": 7806,
    "diet_types": [
      "dash",
      "keto",
      "mediterranean",
      "paleo",
      "vegan"
    ],
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
    "execution_time_seconds": 0.027,
    "source": "Local CSV",
    "dataset": "All_Diets.csv",
    "dataset_from_cache": false
  }
}
```

### GET /api/recipes

```json
{
  "recipes": [
    {
      "Diet_type": "keto",
      "Recipe_name": "Keto Chicken Pot Pie Casserole Recipe",
      "Cuisine_type": "american",
      "Protein(g)": 183.07,
      "Carbs(g)": 66.95,
      "Fat(g)": 330.43
    },
    {
      "Diet_type": "keto",
      "Recipe_name": "Keto Everything Bagel Chicken",
      "Cuisine_type": "american",
      "Protein(g)": 214.84,
      "Carbs(g)": 17.29,
      "Fat(g)": 140.76
    }
  ],
  "count": 2,
  "total": 225,
  "page": 1,
  "limit": 2,
  "total_pages": 113,
  "diet_type_filter": "keto",
  "search": "chicken",
  "metadata": {
    "execution_time_seconds": 0.002,
    "source": "Local CSV",
    "dataset": "All_Diets.csv",
    "dataset_from_cache": true
  }
}
```

### GET /api/clusters

```json
{
  "k": 3,
  "features": [
    "Protein(g)",
    "Carbs(g)",
    "Fat(g)"
  ],
  "standardized": true,
  "seed": 42,
  "iterations": 58,
  "inertia": 12825.275678703805,
  "cluster_counts": {
    "0": 1205,
    "1": 5681,
    "2": 920
  },
  "centroids": [
    {
      "cluster": 0,
      "Protein(g)": 228.09124481327768,
      "Carbs(g)": 119.31101244813274,
      "Fat(g)": 265.9383568464727
    },
    {
      "cluster": 1,
      "Protein(g)": 49.97187114944563,
      "Carbs(g)": 100.62553775743703,
      "Fat(g)": 75.44519978876957
    },
    {
      "cluster": 2,
      "Protein(g)": 98.87491304347826,
      "Carbs(g)": 513.0980000000006,
      "Fat(g)": 181.31163043478267
    }
  ],
  "points": [
    {
      "Recipe_name": "Bone Broth From 'Nom Nom Paleo'",
      "Diet_type": "paleo",
      "Protein(g)": 5.22,
      "Carbs(g)": 1.29,
      "Fat(g)": 3.2,
      "cluster": 1
    },
    {
      "Recipe_name": "Paleo Effect Asian-Glazed Pork Sides, A Sweet & Crispy Appetizer",
      "Diet_type": "paleo",
      "Protein(g)": 181.55,
      "Carbs(g)": 28.62,
      "Fat(g)": 146.14,
      "cluster": 0
    }
  ],
  "metadata": {
    "execution_time_seconds": 0.026,
    "source": "Local CSV",
    "dataset": "All_Diets.csv",
    "dataset_from_cache": true
  }
}
```

## Sign-Off and Hand-Off

Every completion condition for Stage 1 in `division.md` is met, with the evidence in `docs/`:

| Completion condition | Result | Evidence |
|---|---|---|
| 44 pytest tests pass, flake8 clean (Python 3.11) | Pass | docs/screenshots/cli-pytest-flake8.png |
| `func start` brings up the local host with 4 routes | Pass | docs/screenshots/cli-func-start.png |
| All 4 endpoints answer in the browser | Pass | docs/screenshots/api-*-browser.png |
| Real HTTP behaviour (paging, search, 400/404, local CORS) | 10 of 10 cases pass | docs/screenshots/cli-http-verification.png, docs/http-results.json |
| Record count consistent across the full CSV | 7,806 for both insights and clusters | docs/verification.txt |

All 7 screenshots were taken with the macOS `screencapture` tool from real windows on
screen: the browser images are Google Chrome windows with the address bar visible, running
in a separate empty profile so no personal browsing data appears, and the terminal images
are real command output in Terminal.app windows. Every check was local — no Azure resource
was created or changed, and no configuration outside `stage1/` was touched.

Hand-off:
1. To Person 2: the base URL `http://localhost:7071/api`, the JSON contract above, and the
   local CORS settings.
2. Person 3 later swaps local loading for Blob Storage while keeping the same API contract.

The team's existing `frontend/` still targets the earlier three endpoints, so the search box,
correlation heatmap and cluster scatter chart still need Person 2 to wire them up.
Do not run the existing `deploy.sh` to publish this folder: that script still targets
`../backend/`. The group submission also needs the Azure deployment, the PDF/Word screenshot
report and a video featuring every member (about 10 minutes). The original project already
has deployment and screenshot records, so a tool missing from this local environment is not
evidence that that work is outstanding. This folder covers Stage 1 only and does not replace
the final group submission.

## Existing Screenshots Checked

summary.html embeds 5 evidence images from the original project: the Function App running
state, the health, insights and recipes responses, and the CORS / HTTP 200 / timing record.
Those evidence the earlier three-endpoint deployment and do not need to be reproduced; the
new clusters, search and correlation features are evidenced by the Stage 1 verification
record instead. The course brief itself does not mandate k-means or four endpoints — those
come from the team's own division.md.
