"""Task 5: equivalent mean aggregation, repeated filtering vs one groupby."""
import json
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from nutrition import MACROS, average_macros, clean_data


def baseline(df):
    records = []
    for diet in sorted(df["Diet_type"].unique()):
        row = {"Diet_type": diet}
        for col in MACROS:
            row[col] = df.loc[df["Diet_type"] == diet, col].mean()
        records.append(row)
    result = pd.DataFrame(records).set_index("Diet_type")
    result.index = result.index.astype("string")
    return result


def measure(fn, df):
    fn(df)
    samples = []
    for _ in range(15):
        start = time.perf_counter()
        fn(df)
        samples.append((time.perf_counter() - start) * 1000)
    return {"median_ms": statistics.median(samples), "samples_ms": samples}


def main():
    df = clean_data(pd.read_csv("data/All_Diets.csv"))
    results = {"timestamp": datetime.now(timezone.utc).isoformat(),
               "python": platform.python_version(), "pandas": pd.__version__,
               "method": "one warmup, 15 measured runs; aggregation only, no I/O or cleaning",
               "workloads": []}
    for multiplier in [1, 20]:
        frame = pd.concat([df] * multiplier, ignore_index=True)
        pd.testing.assert_frame_equal(baseline(frame), average_macros(frame))
        before = measure(baseline, frame)
        after = measure(average_macros, frame)
        results["workloads"].append({
            "rows": len(frame), "replication_factor": multiplier,
            "baseline": before, "optimized": after,
            "speedup": before["median_ms"] / after["median_ms"],
        })
    Path("evidence").mkdir(exist_ok=True)
    Path("evidence/benchmark.json").write_text(json.dumps(results, indent=2))
    for item in results["workloads"]:
        print(f"{item['rows']} rows: repeated filtering "
              f"{item['baseline']['median_ms']:.3f} ms -> groupby "
              f"{item['optimized']['median_ms']:.3f} ms; {item['speedup']:.2f}x")


if __name__ == "__main__":
    main()
