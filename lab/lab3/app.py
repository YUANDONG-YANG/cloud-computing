"""CPSY 300 Lab 03 - Uber traffic analysis and prediction API.

The Uber-Jan-Feb-FOIL.csv supplied on Brightspace is aggregated per day and
dispatching base (columns: dispatching_base_number, date, active_vehicles,
trips). The handout's code assumes an event-level 'Date/Time' column, so this
script accepts either schema and weights every row by its 'trips' value.

Usage:
    python app.py --analyze   # Subtasks 1.1 / 1.2: preprocessing output and plots
    python app.py             # Flask API on port 5000 (gunicorn in Docker)
"""
import json
import os
import sys
from datetime import datetime, timezone

import pandas as pd
from flask import Flask, jsonify, request

app = Flask(__name__)


@app.after_request
def response_evidence_metadata(response):
    """Expose real request provenance and UTC response time for lab evidence."""
    if response.is_json:
        payload = response.get_json()
        if isinstance(payload, dict):
            payload["served_at_utc"] = datetime.now(timezone.utc).isoformat()
            payload["request_url"] = request.url
            response.set_data(json.dumps(payload, indent=2))
    return response

# ---------------------------------------------------------------------------
# Subtask 1.1 - Data preprocessing and exploration
# ---------------------------------------------------------------------------
df = pd.read_csv(os.getenv("DATA_PATH", "Uber-Jan-Feb-FOIL.csv"))

# Remove rows with missing values and duplicate records
df.dropna(inplace=True)
df.drop_duplicates(inplace=True)

# Convert the date column to datetime ('Date/Time' in the handout, 'date' in the supplied file)
DATE_COL = "Date/Time" if "Date/Time" in df.columns else "date"
df[DATE_COL] = pd.to_datetime(df[DATE_COL])

# Feature extraction
df["Hour"] = df[DATE_COL].dt.hour
df["Day"] = df[DATE_COL].dt.date
df["DayOfWeek"] = df[DATE_COL].dt.day_name()
df["IsWeekend"] = df["DayOfWeek"].isin(["Saturday", "Sunday"])

# Each aggregate row represents many trips; event-level rows represent one trip
df["Trips"] = df["trips"] if "trips" in df.columns else 1

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


# ---------------------------------------------------------------------------
# Subtask 1.2 - Analyze traffic patterns
# ---------------------------------------------------------------------------
def run_analysis(output_dir="plots"):
    import matplotlib
    if "--no-show" in sys.argv or (not os.getenv("DISPLAY") and sys.platform != "darwin"):
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns

    pd.set_option("display.width", 160)
    pd.set_option("display.max_columns", 20)
    captured_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print("Analysis executed at:", captured_at)
    print("Source granularity:", "daily aggregate" if DATE_COL == "date" else "event timestamp")
    print("=== df.head() ===")
    print(df.head())
    print("\n=== df.info() ===")
    df.info()
    print("\n=== df.describe() ===")
    print(df.describe())

    # Aggregate trips by day and by hour (weighted by trips)
    daily_trips = df.groupby("Day")["Trips"].sum()
    hourly_trips = df.groupby("Hour")["Trips"].sum()
    dow_avg = daily_trips.groupby(pd.to_datetime(daily_trips.index).day_name()).mean().reindex(DAY_ORDER)

    print("\n=== Daily trips (top 5) ===")
    print(daily_trips.sort_values(ascending=False).head())
    print("\n=== Hourly trips ===")
    print(hourly_trips)
    print("\nBusiest day:", daily_trips.idxmax(), "with", int(daily_trips.max()), "trips")
    if DATE_COL == "date":
        print("Peak hour: unavailable. Hour=0 is a date-parsing placeholder, not an observed pickup hour.")
    else:
        print("Peak hour:", hourly_trips.idxmax())
    print("Busiest day of week (avg trips/day):", dow_avg.idxmax(), round(dow_avg.max()))
    print("\n=== Average trips per day by day of week ===")
    print(dow_avg.round(0))

    os.makedirs(output_dir, exist_ok=True)

    fig, ax = plt.subplots(figsize=(14, 5))
    daily_trips.plot(kind="bar", ax=ax, color="#1e5eff")
    ax.set_title("Total Trips by Day (Jan-Feb 2015)")
    ax.set_xlabel("Day")
    ax.set_ylabel("Trips")
    ax.set_xticks(range(0, len(daily_trips), 3))
    ax.set_xticklabels([str(d) for d in daily_trips.index[::3]], rotation=60)
    fig.tight_layout()
    fig.text(0.99, 0.005, "Generated: " + captured_at, ha="right", fontsize=8)
    fig.savefig(f"{output_dir}/daily_trips.png", dpi=120)

    fig, ax = plt.subplots(figsize=(8, 5))
    hourly_trips.plot(kind="bar", ax=ax, color="#09a6b8")
    ax.set_title("Hour placeholder totals — not observed hourly demand" if DATE_COL == "date" else "Total Trips by Hour")
    ax.set_xlabel("Hour")
    ax.set_ylabel("Trips")
    fig.tight_layout()
    fig.text(0.99, 0.005, "Generated: " + captured_at, ha="right", fontsize=8)
    fig.savefig(f"{output_dir}/hourly_trips.png", dpi=120)

    # Heatmap from the handout: day of week x hour
    heatmap_data = df.groupby(["DayOfWeek", "Hour"])["Trips"].sum().unstack().reindex(DAY_ORDER)
    fig = plt.figure(figsize=(7, 5))
    sns.heatmap(heatmap_data, cmap="viridis", annot=True, fmt=".0f")
    plt.title("Weekday × Hour (0 = date placeholder)" if DATE_COL == "date" else "Trip Frequency by Day and Hour")
    fig.tight_layout()
    fig.text(0.99, 0.005, "Generated: " + captured_at, ha="right", fontsize=8)
    fig.savefig(f"{output_dir}/heatmap_day_hour.png", dpi=120)

    # Supplementary heatmap that carries information for daily data: day of week x base
    base_heatmap = (df.groupby(["DayOfWeek", "dispatching_base_number"])["Trips"].sum()
                    .unstack().reindex(DAY_ORDER)) if "dispatching_base_number" in df.columns else None
    if base_heatmap is not None:
        fig = plt.figure(figsize=(10, 5))
        sns.heatmap(base_heatmap, cmap="viridis", annot=True, fmt=".0f")
        plt.title("Trip Frequency by Day of Week and Dispatching Base")
        fig.tight_layout()
        fig.text(0.99, 0.005, "Generated: " + captured_at, ha="right", fontsize=8)
        fig.savefig(f"{output_dir}/heatmap_day_base.png", dpi=120)

    print(f"\nPlots saved to {output_dir}/")
    if "--no-show" not in sys.argv and (sys.platform == "darwin" or os.getenv("DISPLAY")):
        plt.show()
    plt.close("all")


# ---------------------------------------------------------------------------
# Subtasks 4.1 / 4.2 - Redis cache (local container or Azure Cache for Redis)
# ---------------------------------------------------------------------------
CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))  # 1 hour
_redis_client = None


def get_redis():
    """Connect lazily; REDIS_HOST unset means caching is disabled."""
    global _redis_client
    if _redis_client is None and os.getenv("REDIS_HOST"):
        import redis
        try:
            client = redis.Redis(
                host=os.getenv("REDIS_HOST"),                 # Azure: <name>.redis.cache.windows.net
                port=int(os.getenv("REDIS_PORT", "6379")),   # Azure: 6380 (SSL)
                password=os.getenv("REDIS_PASSWORD") or None,
                ssl=os.getenv("REDIS_SSL", "false").lower() == "true",
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
            )
            client.ping()
            _redis_client = client
        except Exception as exc:
            app.logger.warning("Redis unavailable: %s", exc)
    return _redis_client


def predict(timestamp):
    """Predict trips for the timestamp's day from the historical mean of the same weekday."""
    parsed = pd.to_datetime(timestamp)
    daily = df.groupby("Day")["Trips"].sum()
    weekday_avg = daily.groupby(pd.to_datetime(daily.index).day_name()).mean()
    day_name = parsed.day_name()
    actual = daily.get(parsed.date())
    return {
        "timestamp": parsed.isoformat(),
        "day_of_week": day_name,
        "predicted_trips": round(float(weekday_avg[day_name]), 2),
        "actual_trips": int(actual) if actual is not None else None,
        "model": "mean daily trips for the same day of week",
    }


@app.get("/")
def health():
    return jsonify({
        "service": "uber-traffic-api",
        "status": "ok",
        "rows": int(len(df)),
        "cache": "enabled" if get_redis() else "disabled",
    })


@app.get("/predict_traffic")
def predict_traffic():
    timestamp = request.args.get("timestamp")
    if not timestamp:
        return jsonify({"error": "timestamp query parameter is required"}), 400

    key = f"predict:{timestamp}"  # the request timestamp is the cache key
    client = get_redis()
    if client:
        try:
            cached = client.get(key)
            if cached:
                return jsonify({**json.loads(cached), "source": "cache"})
        except Exception as exc:
            app.logger.warning("Redis GET failed: %s", exc)

    try:
        result = predict(timestamp)
    except (ValueError, TypeError):
        return jsonify({"error": f"invalid timestamp: {timestamp}"}), 400

    if client:
        try:
            client.setex(key, CACHE_TTL, json.dumps(result))
        except Exception as exc:
            app.logger.warning("Redis SET failed: %s", exc)
    return jsonify({**result, "source": "computed"})


@app.get("/analysis")
def analysis():
    daily = df.groupby("Day")["Trips"].sum()
    return jsonify({
        "rows_after_cleaning": int(len(df)),
        "total_trips": int(df["Trips"].sum()),
        "busiest_day": {"date": str(daily.idxmax()), "trips": int(daily.max())},
    })


if __name__ == "__main__":
    if "--analyze" in sys.argv:
        run_analysis()
    else:
        app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
