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


def process_nutritional_data_from_azurite(
    output_path="simulated_nosql/results.json", service_client=None
):
    owned = service_client is None
    client = service_client or BlobServiceClient.from_connection_string(connection_string())
    try:
        blob = client.get_blob_client(container="datasets", blob="All_Diets.csv")
        raw = pd.read_csv(io.BytesIO(blob.download_blob().readall()))
        df = clean_data(raw)
        records = average_macros(df).reset_index().to_dict(orient="records")
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Atomic replacement prevents interrupted writes leaving a partial database.
        temp_name = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", dir=target.parent,
                                             delete=False, encoding="utf-8") as handle:
                temp_name = handle.name
                json.dump(records, handle, indent=2, allow_nan=False)
            os.replace(temp_name, target)
        finally:
            if temp_name and os.path.exists(temp_name):
                os.unlink(temp_name)
        print(f"{datetime.now(timezone.utc).isoformat()} "
              f"Processed {len(df)} recipes from datasets/All_Diets.csv; "
              f"stored {len(records)} diet documents in {target}")
        return records
    finally:
        if owned:
            client.close()


if __name__ == "__main__":
    process_nutritional_data_from_azurite()
