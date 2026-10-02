"""Public Azurite emulator credentials, never production Azure secrets."""
import os
from urllib.parse import urlparse

AZURITE_KEY = (
    "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/"
    "K1SZFPTOtr/KBHBeksoGMGw=="
)

LOCAL_HOSTS = {"127.0.0.1", "localhost", "azurite"}


def connection_string():
    host = os.getenv("AZURITE_HOST", "127.0.0.1")
    value = os.getenv("AZURE_STORAGE_CONNECTION_STRING") or (
        "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;"
        f"AccountKey={AZURITE_KEY};"
        f"BlobEndpoint=http://{host}:10000/devstoreaccount1;"
    )
    if value.strip().rstrip(";") == "UseDevelopmentStorage=true":
        return value
    parts = dict(p.split("=", 1) for p in value.split(";") if "=" in p)
    # Guard: this project only simulates Azure, so never talk to a real storage account.
    if urlparse(parts.get("BlobEndpoint", "")).hostname not in LOCAL_HOSTS:
        raise ValueError("Refusing non-local Blob endpoint; only Azurite is allowed")
    return value
