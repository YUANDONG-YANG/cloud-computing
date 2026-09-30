"""Upload the course CSV to the local Azurite datasets container."""
import argparse
from datetime import datetime, timezone
from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import BlobServiceClient
from storage_config import connection_string


def upload(path):
    with BlobServiceClient.from_connection_string(connection_string()) as client:
        container = client.get_container_client("datasets")
        try:
            container.create_container()
        except ResourceExistsError:
            pass
        with open(path, "rb") as source:
            container.upload_blob("All_Diets.csv", source, overwrite=True)
        for blob in container.list_blobs():
            print(f"{datetime.now(timezone.utc).isoformat()} "
                  f"Uploaded datasets/{blob.name}: {blob.size} bytes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default="data/All_Diets.csv")
    upload(parser.parse_args().csv)
