# Project 1 Marking Review (2026-10-02)

Source: `Project1/Project 1 Cloud-Native Nutritional Insights Application.html`
Scope: every marking item except the teammates' video recording.

## Checked, no obvious risk
| Task | Marks | Status |
|---|---|---|
| Task 1 Analysis and charts | 20 | `data_analysis.py`, bar chart / heatmap / scatter plot, timestamped screenshot all present |
| Task 2 Docker | 20 | Dockerfile, local build and run, local registry push/pull, Compose all present |
| Task 3 Azurite | 20 | `lambda_function.py` reads from Azurite and writes `simulated_nosql/results.json`; one timestamped live screenshot |
| Task 4 CI/CD | 20 | `deploy.yml`; Actions runs #4 and #13 succeeded |
| Task 5 Enhancement | 5 | One-page report; smaller image + faster grouped aggregation |

Tests: 12 `pytest` tests pass locally and `flake8` is clean (`docs/evidence/tests.log` updated).

## Open issues (possible mark loss)
| # | Issue | Affects | Owner | Status |
|---|---|---|---|---|
| 1 | Missing screenshot of `docker compose run --rm analysis` (command visible, system clock visible) | T2 Compose deployment screenshot | VM | To do |
| 2 | Actions screenshots show no absolute date (run #13 says "3 minutes ago"; run #4 has no calendar date). Wait for the new run triggered by `c9a7a69` / `83ad3f5` to turn green, then recapture with the system clock visible | T4 "date and time visible" | VM / host | To do |
| 3 | Azure Storage Explorer was not used to upload the CSV (the report marks it "partly"). Connect to `http://127.0.0.1:10000/devstoreaccount1` and capture `datasets/All_Diets.csv` with the time visible | T3 | VM | To do |
| 4 | Docker Hub push not done (optional, but safer). The owner types the token personally; never write it to a file or chat | T2 optional item | Yuandong | Optional |
| 5 | After screenshots are added: re-embed them in the Master Overview and re-export `Project1-Report.pdf` | Submitted PDF | Host | To do |
| 6 | Contribution report placeholders: Yuandong's hours, PRs/reviews, meeting records, communication methods, AI-use disclosure | Contribution (5) | Yuandong | To do |
| 7 | Contribution report rows for the teammates (student ID, work, hours, links) are empty. Must not be invented | Contribution (5) | Ethan / Justin | Waiting on teammates |
| 8 | Teammates have no real commit / PR / review, so "GitHub collaboration evidence" is missing | Contribution (5) | Ethan / Justin | Waiting on teammates |
| 9 | Commit `83ad3f5` is authored by "Lab Admin" while the report says "author YUANDONG-YANG". Explain it in the report and set `user.name` / `user.email` in the VM's git | Contribution report consistency | VM | To do |
| 10 | Zip packaging: besides the 4 required files, include `nutrition.py`, `storage_config.py`, `upload_dataset.py`, `requirements.txt`, `docker-compose.yml` and `data/`, otherwise the scripts cannot run | Submission requirements | Host | Deferred at the owner's request |

## Already fixed
- `tests.log` updated from 10 passed to 12 passed.
- Contribution report date, commit count and Actions run numbers updated (`c9a7a69`, `83ad3f5`).
- `storage_config.py` now only allows local Azurite endpoints, with matching tests (`c9a7a69`).
- VM push credential problem: the push was completed from the VM side (`83ad3f5`).

## Notes
- The assignment does not state a pass mark, a video length or a late penalty.
- The teammates' video (10 marks) is out of scope for this review.
- The final grade is decided by the marker; this file only lists possible deductions.
