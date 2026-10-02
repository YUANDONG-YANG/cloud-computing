#!/usr/bin/env python3
"""Generate All_Diets_v2.csv -- the "second version" of the dataset used in the
Phase 3 video demo.

The Phase 3 rubric asks the presenter to upload a modified copy of the dataset
and show that the blob trigger re-runs the cleaning and pre-computation exactly
once, after which the dashboard changes.  For that to read on camera the changes
have to be large and easy to narrate, so this script applies three deliberate
edits to the original file rather than random noise:

  A. Triple Protein(g) on every vegan row.
     -> average_macros / heatmap: vegan goes from the LOWEST-protein diet to the
        highest.
  B. Append one new keto recipe, "DEMO V2 Ultra Protein Power Bowl", with
     1500 g of protein.
     -> top_recipes: a new, obvious #1 for keto and for the whole scatter plot.
  C. Drop every paleo row whose cuisine is "american" (535 rows).
     -> recipe_counts / total_recipes: the paleo slice shrinks.
     -> common_cuisines: paleo's most common cuisine flips american -> italian.
     -> top_recipes: paleo loses "Turkey Soup" (1142.58 g) from its top five.

Nothing else is touched: the column list, column order, dtypes and line endings
all match the original.  Run from any directory:

    python Project3/data/make_v2.py

Measured before/after numbers are tabulated in Project3/docs/demo-plan.md.
"""
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent.parent / "Project1" / "data" / "All_Diets.csv"
TARGET = HERE / "All_Diets_v2.csv"

PROTEIN_MULTIPLIER = 3.0
BOOSTED_DIET = "vegan"
DROPPED_DIET = "paleo"
DROPPED_CUISINE = "american"
HERO_RECIPE = {
    "Diet_type": "keto",
    "Recipe_name": "DEMO V2 Ultra Protein Power Bowl",
    "Cuisine_type": "american",
    "Protein(g)": 1500.0,
    "Carbs(g)": 12.0,
    "Fat(g)": 40.0,
    "Extraction_day": "10/16/2022",
    "Extraction_time": "17:20:09",
}


def build(source: Path = SOURCE) -> pd.DataFrame:
    """Return the v2 DataFrame built from the original CSV."""
    df = pd.read_csv(source)
    columns = list(df.columns)

    # Edit A -- triple vegan protein.
    vegan = df["Diet_type"].eq(BOOSTED_DIET)
    df.loc[vegan, "Protein(g)"] = (
        df.loc[vegan, "Protein(g)"] * PROTEIN_MULTIPLIER
    ).round(2)

    # Edit C -- drop paleo + american rows.
    drop = df["Diet_type"].eq(DROPPED_DIET) & df["Cuisine_type"].eq(DROPPED_CUISINE)
    df = df.loc[~drop].copy()

    # Edit B -- append the new highest-protein recipe.
    df = pd.concat([df, pd.DataFrame([HERO_RECIPE])], ignore_index=True)

    return df[columns]


def main() -> None:
    df = build()
    # The original file is CRLF-terminated and UTF-8; match it so the only
    # difference between v1 and v2 is the data itself.
    df.to_csv(TARGET, index=False, encoding="utf-8", lineterminator="\r\n")
    print(f"wrote {TARGET} ({len(df)} rows, {len(df.columns)} columns)")


if __name__ == "__main__":
    main()
