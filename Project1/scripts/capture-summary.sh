#!/usr/bin/env bash
set -euo pipefail
cd /home/labadmin/Desktop/Project1-Nutritional-Insights
export DISPLAY=:0 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus
export GSETTINGS_SCHEMA_DIR=/home/labadmin/Desktop/lab02-screenshot-tool/usr/share/glib-2.0/schemas
shot() {
 sleep 2
 /home/labadmin/Desktop/lab02-screenshot-tool/usr/bin/gnome-screenshot -f "evidence/$1.png"
}
clear
printf 'CPSY 300 Project 1 | Task 1 | Saved execution log and output\n'
date -Is
head -n 19 evidence/analysis.log
python3 - <<'PY'
import json
s=json.load(open('output/summary.json'))
for k in ['rows','diet_types','highest_mean_protein_diets','highest_mean_protein_g','highest_total_protein_diets','highest_total_protein_g','undefined_ratios']:
 print(k, ':', s[k])
PY
shot task1-analysis
clear
printf 'CPSY 300 Project 1 | Task 2 | Live services and registry logs\n'
date -Is
docker compose ps
docker image ls diet-analysis
printf '\nSaved docker push result:\n'
tail -n 3 evidence/registry-push.log
printf '\nSaved docker pull result:\n'
cat evidence/registry-pull.log
shot task2-registry
clear
printf 'CPSY 300 Project 1 | Task 3 | Saved upload and function logs\n'
date -Is
cat evidence/upload.log evidence/function.log
printf '\nNoSQL JSON documents (compact display):\n'
python3 - <<'PY'
import json
for row in json.load(open('simulated_nosql/results.json')): print(row)
PY
shot task3-azurite
clear
printf 'CPSY 300 Project 1 | Task 4 | LOCAL evidence; GitHub run pending\n'
date -Is
printf '\nSaved pytest output:\n'
cat evidence/tests.log
printf '\nSaved successful flake8 + output verification:\n'
cat evidence/verification.log
printf '\nMeasured aggregation comparison (median of 15 runs):\n'
cat evidence/benchmark.log
shot task4-local-checks
touch evidence/capture-summary.done
