"""Task 1: analyze the course dataset and save charts without a display."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from nutrition import average_macros, clean_data, common_cuisines, top_recipes


def save_chart(fig, path, timestamp):
    fig.text(0.99, 0.01, f"Generated: {timestamp}", ha="right", fontsize=8)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(path, dpi=160)
    plt.close(fig)


def analyze(csv_path="data/All_Diets.csv", output="output"):
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    raw = pd.read_csv(csv_path)
    df = clean_data(raw)
    averages = average_macros(df)
    top = top_recipes(df)
    cuisines = common_cuisines(df)
    totals = df.groupby("Diet_type")["Protein(g)"].sum()
    winner_mean = averages["Protein(g)"].max()
    winner_total = totals.max()
    summary = {
        "generated_at": timestamp, "rows": len(df),
        "diet_types": len(averages), "imputed_values": df.attrs["imputed_values"],
        "highest_mean_protein_diets": averages.index[
            averages["Protein(g)"].eq(winner_mean)].tolist(),
        "highest_mean_protein_g": float(winner_mean),
        "highest_total_protein_diets": totals.index[totals.eq(winner_total)].tolist(),
        "highest_total_protein_g": float(winner_total),
        "undefined_ratios": {
            c: int(df[c].isna().sum()) for c in df if c.endswith("_ratio")},
        "interpretation": "Recipe-level values; no serving size or medical inference.",
    }
    df.to_csv(out / "cleaned_recipes.csv", index=False)
    averages.to_csv(out / "average_macros.csv")
    top.to_csv(out / "top5_protein_recipes.csv", index=False)
    cuisines.to_csv(out / "common_cuisines.csv", index=False)
    totals.to_csv(out / "total_protein.csv")
    (out / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False))
    sns.set_theme(style="whitegrid", palette="colorblind")
    fig, ax = plt.subplots(figsize=(10, 6))
    averages.plot.bar(ax=ax, rot=0)
    ax.set(title="Average macronutrients by diet", ylabel="Grams per recipe", xlabel="Diet type")
    save_chart(fig, out / "average_macros.png", timestamp)
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.heatmap(averages.T, annot=True, fmt=".1f", cmap="YlGnBu", ax=ax)
    ax.set(title="Macronutrients by diet (mean grams per recipe)", xlabel="Diet type", ylabel="")
    save_chart(fig, out / "macronutrient_heatmap.png", timestamp)
    fig, ax = plt.subplots(figsize=(12, 7))
    sns.scatterplot(data=top, x="Cuisine_type", y="Protein(g)", hue="Diet_type",
                    style="Diet_type", s=110, alpha=0.8, ax=ax)
    ax.set(title="Five highest-protein recipes per diet, by cuisine",
           xlabel="Cuisine", ylabel="Protein (g per recipe)")
    ax.tick_params(axis="x", rotation=30)
    save_chart(fig, out / "top5_cuisine_scatter.png", timestamp)
    print(timestamp)
    print(averages.round(2).to_string())
    print("Most common cuisines:\n" + cuisines.to_string(index=False))
    print(json.dumps(summary, indent=2))
    print(f"Saved tables and three charts to {out.resolve()}")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default="data/All_Diets.csv")
    parser.add_argument("--output", default="output")
    args = parser.parse_args()
    analyze(args.csv, args.output)
