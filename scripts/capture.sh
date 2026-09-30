#!/usr/bin/env bash
set -euo pipefail
cd /home/labadmin/Desktop/Project1-Nutritional-Insights
export DISPLAY=:0
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus
export GSETTINGS_SCHEMA_DIR=/home/labadmin/Desktop/lab02-screenshot-tool/usr/share/glib-2.0/schemas
shot() {
  sleep 2
  /home/labadmin/Desktop/lab02-screenshot-tool/usr/bin/gnome-screenshot -f "evidence/$1.png"
}
clear
printf 'CPSY 300 Project 1 | Task 1: batch analysis\n'
date -Is
docker compose run --rm analysis 2>&1 | tee evidence/analysis.log
shot task1-analysis
clear
printf 'CPSY 300 Project 1 | Task 2: Docker Compose + local registry\n'
date -Is
docker compose ps
docker image ls diet-analysis
docker tag diet-analysis:project1 localhost:5001/diet-analysis:project1
docker push localhost:5001/diet-analysis:project1 2>&1 | tee evidence/registry-push.log
docker pull localhost:5001/diet-analysis:project1 2>&1 | tee evidence/registry-pull.log
shot task2-registry
clear
printf 'CPSY 300 Project 1 | Task 3: Azurite + function + JSON\n'
date -Is
docker compose run --rm upload 2>&1 | tee evidence/upload.log
docker compose run --rm --no-deps function 2>&1 | tee evidence/function.log
cat simulated_nosql/results.json
printf '\n'
shot task3-azurite
clear
printf 'CPSY 300 Project 1 | Task 4: LOCAL checks (GitHub run pending)\n'
date -Is
docker run --rm -v "$PWD:/app" diet-analysis:tests python -m pytest -q 2>&1 | tee evidence/tests.log
docker run --rm -v "$PWD:/app" diet-analysis:tests sh -c 'flake8 . && python scripts/verify_outputs.py' 2>&1 | tee evidence/verification.log
printf 'Lint exit code: 0\n'
cat evidence/benchmark.log
shot task4-local-checks
docker compose logs --no-color > evidence/compose.log
docker image inspect diet-analysis:baseline diet-analysis:project1 > evidence/image-inspect.json
docker run --rm diet-analysis:project1 pip freeze > evidence/installed-packages.txt
printf '\nScreenshots and logs saved.\n'
touch evidence/capture.done
