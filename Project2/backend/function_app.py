"""Azure Functions v2 HTTP API for Nutritional Insights Dashboard.

Endpoints:
    GET /api/health   -- liveness check (no storage call)
    GET /api/insights -- average macros, top recipes, common cuisines, summary stats
    GET /api/recipes  -- recipe rows; optional ?diet_type=, ?page=, ?limit=

CORS is configured at the Function App host level (see deploy.sh), so this
module deliberately does not emit Access-Control-Allow-* headers itself --
doing both produces duplicate headers, which browsers reject.
"""
import io
import json
import logging
import os
import threading
import time

import azure.functions as func
import pandas as pd
from azure.storage.blob import BlobServiceClient

from nutrition import average_macros, clean_data, common_cuisines, top_recipes

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 500

RESPONSE_COLUMNS = ["Diet_type", "Recipe_name", "Cuisine_type",
                    "Protein(g)", "Carbs(g)", "Fat(g)"]

# Cleaned dataset cache, keyed by the blob ETag so a re-uploaded CSV is picked
# up automatically. A worker handles requests concurrently, hence the lock.
_cache = {"etag": None, "frame": None}
_cache_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_connection_string():
    """Return the Azure Storage connection string from environment."""
    return os.environ.get(
        "AZURE_STORAGE_CONNECTION_STRING",
        os.environ.get("AzureWebJobsStorage", "UseDevelopmentStorage=true"),
    )


def _load_dataset():
    """Return the cleaned dataset, downloading from Blob Storage on a cache miss.

    The blob ETag is checked on every request (a cheap metadata call) and the
    CSV is only re-downloaded and re-cleaned when it has actually changed.
    """
    container = os.environ.get("BLOB_CONTAINER_NAME", "datasets")
    blob_name = os.environ.get("BLOB_NAME", "All_Diets.csv")

    client = BlobServiceClient.from_connection_string(_get_connection_string())
    try:
        blob_client = client.get_blob_client(container=container, blob=blob_name)
        etag = blob_client.get_blob_properties().etag

        with _cache_lock:
            if _cache["etag"] == etag and _cache["frame"] is not None:
                return _cache["frame"], True

        data = blob_client.download_blob().readall()
        frame = clean_data(pd.read_csv(io.BytesIO(data)))

        with _cache_lock:
            _cache["etag"] = etag
            _cache["frame"] = frame
        return frame, False
    finally:
        client.close()


def _json_response(body, status_code=200):
    """Return an HTTP response with a JSON body."""
    return func.HttpResponse(
        body=json.dumps(body, allow_nan=False, default=str),
        status_code=status_code,
        mimetype="application/json",
    )


def _error_response(message, status_code=500):
    """Return a JSON error response.

    Internal exception text is logged, never returned, so storage details
    cannot leak to the browser.
    """
    return _json_response({"error": message}, status_code)


def _positive_int(raw, default, maximum=None):
    """Parse a positive integer query parameter, raising ValueError when invalid."""
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ValueError(f"expected a positive integer, got {raw!r}")
    if value < 1:
        raise ValueError(f"expected a positive integer, got {raw!r}")
    if maximum is not None:
        value = min(value, maximum)
    return value


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.route(route="health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    """Liveness check. Does not touch storage, so it stays fast and cheap."""
    return _json_response({
        "status": "healthy",
        "service": "nutritional-insights-api",
        "version": "2.0.0",
        "dataset_cached": _cache["frame"] is not None,
    })


@app.route(route="insights", methods=["GET"])
def insights(req: func.HttpRequest) -> func.HttpResponse:
    """Return aggregate nutritional insights: averages, top recipes, common cuisines."""
    start = time.time()
    try:
        df, cache_hit = _load_dataset()

        # Average macros per diet
        avg = average_macros(df)
        avg_records = avg.reset_index().to_dict(orient="records")
        for rec in avg_records:
            for key in ["Protein(g)", "Carbs(g)", "Fat(g)"]:
                rec[key] = round(rec[key], 2)

        # Top 5 highest-protein recipes per diet
        top = top_recipes(df)
        top_records = top[RESPONSE_COLUMNS].to_dict(orient="records")

        # Most common cuisine per diet
        cuisine_records = common_cuisines(df).to_dict(orient="records")

        # Total protein per diet
        totals = df.groupby("Diet_type")["Protein(g)"].sum()
        total_records = [
            {"Diet_type": dt, "Total_Protein(g)": round(float(val), 2)}
            for dt, val in totals.items()
        ]

        # Recipe count per diet
        diet_counts = {str(k): int(v) for k, v in df["Diet_type"].value_counts().items()}

        # Summary statistics
        summary = {
            "total_recipes": len(df),
            "diet_types": sorted(df["Diet_type"].unique().tolist()),
            "diet_counts": diet_counts,
            "highest_mean_protein_diet": avg["Protein(g)"].idxmax(),
            "highest_mean_protein_g": round(float(avg["Protein(g)"].max()), 2),
            "highest_total_protein_diet": totals.idxmax(),
            "highest_total_protein_g": round(float(totals.max()), 2),
        }

        return _json_response({
            "average_macros": avg_records,
            "top_recipes": top_records,
            "common_cuisines": cuisine_records,
            "total_protein_by_diet": total_records,
            "summary": summary,
            "metadata": {
                "execution_time_seconds": round(time.time() - start, 3),
                "source": "Azure Blob Storage",
                "dataset": os.environ.get("BLOB_NAME", "All_Diets.csv"),
                "dataset_from_cache": cache_hit,
            },
        })
    except Exception:
        logging.exception("Error in /api/insights")
        return _error_response("Failed to compute insights from the dataset.")


@app.route(route="recipes", methods=["GET"])
def recipes(req: func.HttpRequest) -> func.HttpResponse:
    """Return a page of recipe rows, optionally filtered by diet_type.

    Query parameters:
        diet_type -- filter to one diet ("all" or omitted returns every diet)
        page      -- 1-based page number (default 1)
        limit     -- rows per page, capped at MAX_PAGE_SIZE (default 50)
    """
    start = time.time()
    try:
        page = _positive_int(req.params.get("page"), 1)
        limit = _positive_int(req.params.get("limit"), DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE)
    except ValueError as exc:
        return _error_response(f"Invalid pagination parameter: {exc}", 400)

    try:
        df, cache_hit = _load_dataset()

        diet_type = req.params.get("diet_type")
        if diet_type and diet_type.lower() != "all":
            df = df[df["Diet_type"].str.lower() == diet_type.lower()]
            if df.empty:
                return _error_response(
                    f"No recipes found for diet type: {diet_type}", 404
                )

        total = len(df)
        total_pages = max(1, -(-total // limit))  # ceiling division
        page = min(page, total_pages)
        offset = (page - 1) * limit

        records = df[RESPONSE_COLUMNS].iloc[offset:offset + limit].to_dict(orient="records")

        return _json_response({
            "recipes": records,
            "count": len(records),
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "diet_type_filter": diet_type or "all",
            "metadata": {
                "execution_time_seconds": round(time.time() - start, 3),
                "source": "Azure Blob Storage",
                "dataset": os.environ.get("BLOB_NAME", "All_Diets.csv"),
                "dataset_from_cache": cache_hit,
            },
        })
    except Exception:
        logging.exception("Error in /api/recipes")
        return _error_response("Failed to read recipes from the dataset.")
