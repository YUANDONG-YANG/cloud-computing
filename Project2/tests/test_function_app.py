"""HTTP handler tests for the Azure Functions v2 API.

The handlers run in-process: ``_load_dataset`` is monkeypatched so no Azure
Storage call is ever made, and requests are built with the azure-functions
test helper instead of going through the Functions host.
"""
import json

import azure.functions as func
import pandas as pd
import pytest

import function_app
from nutrition import clean_data

ROW_COUNT = 120
DIETS = ["keto", "vegan", "dash"]
CUISINES = ["american", "italian", "nordic"]


def raw_rows(count=ROW_COUNT):
    """Deterministic rows: ``Recipe 000``..``Recipe NNN`` cycling through DIETS."""
    return pd.DataFrame({
        "Diet_type": [DIETS[i % len(DIETS)] for i in range(count)],
        "Recipe_name": [f"Recipe {i:03d}" for i in range(count)],
        "Cuisine_type": [CUISINES[i % len(CUISINES)] for i in range(count)],
        "Protein(g)": [float(i + 1) for i in range(count)],
        "Carbs(g)": [float(count - i) for i in range(count)],
        "Fat(g)": [float(i % 7 + 1) for i in range(count)],
    })


def names(start, stop):
    return [f"Recipe {i:03d}" for i in range(start, stop)]


def user_function(route):
    """Return the plain callable behind an ``@app.route``-decorated handler."""
    target = getattr(function_app, route)
    builder = getattr(target, "build", None)
    if builder is None:
        return target
    try:
        return builder().get_user_function()
    except Exception:  # pragma: no cover - tolerates azure-functions variations
        return target


def call(route, **params):
    request = func.HttpRequest(
        method="GET",
        url=f"/api/{route}",
        params={key: str(value) for key, value in params.items()},
        body=None,
    )
    return user_function(route)(request)


def body(response):
    return json.loads(response.get_body())


@pytest.fixture
def dataset():
    return clean_data(raw_rows())


@pytest.fixture(autouse=True)
def no_storage(monkeypatch):
    """Any real Blob Storage client construction is a test failure."""
    class Forbidden:
        @staticmethod
        def from_connection_string(*args, **kwargs):
            raise AssertionError("handler reached Azure Blob Storage")

    monkeypatch.setattr(function_app, "BlobServiceClient", Forbidden)


@pytest.fixture(autouse=True)
def loaded_dataset(monkeypatch, dataset):
    monkeypatch.setattr(function_app, "_load_dataset", lambda: (dataset, False))
    return dataset


def test_health_is_served_without_touching_the_dataset(monkeypatch):
    def forbidden():
        raise AssertionError("/api/health must not load the dataset")

    monkeypatch.setattr(function_app, "_load_dataset", forbidden)
    response = call("health")
    assert response.status_code == 200
    payload = body(response)
    assert payload["status"] == "healthy"
    assert payload["service"] == "nutritional-insights-api"


def test_insights_returns_every_documented_section(loaded_dataset):
    response = call("insights")
    assert response.status_code == 200
    payload = body(response)
    for key in ("average_macros", "top_recipes", "common_cuisines",
                "total_protein_by_diet", "summary", "metadata"):
        assert key in payload, f"missing {key}"
    assert "execution_time_seconds" in payload["metadata"]
    assert payload["metadata"]["execution_time_seconds"] >= 0
    summary = payload["summary"]
    assert summary["total_recipes"] == len(loaded_dataset) == ROW_COUNT
    assert summary["diet_types"] == sorted(DIETS)
    assert sum(summary["diet_counts"].values()) == ROW_COUNT
    assert len(payload["average_macros"]) == len(DIETS)
    assert len(payload["total_protein_by_diet"]) == len(DIETS)
    assert len(payload["top_recipes"]) == 5 * len(DIETS)


def test_recipes_defaults_to_the_first_page_of_fifty(loaded_dataset):
    response = call("recipes")
    assert response.status_code == 200
    payload = body(response)
    assert payload["page"] == 1
    assert payload["limit"] == function_app.DEFAULT_PAGE_SIZE == 50
    assert payload["count"] == 50
    assert payload["total"] == ROW_COUNT
    assert payload["total_pages"] == 3
    assert payload["diet_type_filter"] == "all"
    assert [row["Recipe_name"] for row in payload["recipes"]] == names(0, 50)


def test_recipes_second_page_returns_the_expected_slice():
    payload = body(call("recipes", limit=5, page=2))
    assert payload["page"] == 2
    assert payload["limit"] == 5
    assert payload["total_pages"] == 24
    assert [row["Recipe_name"] for row in payload["recipes"]] == names(5, 10)


def test_limit_above_the_cap_is_clamped():
    payload = body(call("recipes", limit=5000))
    assert function_app.MAX_PAGE_SIZE == 500
    assert payload["limit"] == 500
    assert payload["total_pages"] == 1
    assert payload["count"] == ROW_COUNT


def test_page_beyond_the_last_page_clamps_instead_of_emptying():
    payload = body(call("recipes", page=99))
    assert payload["page"] == 3
    assert payload["total_pages"] == 3
    assert payload["count"] == 20
    assert [row["Recipe_name"] for row in payload["recipes"]] == names(100, 120)


@pytest.mark.parametrize("params", [
    {"page": "0"}, {"page": "-1"}, {"page": "abc"},
    {"limit": "0"}, {"limit": "-1"}, {"limit": "abc"},
])
def test_invalid_pagination_is_a_client_error(params):
    response = call("recipes", **params)
    assert response.status_code == 400
    assert "Invalid pagination parameter" in body(response)["error"]


@pytest.mark.parametrize("value", ["keto", "KETO", "Keto"])
def test_diet_type_filter_is_case_insensitive(value):
    payload = body(call("recipes", diet_type=value, limit=500))
    assert payload["total"] == ROW_COUNT // len(DIETS)
    assert payload["diet_type_filter"] == value
    assert {row["Diet_type"] for row in payload["recipes"]} == {"keto"}


def test_unknown_diet_type_is_not_found():
    response = call("recipes", diet_type="atkins")
    assert response.status_code == 404
    assert "atkins" in body(response)["error"]


@pytest.mark.parametrize("route", ["health", "insights", "recipes"])
def test_handlers_emit_no_cors_headers(route):
    """CORS is configured at the Function App host level only (see deploy.sh)."""
    response = call(route)
    assert response.status_code == 200
    leaked = [key for key in response.headers.keys()
              if key.lower().startswith("access-control-")]
    assert leaked == [], f"handler emitted host-level CORS headers: {leaked}"


@pytest.mark.parametrize("route", ["insights", "recipes"])
def test_internal_failures_return_500_without_leaking_details(route, monkeypatch):
    secret = "DefaultEndpointsProtocol=https;AccountName=acme;AccountKey=TOPSECRET=="

    def explode():
        raise RuntimeError(secret)

    monkeypatch.setattr(function_app, "_load_dataset", explode)
    response = call(route)
    assert response.status_code == 500
    text = response.get_body().decode()
    assert body(response)["error"]
    for fragment in ("AccountKey", "TOPSECRET", "AccountName", "RuntimeError", secret):
        assert fragment not in text
