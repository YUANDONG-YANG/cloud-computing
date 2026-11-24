# Azure deployment smoke check — 2026-11-24

## Deployment

- Subscription: Azure for Students
- Resource group: `cpsy300-project3-rg`
- Storage and Function App: Canada Central
- Cosmos DB serverless: Central US. Cosmos account creation was unavailable in
  Canada Central for this subscription, so `COSMOS_LOCATION=centralus` was used.
- Frontend: <https://cpsy300p3storage.z9.web.core.windows.net/>
- API: <https://cpsy300-p3-functions.azurewebsites.net/api>
- The project deploy script created the resources, deployed the backend and
  frontend, configured platform CORS, and uploaded the dataset.

## Results

- `GET /api/health`: **200**, healthy; Cosmos DB connected; user store is Cosmos
  DB; insights cache is present; recipe cache contains **7,806** records.
- Frontend root: **200**; deployed `config.js` points to the Function App API.
- Unauthenticated `GET /api/insights` and `GET /api/recipes`: **401**.
- Browser preflight to `/api/insights`: **204** with the static website origin,
  `GET`, and the `Authorization` request header allowed.
- Unauthenticated API responses carry one matching `Access-Control-Allow-Origin`
  header.
- Temporary live account flow: register **201**, login **200**, `/api/auth/me`
  **200**, authenticated insights **200**, authenticated recipes **200** with
  five rows returned and a total of 7,806. The temporary Cosmos user document
  was deleted after the check.
- Local backend suite: **181 passed**. `flake8`, JavaScript syntax checks, shell
  syntax checks, and `git diff --check` passed.

## Not covered

Google and GitHub OAuth were not exercised because provider client credentials
were not configured. No screenshots or video were captured. The Azure resources
remain deployed; run `./teardown.sh` after the demo to remove them.
