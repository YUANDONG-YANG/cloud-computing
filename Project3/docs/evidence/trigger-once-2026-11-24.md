# Blob trigger runs once per dataset change — 2026-11-24

Live check against the deployed Function App (`cpsy300-p3-functions`).
Execution records come from the Function host's traces in Application
Insights; cache figures come from `GET /api/health` and authenticated
`GET /api/recipes` requests.

## v1 → v2 upload

| Step | Time (UTC) | Observation |
|---|---|---|
| Before | 20:03 | Cache built at 19:59:07–08 from dataset v1: 7,806 recipes; `diet=keto` → 1,512; `search=chicken` → 732 / 37 pages |
| Upload | 20:03:45 | `data/All_Diets_v2.csv` uploaded over `raw-data/All_Diets.csv` |
| Trigger | 20:03:47 | `Executing 'Functions.blob_trigger_clean' (Reason='New blob detected(LogsAndContainerScan): raw-data/All_Diets.csv')` |
| Done | 20:03:48 | `Executed 'Functions.blob_trigger_clean' (Succeeded, Duration=986ms)`; `insights_updated_at` 20:03:47.98, `recipes_updated_at` 20:03:48.11 |
| After | 20:04–20:08 | Cache from v2: 7,272 recipes; `diet=keto` → 1,513 / 76 pages; `search=chicken` → 680 / 34 pages, matching `docs/demo-plan.md` |
| Repeat reads | 20:07 | Three rounds of recipe and insights requests, all served with `source: cosmosdb` |

`blob_trigger_clean` executed exactly **once** for the upload. Between 20:03
and 20:08 the host logged one `blob_trigger_clean` execution and no other
cleaning or calculation, while the recipe and insights endpoints kept
answering from the Cosmos cache.

## v2 → v1 restore

| Step | Time (UTC) | Observation |
|---|---|---|
| Upload | 20:08:10 | The original v1 `All_Diets.csv` uploaded back over the v2 blob |
| Trigger | 20:08:18 | `Executing 'Functions.blob_trigger_clean'` (new blob detected) |
| Done | 20:08:19 | `Executed 'Functions.blob_trigger_clean' (Succeeded, Duration=868ms)` |
| After | 20:08:30 | Cache back on v1: 7,806 recipes; `diet=keto` → 1,512 / 76; `search=chicken` → 732 / 37 |

Again one execution for one upload. The deployment is left on dataset v1, so
the demo video can start from v1 and show the v2 upload itself.
