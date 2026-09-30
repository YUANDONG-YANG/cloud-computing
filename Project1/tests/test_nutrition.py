import json
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from lambda_function import process_nutritional_data_from_azurite
from nutrition import average_macros, clean_data, common_cuisines, top_recipes


def sample():
    return pd.DataFrame({
        "Diet_type": [" Paleo ", "paleo", "VEGAN"],
        "Recipe_name": ["A", "B", "C"],
        "Cuisine_type": [" Italian ", "ITALIAN", "Indian"],
        "Protein(g)": [10, None, 30], "Carbs(g)": [0, 20, 10],
        "Fat(g)": [5, 0, 10],
    })


def test_cleaning_and_mean_imputation():
    raw = sample()
    df = clean_data(raw)
    assert df["Diet_type"].tolist() == ["paleo", "paleo", "vegan"]
    assert df["Cuisine_type"].tolist() == ["italian", "italian", "indian"]
    assert df["Protein(g)"].tolist() == [10, 20, 30]
    assert pd.isna(raw.loc[1, "Protein(g)"])  # input is not mutated
    assert average_macros(df).loc["paleo", "Protein(g)"] == 15


def test_zero_denominators_are_undefined_not_infinity():
    df = clean_data(sample())
    assert pd.isna(df.loc[0, "Protein_to_Carbs_ratio"])
    assert pd.isna(df.loc[1, "Carbs_to_Fat_ratio"])
    assert df.loc[2, "Protein_to_Carbs_ratio"] == 3
    assert not np.isinf(df.select_dtypes("number").to_numpy()).any()


def test_invalid_numbers_and_missing_labels():
    raw = sample()
    raw["Protein(g)"] = ["bad", -1, 12]
    raw["Carbs(g)"] = [np.inf, 4, 8]
    raw.loc[0, "Diet_type"] = " "
    raw.loc[1, "Cuisine_type"] = None
    df = clean_data(raw)
    assert df["Protein(g)"].tolist() == [12, 12, 12]
    assert df.loc[0, "Carbs(g)"] == 6
    assert df.loc[0, "Diet_type"] == "unknown"
    assert df.loc[1, "Cuisine_type"] == "unknown"


@pytest.mark.parametrize("kind", ["empty", "missing_column", "all_invalid"])
def test_unusable_input_is_rejected(kind):
    raw = sample()
    if kind == "empty":
        raw = raw.iloc[:0]
    elif kind == "missing_column":
        raw = raw.drop(columns="Fat(g)")
    else:
        raw["Fat(g)"] = np.nan
    with pytest.raises(ValueError):
        clean_data(raw)


def test_top_five_per_diet_and_stable_ties():
    raw = pd.concat([sample().iloc[[0]]] * 7, ignore_index=True)
    raw["Protein(g)"] = [1, 9, 9, 8, 7, 6, 5]
    raw["Recipe_name"] = list("ABCDEFG")
    top = top_recipes(clean_data(raw))
    assert top["Recipe_name"].tolist() == list("BCDEF")


def test_cuisine_mode_preserves_ties():
    raw = sample()
    raw.loc[1, "Cuisine_type"] = "French"
    result = common_cuisines(clean_data(raw))
    assert set(result.loc[result.Diet_type == "paleo", "Cuisine_type"]) == {"italian", "french"}


def test_function_downloads_and_writes_valid_json(tmp_path):
    service = MagicMock()
    service.get_blob_client.return_value.download_blob.return_value.readall.return_value = (
        sample().to_csv(index=False).encode())
    path = tmp_path / "new" / "results.json"
    result = process_nutritional_data_from_azurite(path, service)
    service.get_blob_client.assert_called_once_with(container="datasets", blob="All_Diets.csv")
    assert json.loads(path.read_text()) == result
    assert result[0] == {"Diet_type": "paleo", "Protein(g)": 15.0, "Carbs(g)": 10.0, "Fat(g)": 2.5}
    assert len(list(path.parent.iterdir())) == 1


def test_failed_download_preserves_existing_results(tmp_path):
    path = tmp_path / "results.json"
    path.write_text('[{"existing": true}]')
    service = MagicMock()
    service.get_blob_client.return_value.download_blob.side_effect = RuntimeError("unavailable")
    with pytest.raises(RuntimeError, match="unavailable"):
        process_nutritional_data_from_azurite(path, service)
    assert json.loads(path.read_text()) == [{"existing": True}]
