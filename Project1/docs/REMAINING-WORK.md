# Project 1 — remaining work (analysis as of 2026-10-02)

Source of truth for marking: `Project1/Project 1 Cloud-Native Nutritional Insights Application.html`
(Marking Criteria: T1 20, T2 20, T3 20, T4 20, T5 5, Video 10, Contribution 5).
The assignment file states no pass mark, video length or late penalty.

## Already done and verified in the repo
- Task 1: `data_analysis.py`, 3 charts (`docs/results/`), screenshot `docs/evidence/task1-analysis.png`.
- Task 2: multi-stage `Dockerfile`, `docker-compose.yml`, local registry push/pull (`task2-registry.png`). Docker Hub is optional.
- Task 3: `lambda_function.py` reads CSV from Azurite and writes `simulated_nosql/results.json`; screenshot `task3-azurite.png`; explanation is in Master Overview, Task 3.
- Task 4: `.github/workflows/deploy.yml`, green run #4 (`github-actions-run-4.png`).
- Task 5: one-page `docs/reports/Enhancement-Report.pdf` (image size and grouped aggregation).
- `docs/reports/Project1-Report.pdf` (export of Master Overview), `Video-Guide.html` (detailed scripts).

## Gaps that can be closed on the Ubuntu VM (needs a human for screenshots)
1. Task 2 screenshot of `docker compose run --rm analysis` output, full screen, system clock visible.
2. Task 3 screenshot of Azure Storage Explorer connected to Azurite
   (`http://127.0.0.1:10000/devstoreaccount1`) showing `datasets/All_Diets.csv`, with date/time.
3. Task 4 screenshot of Actions run #4 where the calendar date is visible.
4. Optional: Docker Hub push (needs `DOCKERHUB_USERNAME` variable and `DOCKERHUB_TOKEN` secret). Never print secrets.
Save images in `Project1/docs/evidence/`, then embed them in `Project1-Master-Overview.html` and re-export `Project1-Report.pdf`.

## Needs the other team members (cannot be done by tooling)
- Contribution Report (`docs/reports/Contribution-Report.html`): student IDs, hours, meetings, commit/PR/review links
  for Ethan Bayarsaikhan and Justin Norman-Rance. All current commits are by Yuandong; do not fabricate history.
- Team video (10 marks): all three on camera; follow `docs/reports/Video-Guide.html`.
- Ethan and Justin each need at least one real commit/PR and a review.

## Final steps
Re-export the PDF, then zip: `data_analysis.py`, `lambda_function.py`, `Dockerfile`,
`.github/workflows/deploy.yml`, the PDF report (screenshots + 1-page enhancement report), the video, the contribution report.
