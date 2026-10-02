"""Shared test setup for the Project 3 (Phase 3) backend.

Two things have to happen before any test module is imported:

1. ``Project3/backend`` has to be importable, because the backend modules
   import each other by bare name (``import cache``) the way the Azure
   Functions host loads them.
2. ``JWT_SECRET`` has to be in the environment, because ``auth.py`` reads it
   at import time and would otherwise fall back to its development key.

conftest.py is imported before the test modules, so doing it here is enough.
"""
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

# Deterministic signing key for the auth tests.  Set before `import auth`.
TEST_JWT_SECRET = "unit-test-secret-not-a-real-key"
os.environ["JWT_SECRET"] = TEST_JWT_SECRET
os.environ["JWT_EXPIRY_HOURS"] = "24"

# auth.py raises when JWT_SECRET is unset *and* this is set; keep it clear so
# the import path under test is the same one `func start` takes.
os.environ.pop("WEBSITE_INSTANCE_ID", None)

# cache.py must never reach a real Redis or a real Cosmos account.
for _var in ("REDIS_HOST", "REDIS_PASSWORD", "COSMOS_ENDPOINT", "COSMOS_KEY"):
    os.environ.pop(_var, None)
