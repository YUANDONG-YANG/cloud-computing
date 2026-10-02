"""Azure Functions v2 HTTP API for Nutritional Insights Dashboard.

Endpoints:
    GET /api/health   -- health check
    GET /api/insights -- average macros, top recipes, common cuisines, summary stats
    GET /api/recipes  -- all recipes (optional ?diet_type= filter)
"""
import io
import json
import logging
import os
import time

import azure.functions as func
import pandas as pd
from azure.storage.blob import BlobServiceClient

from nutrition import average_macros, clean_data, common_cuisines, top_recipes

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_connection_string():
    """Return the Azure Storage connection string from environment."""
    return os.environ.get(
        "AZURE_STORAGE_CONNECTION_STRING",
        os.environ.get("AzureWebJobsStorage", "UseDevelopmentStorage=true"),
    )


def _get_blob_csv():
    """Download All_Diets.csv from Azure Blob Storage and return a DataFrame."""
    conn_str = _get_connection_string()
    container = os.environ.get("BLOB_CONTAINER_NAME", "datasets")
    blob_name = os.environ.get("BLOB_NAME", "All_Diets.csv")

    client = BlobServiceClient.from_connection_string(conn_str)
    try:
        blob_client = client.get_blob_client(container=container, blob=blob_name)
        data = blob_client.download_blob().readall()
        return pd.read_csv(io.BytesIO(data))
    finally:
        client.close()


def _json_response(body, status_code=200):
    """Return an HTTP response with JSON body and CORS headers."""
    return func.HttpResponse(
        body=json.dumps(body, allow_nan=False, default=str),
        status_code=status_code,
        mimetype="application/json",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        },
    )


def _error_response(message, status_code=500):
    """Return a JSON error response."""
    return _json_response({"error": message}, status_code)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.route(route="health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    """Health check endpoint."""
    return _json_response({
        "status": "healthy",
        "service": "nutritional-insights-api",
        "version": "2.0.0",
    })


@app.route(route="insights", methods=["GET"])
def insights(req: func.HttpRequest) -> func.HttpResponse:
    """Return aggregate nutritional insights: averages, top recipes, common cuisines."""
    start = time.time()
    try:
        raw = _get_blob_csv()
        df = clean_data(raw)

        # Average macros per diet
        avg = average_macros(df)
        avg_records = avg.reset_index().to_dict(orient="records")
        for rec in avg_records:
            for key in ["Protein(g)", "Carbs(g)", "Fat(g)"]:
                rec[key] = round(rec[key], 2)

        # Top 5 highest-protein recipes per diet
        top = top_recipes(df)
        top_records = (
            top[["Diet_type", "Recipe_name", "Cuisine_type",
                 "Protein(g)", "Carbs(g)", "Fat(g)"]]
            .to_dict(orient="records")
        )

        # Most common cuisine per diet
        cuisines = common_cuisines(df)
        cuisine_records = cuisines.to_dict(orient="records")

        # Total protein per diet
        totals = df.groupby("Diet_type")["Protein(g)"].sum()
        total_records = [
            {"Diet_type": dt, "Total_Protein(g)": round(val, 2)}
            for dt, val in totals.items()
        ]

        # Recipe count per diet
        diet_counts = df["Diet_type"].value_counts().to_dict()

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

        elapsed = round(time.time() - start, 3)

        return _json_response({
            "average_macros": avg_records,
            "top_recipes": top_records,
            "common_cuisines": cuisine_records,
            "total_protein_by_diet": total_records,
            "summary": summary,
            "metadata": {
                "execution_time_seconds": elapsed,
                "source": "Azure Blob Storage",
                "dataset": "All_Diets.csv",
            },
        })
    except Exception as e:
        logging.exception("Error in /api/insights")
        return _error_response(str(e))


@app.route(route="recipes", methods=["GET"])
def recipes(req: func.HttpRequest) -> func.HttpResponse:
    """Return recipe data, optionally filtered by diet_type query parameter."""
    start = time.time()
    try:
        raw = _get_blob_csv()
        df = clean_data(raw)

        # Optional diet_type filter
        diet_type = req.params.get("diet_type")
        if diet_type and diet_type.lower() != "all":
            df = df[df["Diet_type"].str.lower() == diet_type.lower()]
            if df.empty:
                return _error_response(
                    f"No recipes found for diet type: {diet_type}", 404
                )

        # Limit columns for the response
        cols = ["Diet_type", "Recipe_name", "Cuisine_type",
                "Protein(g)", "Carbs(g)", "Fat(g)"]
        records = df[cols].to_dict(orient="records")

        elapsed = round(time.time() - start, 3)

        return _json_response({
            "recipes": records,
            "count": len(records),
            "diet_type_filter": diet_type or "all",
            "metadata": {
                "execution_time_seconds": elapsed,
                "source": "Azure Blob Storage",
                "dataset": "All_Diets.csv",
            },
        })
    except Exception as e:
        logging.exception("Error in /api/recipes")
        return _error_response(str(e))
