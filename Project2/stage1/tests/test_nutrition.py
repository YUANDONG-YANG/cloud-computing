"""Unit tests for the shared cleaning and aggregation helpers.

These guard the numbers the dashboard and the batch results agree on, so a
regression in cleaning or grouping fails here rather than in a marker's browser.
"""
import numpy as np
import pandas as pd
import pytest

from nutrition import MACROS, average_macros, clean_data, common_cuisines, top_recipes


def sample():
    """Three rows with messy labels, a missing protein and two zero denominators."""
    return pd.DataFrame({
        "Diet_type": [" Paleo ", "paleo", "VEGAN"],
        "Recipe_name": ["A", "B", "C"],
        "Cuisine_type": [" Italian ", "ITALIAN", "Indian"],
        "Protein(g)": [10, None, 30],
        "Carbs(g)": [0, 20, 10],
        "Fat(g)": [5, 0, 10],
    })


def frame(diets, proteins, names=None, cuisines=None):
    """Build an already-tidy raw frame with the given diets and protein values."""
    size = len(diets)
    return pd.DataFrame({
        "Diet_type": list(diets),
        "Recipe_name": list(names) if names else [f"R{i}" for i in range(size)],
        "Cuisine_type": list(cuisines) if cuisines else ["american"] * size,
        "Protein(g)": [float(value) for value in proteins],
        "Carbs(g)": [float(i + 1) for i in range(size)],
        "Fat(g)": [float(i + 2) for i in range(size)],
    })


def test_text_columns_are_stripped_casefolded_and_filled():
    raw = sample().rename(columns={"Diet_type": " Diet_type "})
    raw.loc[0, "Recipe_name"] = "  Spiced Lentils  "
    raw.loc[1, "Recipe_name"] = "   "
    raw.loc[2, " Diet_type "] = " "
    raw.loc[1, "Cuisine_type"] = None
    df = clean_data(raw)
    assert df["Diet_type"].tolist() == ["paleo", "paleo", "unknown"]
    assert df["Cuisine_type"].tolist() == ["italian", "unknown", "indian"]
    assert df["Recipe_name"].tolist() == ["Spiced Lentils", "Unnamed recipe", "C"]
    assert raw.loc[0, "Recipe_name"] == "  Spiced Lentils  "  # input is not mutated


def test_negative_and_non_finite_macros_are_imputed_with_the_column_mean():
    raw = sample()
    raw["Protein(g)"] = ["bad", -1, 12]
    raw["Carbs(g)"] = [np.inf, 4, 8]
    raw["Fat(g)"] = [5, 0, 10]
    df = clean_data(raw)
    assert df["Protein(g)"].tolist() == [12, 12, 12]
    assert df["Carbs(g)"].tolist() == [6, 4, 8]
    assert df["Fat(g)"].tolist() == [5, 0, 10]  # zero is valid, not missing
    assert df.attrs["imputed_values"] == {"Protein(g)": 2, "Carbs(g)": 1, "Fat(g)": 0}


def test_zero_denominators_are_undefined_not_infinity():
    df = clean_data(sample())
    assert pd.isna(df.loc[0, "Protein_to_Carbs_ratio"])
    assert pd.isna(df.loc[1, "Carbs_to_Fat_ratio"])
    assert df.loc[2, "Protein_to_Carbs_ratio"] == 3
    assert not np.isinf(df.select_dtypes("number").to_numpy()).any()


@pytest.mark.parametrize("kind", ["empty", "missing_column", "all_nan", "all_negative"])
def test_unusable_input_is_rejected(kind):
    raw = sample()
    if kind == "empty":
        raw = raw.iloc[:0]
    elif kind == "missing_column":
        raw = raw.drop(columns="Fat(g)")
    elif kind == "all_nan":
        raw["Fat(g)"] = np.nan
    else:
        raw["Fat(g)"] = [-1, -2, -3]
    with pytest.raises(ValueError):
        clean_data(raw)


def test_average_macros_groups_by_diet_and_sorts():
    df = clean_data(frame(["vegan", "dash", "vegan", "keto"], [10, 40, 20, 30]))
    avg = average_macros(df)
    assert avg.index.tolist() == ["dash", "keto", "vegan"]
    assert avg.columns.tolist() == MACROS
    assert avg.loc["vegan", "Protein(g)"] == 15
    assert avg.loc["dash", "Protein(g)"] == 40


def test_top_recipes_returns_n_highest_protein_rows_per_diet():
    df = clean_data(frame(
        ["keto", "keto", "keto", "keto", "vegan", "vegan"],
        [1, 9, 5, 7, 3, 8],
        names=list("ABCDEF"),
    ))
    top = top_recipes(df, n=2)
    assert top.groupby("Diet_type").size().to_dict() == {"keto": 2, "vegan": 2}
    assert top.loc[top["Diet_type"] == "keto", "Recipe_name"].tolist() == ["B", "D"]
    assert top.loc[top["Diet_type"] == "vegan", "Recipe_name"].tolist() == ["F", "E"]


def test_top_recipes_defaults_to_at_most_five_per_diet():
    df = clean_data(frame(["keto"] * 7 + ["vegan"] * 2, [1, 2, 3, 4, 5, 6, 7, 8, 9]))
    top = top_recipes(df)
    assert top.groupby("Diet_type").size().to_dict() == {"keto": 5, "vegan": 2}
    assert top.loc[top["Diet_type"] == "keto", "Protein(g)"].tolist() == [7, 6, 5, 4, 3]


def test_cuisine_mode_preserves_ties():
    df = clean_data(frame(
        ["paleo", "paleo", "vegan", "vegan", "vegan"],
        [1, 2, 3, 4, 5],
        cuisines=["italian", "French", "indian", "indian", "thai"],
    ))
    result = common_cuisines(df)
    paleo = result[result["Diet_type"] == "paleo"]
    vegan = result[result["Diet_type"] == "vegan"]
    assert set(paleo["Cuisine_type"]) == {"italian", "french"}
    assert paleo["count"].tolist() == [1, 1]
    assert vegan["Cuisine_type"].tolist() == ["indian"]
    assert vegan["count"].tolist() == [2]
