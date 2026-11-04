"""Stage 1 contracts: search, correlation, clustering and local file loading."""
import json

import azure.functions as func
import numpy as np
import pandas as pd
import pytest

import function_app as api
from clustering import kmeans
from nutrition import MACROS, clean_data


def frame():
    return pd.DataFrame({
        "Diet_type": ["keto", "keto", "vegan", "vegan"],
        "Recipe_name": ["Soup [A]", "Soup B", "Rice", "Beans"],
        "Cuisine_type": ["italian"] * 4,
        "Protein(g)": [1, 2, 10, 12],
        "Carbs(g)": [2, 4, 20, 24],
        "Fat(g)": [1, 1, 1, 1],
    })


def call(route, **params):
    request = func.HttpRequest(method="GET", url=f"/api/{route}",
                               params={k: str(v) for k, v in params.items()}, body=None)
    response = getattr(api, route).build().get_user_function()(request)
    return response.status_code, json.loads(response.get_body())


@pytest.fixture
def loaded(monkeypatch):
    df = clean_data(frame())
    monkeypatch.setattr(api, "_load_dataset", lambda: (df, False))
    return df


def test_search_is_literal_and_combines_with_filter(loaded):
    status, payload = call("recipes", search="[a]", diet_type="KETO", limit=1)
    assert status == 200 and payload["total"] == 1
    assert payload["recipes"][0]["Recipe_name"] == "Soup [A]"
    assert call("recipes", search="no match")[1]["recipes"] == []
    assert call("recipes", search="ITALIAN")[1]["total"] == 4


def test_correlation_values_and_undefined_constant_column(loaded):
    status, payload = call("insights")
    assert status == 200
    assert payload["correlation"]["Protein(g)"]["Carbs(g)"] == 1
    assert payload["correlation"]["Fat(g)"]["Fat(g)"] is None
    assert payload["summary"]["diet_counts"] == {"keto": 2, "vegan": 2}


def test_kmeans_finds_two_separated_groups_reproducibly():
    values = np.array([[0, 0], [0, 1], [10, 10], [10, 11]])
    labels, centers, _ = kmeans(values, k=2)
    assert labels[0] == labels[1] and labels[2] == labels[3]
    assert labels[0] != labels[2]
    assert np.array_equal(labels, kmeans(values, k=2)[0])
    assert sorted(centers[:, 0]) == [0, 10]


def test_clusters_contract_and_constant_features(loaded):
    status, payload = call("clusters", k=2)
    assert status == 200 and len(payload["points"]) == 4
    assert sum(payload["cluster_counts"].values()) == 4
    assert len(payload["centroids"]) == 2
    assert payload["features"] == MACROS
    assert all(row["Fat(g)"] == 1 for row in payload["centroids"])


@pytest.mark.parametrize("k", ["abc", "0", "-1", "11", "5"])
def test_invalid_cluster_count(loaded, k):
    assert call("clusters", k=k)[0] == 400


def test_local_csv_cache_and_refresh(tmp_path, monkeypatch):
    path = tmp_path / "recipes.csv"
    raw = frame()
    raw.to_csv(path, index=False)
    monkeypatch.setenv("DATASET_PATH", str(path))
    monkeypatch.setattr(api, "_cache", {"etag": None, "frame": None})
    assert api._load_dataset()[1] is False
    assert api._load_dataset()[1] is True
    raw.iloc[:2].to_csv(path, index=False)
    updated, hit = api._load_dataset()
    assert not hit and len(updated) == 2
