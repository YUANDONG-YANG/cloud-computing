"""Tests for nutrition.clean_data, precompute_all and df_to_records."""
import json
import math

import numpy as np
import pandas as pd
import pytest

import nutrition


def make_raw(**overrides):
    """A small, valid raw dataset; any column can be overridden."""
    data = {
        "Diet_type": ["  VEGAN ", "vegan", "Keto", "KETO "],
        "Recipe_name": ["  Lentil Stew ", "Tofu Bowl", " Steak ", "Egg Bake"],
        "Cuisine_type": [" Indian", "indian", "AMERICAN", " american "],
        "Protein(g)": [10.0, 20.0, 30.0, 40.0],
        "Carbs(g)": [50.0, 60.0, 5.0, 10.0],
        "Fat(g)": [1.0, 2.0, 30.0, 40.0],
    }
    data.update(overrides)
    return pd.DataFrame(data)


# ---------------------------------------------------------------------------
# clean_data: normalization
# ---------------------------------------------------------------------------

def test_column_names_are_stripped():
    raw = make_raw()
    raw.columns = [f"  {c} " for c in raw.columns]
    df = nutrition.clean_data(raw)
    assert "Diet_type" in df.columns
    assert "Protein(g)" in df.columns


def test_text_columns_are_stripped_and_casefolded():
    df = nutrition.clean_data(make_raw())
    assert list(df["Diet_type"]) == ["vegan", "vegan", "keto", "keto"]
    assert list(df["Cuisine_type"]) == [
        "indian", "indian", "american", "american",
    ]


def test_recipe_name_is_stripped_but_not_casefolded():
    df = nutrition.clean_data(make_raw())
    assert list(df["Recipe_name"]) == [
        "Lentil Stew", "Tofu Bowl", "Steak", "Egg Bake",
    ]


def test_blank_text_values_get_placeholders():
    raw = make_raw(
        Diet_type=["   ", "vegan", "keto", "keto"],
        Cuisine_type=["", "indian", "american", "american"],
        Recipe_name=["  ", "Tofu Bowl", "Steak", "Egg Bake"],
    )
    df = nutrition.clean_data(raw)
    assert df.loc[0, "Diet_type"] == "unknown"
    assert df.loc[0, "Cuisine_type"] == "unknown"
    assert df.loc[0, "Recipe_name"] == "Unnamed recipe"


def test_null_text_values_get_placeholders():
    raw = make_raw(
        Diet_type=[None, "vegan", "keto", "keto"],
        Cuisine_type=[np.nan, "indian", "american", "american"],
        Recipe_name=[None, "Tofu Bowl", "Steak", "Egg Bake"],
    )
    df = nutrition.clean_data(raw)
    assert df.loc[0, "Diet_type"] == "unknown"
    assert df.loc[0, "Cuisine_type"] == "unknown"
    assert df.loc[0, "Recipe_name"] == "Unnamed recipe"


def test_cleaning_does_not_mutate_the_caller_dataframe():
    raw = make_raw()
    before = raw.copy(deep=True)
    nutrition.clean_data(raw)
    pd.testing.assert_frame_equal(raw, before)


# ---------------------------------------------------------------------------
# clean_data: numeric imputation
# ---------------------------------------------------------------------------

def test_missing_macros_are_imputed_with_the_column_mean():
    raw = make_raw(**{"Protein(g)": [10.0, 20.0, np.nan, None]})
    df = nutrition.clean_data(raw)
    # Valid values are 10 and 20 -> mean 15.
    assert list(df["Protein(g)"]) == [10.0, 20.0, 15.0, 15.0]
    assert df.attrs["imputed_values"]["Protein(g)"] == 2


def test_negative_macros_are_treated_as_missing_and_imputed():
    raw = make_raw(**{"Fat(g)": [-5.0, 2.0, 4.0, -1.0]})
    df = nutrition.clean_data(raw)
    # Valid values are 2 and 4 -> mean 3.
    assert list(df["Fat(g)"]) == [3.0, 2.0, 4.0, 3.0]
    assert df.attrs["imputed_values"]["Fat(g)"] == 2
    assert (df["Fat(g)"] >= 0).all()


def test_non_numeric_and_infinite_macros_are_imputed():
    raw = make_raw(**{"Carbs(g)": ["not a number", 10.0, np.inf, 20.0]})
    df = nutrition.clean_data(raw)
    assert list(df["Carbs(g)"]) == [15.0, 10.0, 15.0, 20.0]
    assert df.attrs["imputed_values"]["Carbs(g)"] == 2
    assert np.isfinite(df["Carbs(g)"]).all()


def test_zero_macros_are_kept_not_imputed():
    raw = make_raw(**{"Protein(g)": [0.0, 20.0, 30.0, 40.0]})
    df = nutrition.clean_data(raw)
    assert df.loc[0, "Protein(g)"] == 0.0
    assert df.attrs["imputed_values"]["Protein(g)"] == 0


def test_imputed_counts_are_plain_ints_for_every_macro():
    df = nutrition.clean_data(make_raw())
    imputed = df.attrs["imputed_values"]
    assert set(imputed) == set(nutrition.MACROS)
    assert all(type(v) is int for v in imputed.values())
    assert json.dumps(imputed)


def test_all_invalid_macro_column_raises():
    raw = make_raw(**{"Protein(g)": [-1.0, np.nan, "abc", None]})
    with pytest.raises(ValueError, match="No valid numeric values"):
        nutrition.clean_data(raw)


# ---------------------------------------------------------------------------
# clean_data: error paths
# ---------------------------------------------------------------------------

def test_missing_required_column_raises_and_names_the_column():
    raw = make_raw().drop(columns=["Protein(g)"])
    with pytest.raises(ValueError, match="Missing required columns") as exc:
        nutrition.clean_data(raw)
    assert "Protein(g)" in str(exc.value)


def test_missing_required_columns_are_reported_sorted():
    raw = make_raw().drop(columns=["Cuisine_type", "Protein(g)"])
    with pytest.raises(ValueError) as exc:
        nutrition.clean_data(raw)
    message = str(exc.value)
    assert message.index("Cuisine_type") < message.index("Protein(g)")


def test_empty_dataframe_raises():
    raw = pd.DataFrame({col: [] for col in nutrition.REQUIRED})
    with pytest.raises(ValueError, match="Dataset contains no recipes"):
        nutrition.clean_data(raw)


def test_missing_columns_checked_before_emptiness():
    """An empty frame that is also missing columns reports the columns."""
    raw = pd.DataFrame({"Diet_type": []})
    with pytest.raises(ValueError, match="Missing required columns"):
        nutrition.clean_data(raw)


# ---------------------------------------------------------------------------
# clean_data: ratio columns
# ---------------------------------------------------------------------------

def test_ratio_columns_are_computed():
    raw = make_raw(**{
        "Protein(g)": [10.0, 20.0, 30.0, 40.0],
        "Carbs(g)": [5.0, 10.0, 10.0, 20.0],
        "Fat(g)": [1.0, 2.0, 5.0, 4.0],
    })
    df = nutrition.clean_data(raw)
    assert list(df["Protein_to_Carbs_ratio"]) == [2.0, 2.0, 3.0, 2.0]
    assert list(df["Carbs_to_Fat_ratio"]) == [5.0, 5.0, 2.0, 5.0]


def test_zero_denominator_gives_nan_not_inf():
    raw = make_raw(**{
        "Protein(g)": [10.0, 20.0, 30.0, 40.0],
        "Carbs(g)": [0.0, 10.0, 10.0, 20.0],
        "Fat(g)": [0.0, 2.0, 5.0, 4.0],
    })
    df = nutrition.clean_data(raw)
    assert math.isnan(df.loc[0, "Protein_to_Carbs_ratio"])
    assert math.isnan(df.loc[0, "Carbs_to_Fat_ratio"])
    # Nothing anywhere became an infinity.
    for col in ("Protein_to_Carbs_ratio", "Carbs_to_Fat_ratio"):
        assert not np.isinf(df[col].to_numpy(dtype="float64")).any()
    # The macro columns themselves keep their zeros.
    assert df.loc[0, "Carbs(g)"] == 0.0
    assert df.loc[0, "Fat(g)"] == 0.0


def test_zero_numerator_over_zero_denominator_is_nan():
    raw = make_raw(**{
        "Protein(g)": [0.0, 20.0, 30.0, 40.0],
        "Carbs(g)": [0.0, 10.0, 10.0, 20.0],
        "Fat(g)": [1.0, 2.0, 5.0, 4.0],
    })
    df = nutrition.clean_data(raw)
    assert math.isnan(df.loc[0, "Protein_to_Carbs_ratio"])


# ---------------------------------------------------------------------------
# Aggregates
# ---------------------------------------------------------------------------

@pytest.fixture
def clean():
    return nutrition.clean_data(make_raw())


def test_average_macros_groups_by_diet(clean):
    avg = nutrition.average_macros(clean)
    assert list(avg.index) == ["keto", "vegan"]
    assert avg.loc["vegan", "Protein(g)"] == pytest.approx(15.0)
    assert avg.loc["keto", "Protein(g)"] == pytest.approx(35.0)


def test_diet_counts(clean):
    counts = nutrition.diet_counts(clean)
    assert counts.to_dict() == {"keto": 2, "vegan": 2}


def test_common_cuisines_preserves_ties():
    raw = make_raw(
        Diet_type=["vegan", "vegan", "vegan", "vegan"],
        Cuisine_type=["indian", "indian", "thai", "thai"],
    )
    df = nutrition.clean_data(raw)
    table = nutrition.common_cuisines(df)
    assert sorted(table["Cuisine_type"]) == ["indian", "thai"]
    assert set(table["count"]) == {2}


def test_top_recipes_caps_per_diet():
    rows = 8
    raw = pd.DataFrame({
        "Diet_type": ["vegan"] * rows + ["keto"] * rows,
        "Recipe_name": [f"v{i}" for i in range(rows)]
                       + [f"k{i}" for i in range(rows)],
        "Cuisine_type": ["indian"] * rows + ["american"] * rows,
        "Protein(g)": list(range(rows)) + list(range(rows)),
        "Carbs(g)": [10.0] * (2 * rows),
        "Fat(g)": [5.0] * (2 * rows),
    })
    df = nutrition.clean_data(raw)
    top = nutrition.top_recipes(df, n=5)
    assert len(top) == 10
    assert top.groupby("Diet_type").size().to_dict() == {"keto": 5, "vegan": 5}
    # The highest-protein rows are the ones kept.
    assert sorted(top[top["Diet_type"] == "vegan"]["Protein(g)"]) == [
        3.0, 4.0, 5.0, 6.0, 7.0,
    ]


# ---------------------------------------------------------------------------
# precompute_all
# ---------------------------------------------------------------------------

def test_precompute_all_aggregates(clean):
    out = nutrition.precompute_all(clean)
    assert out["total_recipes"] == 4
    assert out["diet_types"] == ["keto", "vegan"]
    assert out["cuisine_types"] == ["american", "indian"]
    assert out["recipe_counts"] == {"keto": 2, "vegan": 2}
    assert out["average_macros"]["vegan"] == {
        "Protein": 15.0, "Carbs": 55.0, "Fat": 1.5,
    }
    assert out["average_macros"]["keto"] == {
        "Protein": 35.0, "Carbs": 7.5, "Fat": 35.0,
    }


def test_precompute_all_heatmap_shape(clean):
    out = nutrition.precompute_all(clean)
    heatmap = out["heatmap"]
    assert heatmap["diets"] == ["keto", "vegan"]
    assert heatmap["nutrients"] == nutrition.MACROS
    assert len(heatmap["values"]) == len(heatmap["diets"])
    assert all(len(row) == len(nutrition.MACROS)
               for row in heatmap["values"])
    assert heatmap["values"][0] == [35.0, 7.5, 35.0]


def test_precompute_all_top_recipes_rows(clean):
    out = nutrition.precompute_all(clean)
    rows = out["top_recipes"]
    assert len(rows) == 4
    assert set(rows[0]) == {"diet", "recipe", "cuisine",
                            "protein", "carbs", "fat"}
    names = {r["recipe"] for r in rows}
    assert names == {"Lentil Stew", "Tofu Bowl", "Steak", "Egg Bake"}


def test_precompute_all_common_cuisines(clean):
    out = nutrition.precompute_all(clean)
    assert out["common_cuisines"] == {
        "keto": [{"cuisine": "american", "count": 2}],
        "vegan": [{"cuisine": "indian", "count": 2}],
    }


def test_precompute_all_is_json_serializable(clean):
    out = nutrition.precompute_all(clean)
    # Must not raise, and must contain no NaN/Infinity (which json.dumps
    # would happily emit as invalid JSON).
    text = json.dumps(out, allow_nan=False)
    assert json.loads(text) == out


def test_precompute_all_json_safe_with_messy_input():
    """Zero denominators, negatives, blanks and junk still serialize."""
    raw = pd.DataFrame({
        " Diet_type ": ["  VEGAN", "", None, "keto", "keto"],
        "Recipe_name": ["  A ", "", None, "D", "E"],
        "Cuisine_type": ["Indian ", None, "", "american", "AMERICAN"],
        "Protein(g)": [10.0, -3.0, np.nan, "xyz", 40.0],
        "Carbs(g)": [0.0, 0.0, 10.0, np.inf, 20.0],
        "Fat(g)": [0.0, 2.0, -1.0, 4.0, None],
    })
    df = nutrition.clean_data(raw)
    out = nutrition.precompute_all(df)
    text = json.dumps(out, allow_nan=False)
    assert json.loads(text)["total_recipes"] == 5
    assert "unknown" in out["diet_types"]


def test_precompute_all_scalar_types_are_native(clean):
    out = nutrition.precompute_all(clean)
    assert type(out["total_recipes"]) is int
    for value in out["recipe_counts"].values():
        assert type(value) is int
    for macros in out["average_macros"].values():
        for value in macros.values():
            assert type(value) is float
    for diet in out["diet_types"]:
        assert type(diet) is str


# ---------------------------------------------------------------------------
# df_to_records
# ---------------------------------------------------------------------------

def test_df_to_records_columns_and_rounding():
    raw = make_raw(**{"Protein(g)": [10.123456, 20.0, 30.0, 40.0]})
    df = nutrition.clean_data(raw)
    records = nutrition.df_to_records(df)
    assert len(records) == 4
    assert list(records[0]) == ["Diet_type", "Recipe_name", "Cuisine_type",
                               "Protein(g)", "Carbs(g)", "Fat(g)"]
    assert records[0]["Protein(g)"] == 10.12
    # Ratio columns are deliberately not shipped to the client.
    assert "Protein_to_Carbs_ratio" not in records[0]


def test_df_to_records_uses_cleaned_values(clean):
    records = nutrition.df_to_records(clean)
    assert records[0]["Diet_type"] == "vegan"
    assert records[0]["Recipe_name"] == "Lentil Stew"
    assert records[0]["Cuisine_type"] == "indian"


def test_df_to_records_is_json_serializable(clean):
    records = nutrition.df_to_records(clean)
    text = json.dumps(records, allow_nan=False)
    assert json.loads(text) == records


def test_df_to_records_json_safe_with_messy_input():
    raw = pd.DataFrame({
        "Diet_type": ["vegan", None, "keto"],
        "Recipe_name": ["", "  B  ", None],
        "Cuisine_type": [None, "indian", ""],
        "Protein(g)": [-1.0, 20.0, np.nan],
        "Carbs(g)": [0.0, "oops", 20.0],
        "Fat(g)": [np.inf, 2.0, 4.0],
    })
    df = nutrition.clean_data(raw)
    records = nutrition.df_to_records(df)
    assert json.dumps(records, allow_nan=False)


def test_df_to_records_tolerates_missing_optional_columns(clean):
    trimmed = clean.drop(columns=["Cuisine_type"])
    records = nutrition.df_to_records(trimmed)
    assert "Cuisine_type" not in records[0]
    assert "Recipe_name" in records[0]
