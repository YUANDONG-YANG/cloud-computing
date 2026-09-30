"""Public Azurite emulator credentials, never production Azure secrets."""
import os

AZURITE_KEY = (
    "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/"
    "K1SZFPTOtr/KBHBeksoGMGw=="
)


def connection_string():
    host = os.getenv("AZURITE_HOST", "127.0.0.1")
    return os.getenv("AZURE_STORAGE_CONNECTION_STRING") or (
        "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;"
        f"AccountKey={AZURITE_KEY};"
        f"BlobEndpoint=http://{host}:10000/devstoreaccount1;"
    )
