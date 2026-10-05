"""Task 3: manually invoked serverless simulation using real Azurite Blob I/O."""
import io
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from azure.storage.blob import BlobServiceClient

from nutrition import average_macros, clean_data
from storage_config import connection_string

# Task 5 (warm path): state kept between invocations while the process stays alive.
# A cold start begins with both empty; a warm instance reuses them.
_shared_client = None
_last_run = {"etag": None, "target": None, "records": None}


def _client():
    """Create the Blob client once per process instead of once per invocation."""
    global _shared_client
    if _shared_client is None:
        _shared_client = BlobServiceClient.from_connection_string(connection_string())
    return _shared_client


def process_nutritional_data_from_azurite(
    output_path="simulated_nosql/results.json", service_client=None
):
    client = service_client or _client()
    blob = client.get_blob_client(container="datasets", blob="All_Diets.csv")
    target = Path(output_path)

    # Task 5: asking for the ETag is one small request; downloading and processing
    # the CSV is the expensive part. Skip it when the CSV has not changed.
    etag = blob.get_blob_properties().etag
    if (etag == _last_run["etag"] and target == _last_run["target"] and target.exists()):
        print(f"{datetime.now(timezone.utc).isoformat()} "
              f"datasets/All_Diets.csv unchanged (ETag {etag}); "
              f"reused {len(_last_run['records'])} stored diet documents in {target}")
        return _last_run["records"]

    download = blob.download_blob()
    raw = pd.read_csv(io.BytesIO(download.readall()))
    df = clean_data(raw)
    records = average_macros(df).reset_index().to_dict(orient="records")
    target.parent.mkdir(parents=True, exist_ok=True)
    # Atomic replacement prevents interrupted writes leaving a partial database.
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=target.parent,
                                         delete=False, encoding="utf-8") as handle:
            temp_name = handle.name
            json.dump(records, handle, indent=2, allow_nan=False)
        # Temp files are 0600; make the result readable by the host user (e.g. CI runner).
        os.chmod(temp_name, 0o644)
        os.replace(temp_name, target)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)
    # Remember the ETag of the bytes actually processed, so a change made between
    # the check above and the download is still picked up next time.
    _last_run.update(etag=download.properties.etag, target=target, records=records)
    print(f"{datetime.now(timezone.utc).isoformat()} "
          f"Processed {len(df)} recipes from datasets/All_Diets.csv; "
          f"stored {len(records)} diet documents in {target}")
    return records


if __name__ == "__main__":
    process_nutritional_data_from_azurite()
