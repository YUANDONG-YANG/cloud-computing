"""Runs inside the function container: import once, then invoke the function N times.

This is what a warm serverless instance does: the process stays alive, so only
the first call pays for imports and setup. Prints one JSON line of timings.
"""
import json
import statistics
import sys
import time

start = time.perf_counter()
from lambda_function import process_nutritional_data_from_azurite  # noqa: E402
import_s = time.perf_counter() - start

calls = []
for _ in range(int(sys.argv[1])):
    t = time.perf_counter()
    process_nutritional_data_from_azurite()
    calls.append(time.perf_counter() - t)

print(json.dumps({"import_s": import_s, "first_call_s": calls[0],
                  "median_s": statistics.median(calls[1:])}))