"""Shared, deterministic cleaning and aggregation for batch and function jobs."""
import numpy as np
import pandas as pd

MACROS = ["Protein(g)", "Carbs(g)", "Fat(g)"]
REQUIRED = ["Diet_type", "Recipe_name", "Cuisine_type", *MACROS]


def clean_data(raw):
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
    return df.groupby("Diet_type", sort=True)[MACROS].mean()


def top_recipes(df):
    # Stable sorting preserves source order for equal protein values.
    return (df.sort_values("Protein(g)", ascending=False, kind="stable")
            .groupby("Diet_type", sort=True).head(5)
            .sort_values("Diet_type", kind="stable"))


def common_cuisines(df):
    counts = df.groupby(["Diet_type", "Cuisine_type"]).size().rename("count")
    table = counts.reset_index()
    # Preserve all co-winners instead of silently dropping ties.
    maxima = table.groupby("Diet_type")["count"].transform("max")
    return table[table["count"].eq(maxima)].reset_index(drop=True)
