"""Shared, deterministic cleaning and aggregation for batch and function jobs.

Adapted from Project 1 for use in Azure Functions (Phase 3).
Adds pre-computation of all visualization results for caching.
"""
import numpy as np
import pandas as pd

MACROS = ["Protein(g)", "Carbs(g)", "Fat(g)"]
REQUIRED = ["Diet_type", "Recipe_name", "Cuisine_type", *MACROS]


def clean_data(raw):
    """Clean raw recipe data: strip whitespace, normalize text, impute missing numerics."""
    df = raw.copy()
    df.columns = df.columns.str.strip()
    missing = sorted(set(REQUIRED) - set(df.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    if df.empty:
        raise ValueError("Dataset contains no recipes")
    for col in ["Diet_type", "Cuisine_type"]:
        df[col] = df[col].astype("string").str.strip().str.casefold()
        df[col] = df[col].replace("", pd.NA).fillna("unknown")
    df["Recipe_name"] = (df["Recipe_name"].astype("string").str.strip()
                         .replace("", pd.NA).fillna("Unnamed recipe"))
    imputed = {}
    for col in MACROS:
        values = pd.to_numeric(df[col], errors="coerce")
        values = values.where(np.isfinite(values) & (values >= 0))
        imputed[col] = int(values.isna().sum())
        if values.notna().sum() == 0:
            raise ValueError(f"No valid numeric values in {col}; cannot impute")
        df[col] = values.fillna(values.mean())
    for name, numerator, denominator in [
        ("Protein_to_Carbs_ratio", "Protein(g)", "Carbs(g)"),
        ("Carbs_to_Fat_ratio", "Carbs(g)", "Fat(g)"),
    ]:
        df[name] = df[numerator].div(df[denominator].replace(0, np.nan))
        df[name] = df[name].replace([np.inf, -np.inf], np.nan)
    df.attrs["imputed_values"] = imputed
    return df


def average_macros(df):
    """Return mean macronutrient values grouped by diet type."""
    return df.groupby("Diet_type", sort=True)[MACROS].mean()


def top_recipes(df, n=5):
    """Return the top n highest-protein recipes per diet type."""
    return (df.sort_values("Protein(g)", ascending=False, kind="stable")
            .groupby("Diet_type", sort=True).head(n)
            .sort_values("Diet_type", kind="stable"))


def common_cuisines(df):
    """Return the most common cuisine type(s) per diet, preserving ties."""
    counts = df.groupby(["Diet_type", "Cuisine_type"]).size().rename("count")
    table = counts.reset_index()
    maxima = table.groupby("Diet_type")["count"].transform("max")
    return table[table["count"].eq(maxima)].reset_index(drop=True)


def diet_counts(df):
    """Return recipe count per diet type."""
    return df.groupby("Diet_type").size().rename("count")


def precompute_all(df):
    """Pre-calculate ALL visualization results for caching.

    Returns a dict ready to be serialized and stored in Redis / Cosmos DB.
    All subsequent /api/insights calls serve this cached data instead
    of re-computing.
    """
    avg = average_macros(df)
    top = top_recipes(df, n=5)
    cuisines = common_cuisines(df)
    counts = diet_counts(df)

    # Bar chart data: average macros per diet
    avg_dict = {}
    for diet in avg.index:
        avg_dict[diet] = {
            "Protein": round(float(avg.loc[diet, "Protein(g)"]), 2),
            "Carbs": round(float(avg.loc[diet, "Carbs(g)"]), 2),
            "Fat": round(float(avg.loc[diet, "Fat(g)"]), 2),
        }

    # Pie chart data: recipe count per diet
    counts_dict = {diet: int(counts[diet]) for diet in counts.index}

    # Heatmap data: macros grid
    heatmap = {
        "diets": list(avg.index),
        "nutrients": MACROS,
        "values": avg.round(2).values.tolist(),
    }

    # Scatter plot data: top recipes
    scatter_data = []
    for _, row in top.iterrows():
        scatter_data.append({
            "diet": row["Diet_type"],
            "recipe": row["Recipe_name"],
            "cuisine": row["Cuisine_type"],
            "protein": round(float(row["Protein(g)"]), 2),
            "carbs": round(float(row["Carbs(g)"]), 2),
            "fat": round(float(row["Fat(g)"]), 2),
        })

    # Common cuisines per diet
    cuisines_dict = {}
    for _, row in cuisines.iterrows():
        diet = row["Diet_type"]
        if diet not in cuisines_dict:
            cuisines_dict[diet] = []
        cuisines_dict[diet].append({
            "cuisine": row["Cuisine_type"],
            "count": int(row["count"]),
        })

    # All unique diet types and cuisine types for filters
    all_diets = sorted(df["Diet_type"].unique().tolist())
    all_cuisines = sorted(df["Cuisine_type"].unique().tolist())

    return {
        "total_recipes": len(df),
        "diet_types": all_diets,
        "cuisine_types": all_cuisines,
        "average_macros": avg_dict,
        "recipe_counts": counts_dict,
        "heatmap": heatmap,
        "top_recipes": scatter_data,
        "common_cuisines": cuisines_dict,
    }


def df_to_records(df):
    """Convert a cleaned DataFrame to a list of dicts for recipe search."""
    cols = ["Diet_type", "Recipe_name", "Cuisine_type",
            "Protein(g)", "Carbs(g)", "Fat(g)"]
    available = [c for c in cols if c in df.columns]
    records = df[available].copy()
    for col in MACROS:
        if col in records.columns:
            records[col] = records[col].round(2)
    return records.to_dict(orient="records")
