# Project 2 (Phase 2) Mark-Loss Review (2026-10-02)

Source of truth for marking: `Project2/Phase2_Cloud_Dashboard_Project 1.docx` (section 6 rubric, section 7 deliverables).
Ground truth for all data claims: `Project1/data/All_Diets.csv` and `Project1/docs/results/*.csv`.
Scope: every rubric category. Companion to `gap-review-2026-10-02.md`, which was written before the code landed and is now
partly out of date (backend and frontend code now exist).

## Verification method

- Extracted the rubric from the .docx and mapped each category to the code that implements it.
- Re-ran the `/api/insights` aggregation logic against the real CSV and compared every number against `Project1/docs/results/`.
- Executed the `sed` expression from `deploy.sh` in isolation to confirm whether it runs.
- Recomputed recipe counts, total protein, common cuisines, diet shares and macro correlations from the raw CSV.

## Score estimate if submitted as-is

| Category | Marks | Estimate | Main cause of loss |
|---|---|---|---|
| Deployment (Azure Cloud) | 20 | 0-4 | No real Azure resources, no portal screenshots; `deploy.sh` aborts before finishing |
| Frontend Dashboard | 20 | 12-16 | Code is complete and clear, but the rubric requires a publicly accessible deployment |
| Data Visualization | 20 | 14-18 | Four charts are implemented; in demo mode they render fabricated numbers |
| Integration | 20 | 0-5 | `API_BASE_URL` defaults to `/api`; on static hosting this 404s and silently falls back to demo data |
| Cloud Practices | 10 | 4-6 | CORS wide open, connection string echoed to the terminal, naming/region inconsistent across docs and script |
| Documentation & Presentation | 10 | 3-5 | No PDF, no screenshots; the master overview describes a system that does not exist |
| **Total** | **100** | **~33-54** | |

With the blockers below fixed and one real deployment performed, 90+ is reachable. The backend aggregation code is the
strongest part of the project and needs no functional change.

## Blockers (fix these first)

### B1. deploy.sh cannot complete -- `deploy.sh:132`

The `sed` command uses `|` as its delimiter while the search pattern itself contains `||`, which truncates the expression.
Verified in isolation:

```
sed: -e expression #1, char 54: unknown option to `s'   EXIT=1
```

`deploy.sh:14` sets `set -euo pipefail`, so the script aborts at step 5 of 6 -- after the Function App is published but
before the frontend is configured or deployed. Step 6 never runs.

Fix: use a delimiter that does not appear in the pattern, e.g.

```bash
sed -i "s#^const API_BASE_URL = .*#const API_BASE_URL = window.NUTRITIONAL_API_URL || \"${FUNCTION_URL}/api\";#" frontend/app.js
```

### B2. Integration marks are lost silently -- `frontend/app.js:15`

`API_BASE_URL` falls back to `/api`. A Static Web App with no linked API backend returns 404, the `catch` at
`frontend/app.js:171` switches to `DEMO_DATA`, and the page still renders every chart behind a small yellow
"Demo Mode" pill. A marker sees a full dashboard built entirely from invented numbers.

Fix: inject the real endpoint in `index.html` before `app.js` loads, and make the demo fallback a prominent banner rather
than a pill.

```html
<script>window.NUTRITIONAL_API_URL = "https://<function-app>.azurewebsites.net/api";</script>
```

### B3. DEMO_DATA is fabricated while its comment claims otherwise -- `frontend/app.js:34`

The comment reads "real values from the dataset". Checked field by field against the CSV:

| Field | In `app.js` | Ground truth | |
|---|---|---|---|
| `average_macros` | dash 69.28 / keto 101.27 / vegan 56.16 | matches | OK |
| `diet_counts` | dash 1558, keto 1241, paleo 1561, vegan 1693 | dash **1745**, keto **1512**, paleo **1274**, vegan **1522** | 4 of 5 wrong |
| `total_protein_by_diet` | dash 107935.12, keto 125670.45, paleo 138412.34, vegan 87654.21 | dash **120897.57**, keto **153114.96**, paleo **112971.65**, vegan **85471.00** | 4 of 5 wrong |
| `common_cuisines` | mediterranean -> italian 410; vegan -> indian 378; dash 520; keto 485; paleo 498 | mediterranean -> **mediterranean 1274**; vegan -> **american 925**; dash **639**; keto **663**; paleo **535** | all wrong |
| `top_recipes` | 25 entries, e.g. "Bacon-Wrapped Stuffed Chicken" | real top rows are "Salmon Mousse", "12th Man Hot Wings", "Fava Bean Salad with Mountain Ham and Mint", ... | 25 of 25 invented |

Only `mediterranean: 1753`, `highest_mean_protein_diet: keto` (101.27) and `highest_total_protein_g: 177249.89` are correct.
Real values are already committed in `Project1/docs/results/average_macros.csv`, `total_protein.csv`,
`common_cuisines.csv` and `top5_protein_recipes.csv` -- copy them in and delete the misleading comment.
This is an academic-integrity exposure, not just a defect.

## Project2-Master-Overview.html contradicts the implementation

The report marks all six rubric categories "Done" and both URLs "Ready", with no supporting evidence in the repository.
It also describes a different system from the one that was built:

| # | Report claims | Repository reality |
|---|---|---|
| 1 | Code sample uses the v1 model (`main(req)` + `function.json`) | `backend/function_app.py` uses the v2 model (`func.FunctionApp()` decorators); no `function.json` exists |
| 2 | Endpoints `/api/nutritional-insights` and `/api/clusters` (K-means) | Actual endpoints are `/api/health`, `/api/insights`, `/api/recipes`; there is no clustering feature at all |
| 3 | Server-side pagination `?page=1&limit=20` | Client-side only (`ROWS_PER_PAGE = 50`, `frontend/app.js:31`); `/api/recipes` returns the full 1.21 MB payload |
| 4 | GitHub Actions deploys the Function App and the Static Web App | `.github/workflows/deploy.yml` only runs the Project 1 local Docker simulation; no Azure deployment job |
| 5 | "CORS properly scoped" to the Static Web App origin | `deploy.sh:111` and `function_app.py:56` both use `*` |
| 6 | Resource group `cpsy300-nutritional-rg`, region canadacentral, storage `nutritionalstorage`, container `data`, env var `STORAGE_CONTAINER`, Python 3.10 | `deploy.sh`: `cpsy300-nutritional-insights-rg`, eastus, `cpsy300nutrition<hex>`, container `datasets`, env var `BLOB_CONTAINER_NAME`, Python 3.11 |
| 7 | Pie insight: "Keto has the largest share (24.2%), Vegan the smallest (13.5%)" | Real shares: mediterranean **22.5%** (largest), dash 22.4%, vegan 19.5%, keto 19.4%, paleo **16.3%** (smallest) |
| 8 | Heatmap insight: "Protein-Carbs and Carbs-Fat show negative correlations" | Both are **positive**: Protein-Carbs **+0.156**, Carbs-Fat **+0.269**. (Protein-Fat 0.478 vs the reported 0.45 is fine) |
| 9 | Frontend has "search + dropdown, API interaction buttons" | Implemented controls are a diet dropdown and a refresh button only |
| 10 | All six Challenges marked "Solved" | At least CORS scoping, server-side pagination and CI/CD deployment have no implementation behind them |

`docs/Phase2-Analysis.md` section 7 is also wrong (keto ~1890, vegan ~1050, dash ~1561, paleo ~1553) and disagrees with
the equally wrong numbers in `app.js`. Correct counts: mediterranean 1753, dash 1745, vegan 1522, keto 1512, paleo 1274.

## Backend: verified correct

Re-ran the `/api/insights` pipeline (`clean_data` then `average_macros` / `top_recipes` / `common_cuisines` plus totals
and summary) against the real CSV:

```
insights JSON OK, 5848 bytes
diet_counts: {mediterranean: 1753, dash: 1745, vegan: 1522, keto: 1512, paleo: 1274}   <- matches Project 1 results
recipes JSON: 1,272,707 bytes (1.21 MB)
```

Every aggregate agrees with `Project1/docs/results/`. `allow_nan=False` does not trip, because the NaN-bearing ratio
columns are not included in any response. Secondary issues:

| # | Issue | Location | Affects |
|---|---|---|---|
| 1 | `/api/recipes` returns all 7,806 rows (1.21 MB) with no pagination, while the report claims pagination exists | `backend/function_app.py:149` | Cloud Practices; also makes claim 3 above true if implemented |
| 2 | Storage connection string is echoed to stdout at the end of deployment -- leaks into screen recordings and screenshots | `deploy.sh:199` | Cloud Practices |
| 3 | Host-level CORS (`az functionapp cors add`) stacked on a hand-written `Access-Control-Allow-Origin: *` can emit a duplicate header, which browsers reject. Keep one, preferably the host-level setting | `deploy.sh:108`, `function_app.py:56` | Integration |
| 4 | Response advertises `Access-Control-Allow-Methods: GET, OPTIONS` but no route accepts OPTIONS. Harmless today because the frontend sends no custom headers and triggers no preflight | `function_app.py:57` | Latent |
| 5 | No `staticwebapp.config.json`; `az staticwebapp create --source "."` without a GitHub token cannot actually create the app, and the failure is swallowed by a redirect-and-true guard | `deploy.sh:154` | Deployment |
| 6 | The execution-time badge is overwritten by the `/api/recipes` timing, so it reports the last call rather than the insights call | `frontend/app.js:176` | Minor; rubric only asks that execution time be shown |
| 7 | Project 2 has no tests or lint config, unlike Project 1 (pytest + flake8) | `Project2/` | Not scored directly; weakens the Cloud Practices narrative |

## Deliverables checklist (docx section 7)

- [ ] Deployed Azure Function URL -- real and tested (currently only an unverified URL in the report)
- [ ] Azure Static Web App / frontend link -- real and public
- [x] GitHub repository with frontend and backend code -- `origin` is `github.com/YUANDONG-YANG/cloud-computing`, code present
- [ ] Documentation PDF with architecture, services and screenshots -- not started (report lists it as "Pending")

## Fix order

1. Fix the `deploy.sh` sed (B1), then run one real deployment and capture portal screenshots with the clock visible. -- Deployment 20
2. Inject the real API URL (B2); confirm the page shows "API Connected", not "Demo Mode"; capture that plus a Postman/browser test of the endpoint. -- Integration 20
3. Replace `DEMO_DATA` with the real values from `Project1/docs/results/*.csv` and remove the false comment (B3).
4. Rewrite `Project2-Master-Overview.html`: use the real code, drop `/api/clusters` and the server-side pagination claim, correct the pie shares and the correlation signs, align resource names/region/runtime with `deploy.sh`, and downgrade unfinished items from "Done" to "Planned".
5. Export the Documentation PDF with timestamped screenshots. -- Documentation 10
6. Narrow CORS to the Static Web App origin and delete the connection-string echo. -- Cloud Practices 10

Step 4 should come before step 5. As it stands, a marker who compares the report against the code will find the described
system does not match the implementation, which costs more than an openly incomplete submission would.

## Needs a human with an Azure account

Creating the subscription resources, deploying, and capturing portal screenshots cannot be done from this repository.
Never commit storage keys, connection strings or publish profiles; use app settings and GitHub secrets.
