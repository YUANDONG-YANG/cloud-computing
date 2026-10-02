# Project 2 (Phase 2) Gap Review - 2026-10-02

Sources: `Project2/Phase2_Cloud_Dashboard_Project 1.docx`, `Project2/UI-for-project2.html`.

## What exists in the repository
- Requirements analysis (`docs/Phase2-Analysis.md`) and a master overview report (`docs/reports/Project2-Master-Overview.html`).
- The course UI skeleton and the specification file.

## Critical finding: report claims are not backed by the repository
The master overview marks deployment, dashboard, visualization and integration items as "Done" / "Ready" / "Solved" and lists
URLs (`nutritional-func-app.azurewebsites.net`, `nutritional-dashboard.azurestaticapps.net`, resource group
`cpsy300-nutritional-rg`). The repository contains **no backend code, no frontend code, no deployment workflow and no
Azure screenshots**. Unless these resources really exist and are evidenced, those statements must be changed to
"Planned" or removed before submission. Submitting claims of deployed resources that were never created is an academic-integrity risk.

## Missing items per rubric
| Rubric item | Marks | Missing |
|---|---|---|
| Deployment (Azure Cloud) | 20 | Function App source (HTTP trigger, `function_app.py`, `host.json`, `requirements.txt`); real Azure Function App, Storage Account and resource group; portal screenshots with date/time; working public Function URL |
| Frontend Dashboard | 20 | Dashboard source (HTML/CSS/JS) based on the UI skeleton; Static Web App deployment and public link |
| Data Visualization | 20 | At least 3 charts rendered from live function data (bar, scatter/heatmap, pie) |
| Integration | 20 | Frontend `fetch()` to the Function endpoint; CORS configuration; refresh button; function execution time shown as metadata; Postman/browser test evidence |
| Cloud Practices | 10 | Environment variables / app settings (no secrets in repo), resource group, connection string to live storage; CI/CD workflow for the frontend and function |
| Documentation & Presentation | 10 | PDF with architecture, services and screenshots; challenges section based on real events |

## Deliverables checklist
- [ ] Deployed Azure Function URL (real, tested)
- [ ] Static Web App / frontend link (real, public)
- [ ] GitHub repo with frontend and backend code
- [ ] Documentation PDF with date/time-stamped screenshots

## Needs a human / an Azure account
Creating the Azure subscription resources, deploying, and taking portal screenshots cannot be done by tooling in this repo.
Never commit storage keys, connection strings or publish profiles; use app settings and GitHub secrets.
