# Project 3 (Phase 3) Gap Review - 2026-10-02

> **Stale.** This review predates the implementation in commit `1049cbd`, which added the blob
> trigger, cache layer, auth and OAuth code that the sections below describe as missing. For the
> current picture see `score-risk-2026-10-02.md`.

Sources: `Project3/Project Phase 3.docx`, `Project3/UI-for-project3.html`.

## What exists in the repository
- Requirements analysis (`docs/Phase3-Analysis.md`) and a master overview report (`docs/reports/Project3-Master-Overview.html`).
- The course UI skeleton and the specification file.

## Critical finding: report claims are not backed by the repository
The master overview shows "Complete" for 9 rubric items (self-score "80/100, +20 pending"), "Enabled" encryption,
"bcrypt-12" and "Mitigated" security risks. The repository has **no blob-trigger function, no cache layer, no auth code,
no OAuth integration, no database and no screenshots**. Those statuses must be changed to "Planned" until real code and
evidence exist. A self-reported 80/100 for unbuilt work is an academic-integrity risk.

## Missing items per rubric
| Rubric item | Marks | Missing |
|---|---|---|
| Data cleaning once on file change | 10 | Blob-triggered function; cleaned CSV written to blob storage; logs proving it runs once per upload (needs 2 versions of All_Diets.csv) |
| Result calculation once on file change | 10 | Pre-computed results stored in Redis or Cosmos DB; insights endpoint reading only from the cache; before/after timing |
| Diet type filter | 5 | `/api/recipes?diet=` endpoint and UI control |
| Keyword search | 10 | `/api/recipes?search=` endpoint and UI input |
| Pagination | 5 | `page` / `pageSize` support in API and UI |
| Email/password auth | 10 | Register and login endpoints, bcrypt hashing, session/JWT, forms |
| OAuth login | 10 | Real OAuth app (Google or GitHub), redirect/callback handling, registered client ID and secret kept out of the repo |
| DB encryption + password hash | 10 | User store (Cosmos DB or similar) with encryption at rest, only hashes stored; evidence of the setting |
| Dashboard auth gate | 10 | Login-first UI, user name at top right, logout button |
| Presentation | 20 | Video (all members) covering the three required demo points |

## Dependency
Phase 3 builds on the Phase 2 deployed dashboard, so the Phase 2 gaps must be closed first.

## Needs a human / an Azure and OAuth account
Azure resources, Redis/Cosmos provisioning, OAuth app registration and the video cannot be produced by tooling.
Keep all secrets in app settings or GitHub secrets, never in the repository.
