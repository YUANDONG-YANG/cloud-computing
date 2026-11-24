# Project 3 Demo Screenshots

Screenshots captured from the deployed Azure environment on 2026-11-24:

- `azure-resources-overview.png` — Azure resource group inventory.
- `function-app-functions.png` — deployed Function App, including the enabled `blob_trigger_clean` trigger.
- `dashboard-authenticated.png` — authenticated dashboard and security cards.
- `health-status.png` — public health endpoint showing Cosmos DB connectivity, 7,806 cached recipes, bcrypt, and service-managed AES-256 encryption.
- `cosmos-cache-documents.png` — Cosmos DB cache document IDs and cache totals.
- `cosmos-encryption.png` — Cosmos DB Data Encryption blade showing service-managed keys.
- `bcrypt-hash.png` — Cosmos DB user document showing a bcrypt hash; the temporary evidence user was removed after capture.

The Function App list confirms the Blob trigger is enabled.

## Added later on 2026-11-24

- `dashboard-diet-filter.png` — Keto filter applied: every row is Keto, footer reads 1512 total over 76 pages.
- `dashboard-keyword-search.png` — search for "chicken": 732 total over 37 pages.
- `dashboard-pagination.png` — page 2 of the chicken search: rows 21–40, page 2 highlighted, Previous enabled.

Each of these three is a composite of two crops from the same browser view (top
controls and table footer), joined at a dashed line.

The Blob trigger log that was unavailable earlier is now recorded: a live
v1 → v2 upload and its reversal each produced exactly one `blob_trigger_clean`
execution. See `trigger-once-2026-11-24.md`.
