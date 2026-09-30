"""Check independent batch and Blob pipelines agree on every mean."""
import json
from pathlib import Path
import pandas as pd

batch = pd.read_csv("output/average_macros.csv").set_index("Diet_type")
blob = pd.DataFrame(json.loads(Path("simulated_nosql/results.json").read_text()))
pd.testing.assert_frame_equal(batch.sort_index(), blob.set_index("Diet_type").sort_index())
for name in ["average_macros.png", "macronutrient_heatmap.png", "top5_cuisine_scatter.png"]:
    assert (Path("output") / name).stat().st_size > 1000
print("PASS: batch and Azurite means match; all three charts exist")
