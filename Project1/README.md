# CPSY 300 — Project 1: Nutritional Insights

A local cloud-native simulation: course CSV → Pandas analysis / Azurite Blob Storage → manually invoked Python function → JSON documents. No real Azure resources are required.

## Run with Docker (Ubuntu VM)

```bash
mkdir -p output simulated_nosql evidence
docker build -t diet-analysis:project1 .
docker compose run --rm analysis
docker compose up -d --wait azurite
docker compose run --rm upload
docker compose run --rm --no-deps function
```

The image uses UID 1000. On a machine with another UID, make the two output folders writable or use `docker compose run --user "$(id -u):$(id -g)" ...`. The dataset is bundled at `data/All_Diets.csv`. To substitute another file, bind-mount it onto `/app/data/All_Diets.csv`.

`docker compose up function` also starts Azurite and its upload dependency. The function is a manually invoked Python simulation, not an Azure Functions host or real event trigger. Azurite persists blobs in a named volume; the JSON database is mounted onto the host. Compose uses `AZURITE_HOST=azurite`, while host execution defaults to `127.0.0.1`. The connection key in `storage_config.py` is the public emulator key documented by Microsoft.

## Local Python alternative

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python data_analysis.py
# Start Azurite with Compose before these two commands:
python upload_dataset.py
python lambda_function.py
pytest -q
flake8 .
python scripts/verify_outputs.py
```

## Tests and benchmark without host Python packages

```bash
docker build -f Dockerfile.test -t diet-analysis:tests .
docker run --rm -v "$PWD:/app" diet-analysis:tests python -m pytest -q
docker run --rm -v "$PWD:/app" diet-analysis:tests flake8 .
docker run --rm -v "$PWD:/app" diet-analysis:project1 python scripts/verify_outputs.py
docker run --rm -v "$PWD:/app" diet-analysis:project1 python scripts/benchmark.py
docker build -f Dockerfile.baseline -t diet-analysis:baseline .
docker image inspect diet-analysis:baseline diet-analysis:project1
```

The aggregation benchmark verifies numerical equivalence, uses one warmup and 15 measured runs, and reports medians. The 20x workload is a replicated stress test, not new observations. The Docker baseline uses identical dependencies and source but retains pip's cache. The optimized image uses a wheel builder and a transient wheel mount with no pip cache. Size reduction is attributable to excluded cache/artifacts, not to the mere presence of a second stage. Exact resolved dependencies are in `evidence/installed-packages.txt`; direct requirements are pinned, transitive dependencies and base tags can change in future builds.

## Local registry demonstration

```bash
docker compose --profile registry up -d registry
docker tag diet-analysis:project1 localhost:5001/diet-analysis:project1
docker push localhost:5001/diet-analysis:project1
docker pull localhost:5001/diet-analysis:project1
docker run --rm localhost:5001/diet-analysis:project1
```

Port 5001 avoids a pre-existing Lab 02 service. Registry and Azurite ports bind to loopback. Shut down project services with `docker compose --profile registry down`; add `-v` only if you intend to delete the stored blobs and registry data.

## Analysis decisions

- Trim and case-normalize diet/cuisine labels; missing labels become `unknown`.
- Convert macronutrients to numbers; missing, nonnumeric, negative and infinite values use the valid column mean. Reject empty inputs, missing required columns and columns with no usable numeric values.
- Undefined ratios (zero denominator) remain missing; they are blank in the exported CSV, never infinity.
- Rank each diet by protein descending, retain five rows (fewer if the group is smaller), preserve source order for ties. Cuisine mode includes every tied winner.
- Mean protein is the main comparison across diets; total protein is also reported and depends on recipe counts. These are recipe quantities, not standardized serving quantities.
- Keep original rows and extraction fields. A repeated name is not enough evidence to delete a recipe.

Outputs include the cleaned dataset with both ratios, mean and total tables, 25 top recipes, cuisine counts, summary JSON, and three timestamped PNGs. Serverless output is `simulated_nosql/results.json`.

## GitHub Actions and remaining submission steps

`.github/workflows/deploy.yml` builds, tests, checks code, runs the full Azurite flow, compares outputs, pushes/pulls a local registry image, and executes the retrieved image. Artifacts are uploaded even on failure. A GitHub-hosted runner starts its own Azurite; it never tries to reach this VM. Optional Docker Hub publishing uses repository variable `DOCKERHUB_USERNAME` and secret `DOCKERHUB_TOKEN`.

A local Git repository has been initialized. No remote GitHub run is claimed. Create/select your team repository and use your own Git identity:

```bash
git config user.name "YOUR REAL NAME"
git config user.email "YOUR GITHUB EMAIL"
git add .
git commit -m "Implement nutritional analysis and local cloud simulation"
git remote add origin YOUR_REPOSITORY_URL
git push -u origin main
```

Review the Actions result and capture a real successful run with date/time visible. Each member should make and review their own substantive changes; do not manufacture contribution history. Complete `report/Contribution-Report.html` with actual names, IDs, hours, meetings and commit/PR links, then print it to PDF. Record the team presentation using `report/Video-Guide.html` (everyone visible). The included project PDF clearly identifies GitHub and team evidence as pending.

## References

- [Azurite default account and connection strings](https://github.com/Azure/Azurite#default-storage-account)
- [Docker multi-stage builds](https://docs.docker.com/build/building/multi-stage/)
- [Pandas GroupBy guide](https://pandas.pydata.org/docs/user_guide/groupby.html)
- [GitHub: publishing Docker images](https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images)
