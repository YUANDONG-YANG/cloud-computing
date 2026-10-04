"""Task 5: measure cold-start and warm-invocation latency of the simulated function.

Runs on the CI runner with the standard library only. Azurite must already be
running with All_Diets.csv uploaded (docker compose up -d --wait azurite, then
docker compose run --rm upload).

Usage: python3 scripts/cold_start_benchmark.py <image> <label>
"""
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

NETWORK = "nutritional-insights_default"  # network created by docker compose
RUNS = 5


def timed(cmd):
    start = time.perf_counter()
    subprocess.run(cmd, check=True, capture_output=True)
    return time.perf_counter() - start


def median_seconds(cmd):
    timed(cmd)  # discard one run so Docker's own first-use caching does not skew the median
    return statistics.median(timed(cmd) for _ in range(RUNS))


def main(image, label):
    run = ["docker", "run", "--rm", "--network", NETWORK, "-e", "AZURITE_HOST=azurite"]
    size = subprocess.run(["docker", "image", "inspect", image, "--format", "{{.Size}}"],
                          check=True, capture_output=True, text=True).stdout

    # Every "docker run" is a brand-new container, so each of these is a cold start.
    container = median_seconds(run + [image, "true"])
    imports = median_seconds(run + [image, "python", "-c", "import lambda_function"])
    cold = median_seconds(run + [image, "python", "lambda_function.py"])

    # One long-lived container that invokes the function several times: a warm instance.
    warm_cmd = run + ["-e", "PYTHONPATH=/app", "-v", f"{Path('scripts').resolve()}:/bench:ro",
                      image, "python", "/bench/warm_invocations.py", str(RUNS)]
    warm_out = subprocess.run(warm_cmd, check=True, capture_output=True, text=True).stdout
    warm = json.loads(warm_out.strip().splitlines()[-1])

    result = {
        "label": label, "image": image, "size_mb": round(int(size) / 1e6, 1),
        "container_start_s": round(container, 3),
        "python_imports_s": round(imports - container, 3),
        "cold_invocation_s": round(cold, 3),
        "warm_invocation_s": round(warm["median_s"], 3),
    }
    Path("evidence").mkdir(exist_ok=True)
    Path(f"evidence/cold-start-{label}.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))

    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as out:
            out.write(f"### Cold start: {label}\n\n| Measure | Value |\n|---|---|\n")
            for key, value in result.items():
                out.write(f"| {key} | {value} |\n")
            out.write("\n")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
