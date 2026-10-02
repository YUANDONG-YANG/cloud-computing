#!/usr/bin/env bash
###############################################################################
# Project 3 (Phase 3) — Azure Deployment Script
#
# Provisions all required Azure resources and deploys the application:
#   - Resource Group
#   - Storage Account (Blob containers: raw-data, clean-data; static website)
#   - Cosmos DB (SQL API, serverless, encrypted at rest)
#   - Azure Functions (Python, Consumption plan)
#
# Cost: this stays inside a student credit. Cosmos is provisioned serverless,
# so it bills per request rather than for reserved throughput, and the
# Functions Consumption plan and Blob storage are effectively free at this
# scale. Azure Cache for Redis is NOT provisioned: it has no free tier, and
# the rubric allows "an external cache (like Redis) or a database (like
# Cosmos)". The code uses Redis only when REDIS_HOST is set.
#
# Billing is per hour and per request, so DELETE THE RESOURCE GROUP once the
# demo is recorded -- see teardown.sh.
#
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh
#
# Prerequisites:
#   - Azure CLI (az) installed and logged in
#   - Azure Functions Core Tools (func) installed
###############################################################################

set -euo pipefail

# A second `trap ... EXIT` replaces the first rather than adding to it, so every
# temporary path registers with this single handler instead of installing its
# own trap.  Each entry is a path from mktemp, never a bare variable.
CLEANUP_PATHS=()
cleanup() {
  local path
  for path in ${CLEANUP_PATHS[@]+"${CLEANUP_PATHS[@]}"}; do
    [[ -n "$path" && "$path" == "${TMPDIR:-/tmp}"/* ]] && rm -rf -- "$path"
  done
  return 0
}
cleanup_add() { CLEANUP_PATHS+=("$1"); }
trap cleanup EXIT

# Every path below is relative to the project directory, so anchor there rather
# than depending on where the script was invoked from.
cd "$(dirname "${BASH_SOURCE[0]}")"

# ---- Configuration ----
# The storage account, Cosmos account and Function App names must each be
# GLOBALLY unique across all of Azure, not just within the subscription. Export
# any of these to use your own names, e.g. if a teammate already deployed with
# the defaults:
#   STORAGE_ACCOUNT=cpsy300p3storage2 FUNCTION_APP=cpsy300-p3-func2 ./deploy.sh
RESOURCE_GROUP="${RESOURCE_GROUP:-cpsy300-project3-rg}"
LOCATION="${LOCATION:-canadacentral}"
STORAGE_ACCOUNT="${STORAGE_ACCOUNT:-cpsy300p3storage}"
FUNCTION_APP="${FUNCTION_APP:-cpsy300-p3-functions}"
COSMOS_ACCOUNT="${COSMOS_ACCOUNT:-cpsy300-p3-cosmos}"
COSMOS_DATABASE="${COSMOS_DATABASE:-nutritiondb}"

# ---- Pre-flight ----
# Without this the first az call fails with a long authentication trace that
# does not say "you are not logged in".
command -v az >/dev/null 2>&1 || {
  echo "ERROR: the Azure CLI (az) is not installed or not on PATH." >&2
  exit 1
}
command -v func >/dev/null 2>&1 || {
  echo "ERROR: Azure Functions Core Tools (func) is not installed." >&2
  echo "       npm i -g azure-functions-core-tools@4 --unsafe-perm true" >&2
  exit 1
}
az account show --output none 2>/dev/null || {
  echo "ERROR: not logged in to Azure. Run 'az login' first." >&2
  exit 1
}

# Fail now, with an actionable message, rather than after provisioning.
[[ -f frontend/config.js ]] || {
  echo "ERROR: frontend/config.js is missing. It carries the __API_BASE__" >&2
  echo "       placeholder the frontend needs to find the backend." >&2
  exit 1
}
[[ -f ../Project1/data/All_Diets.csv ]] || {
  echo "ERROR: ../Project1/data/All_Diets.csv not found. The blob trigger has" >&2
  echo "       nothing to process without it." >&2
  exit 1
}

# OAuth: register the apps first, then export these before running.
#   GitHub -> Settings > Developer settings > OAuth Apps > New OAuth App
#   Callback URL must match exactly:
#     https://<FUNCTION_APP>.azurewebsites.net/api/auth/oauth/github/callback
GITHUB_CLIENT_ID="${GITHUB_CLIENT_ID:-}"
GITHUB_CLIENT_SECRET="${GITHUB_CLIENT_SECRET:-}"
GOOGLE_CLIENT_ID="${GOOGLE_CLIENT_ID:-}"
GOOGLE_CLIENT_SECRET="${GOOGLE_CLIENT_SECRET:-}"

if [[ -z "$GITHUB_CLIENT_ID" && -z "$GOOGLE_CLIENT_ID" ]]; then
  echo "WARNING: no OAuth client configured. Third-party login will not work."
  echo "         Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET, or configure"
  echo "         them in the Function App settings afterwards."
  echo ""
fi

echo "============================================"
echo " Project 3 (Phase 3) — Azure Deployment"
echo "============================================"

# ---- 1. Resource Group ----
echo "[1/6] Creating resource group..."
az group create \
  --name "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --output none

# ---- 2. Storage Account ----
echo "[2/6] Creating storage account..."
# Storage account names are global. If this one belongs to somebody else the
# create fails with a message that reads like a validation error, so check and
# say what is actually wrong.
if ! az storage account show --name "$STORAGE_ACCOUNT" \
       --resource-group "$RESOURCE_GROUP" --output none 2>/dev/null; then
  if [[ "$(az storage account check-name-availability --name "$STORAGE_ACCOUNT" \
            --query nameAvailable -o tsv)" != "true" ]]; then
    echo "ERROR: the storage account name '$STORAGE_ACCOUNT' is already taken" >&2
    echo "       by another Azure subscription. Names are globally unique." >&2
    echo "       Re-run with your own, e.g.:" >&2
    echo "         STORAGE_ACCOUNT=${STORAGE_ACCOUNT}$RANDOM ./deploy.sh" >&2
    exit 1
  fi
fi

az storage account create \
  --name "$STORAGE_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --sku Standard_LRS \
  --kind StorageV2 \
  --output none

STORAGE_CONN=$(az storage account show-connection-string \
  --name "$STORAGE_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --query connectionString -o tsv)

# Create blob containers. `az storage container create` already succeeds when
# the container exists (it reports created:false), so there is nothing to
# tolerate here -- a non-zero exit means a real problem such as a bad key, and
# swallowing it would surface much later as a dashboard with no data.
echo "    Creating blob containers..."
az storage container create --name raw-data --connection-string "$STORAGE_CONN" --output none
az storage container create --name clean-data --connection-string "$STORAGE_CONN" --output none

# ---- 3. Cosmos DB ----
# Serverless: billed per request unit consumed, with no reserved throughput to
# pay for while the app sits idle between demo runs. Encrypted at rest with
# service-managed keys by default, which is what rubric item 8 asks for.
echo "[3/6] Creating Cosmos DB account, serverless (a few minutes)..."
az cosmosdb create \
  --name "$COSMOS_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --locations regionName="$LOCATION" failoverPriority=0 \
  --default-consistency-level Session \
  --capabilities EnableServerless \
  --output none

COSMOS_ENDPOINT=$(az cosmosdb show \
  --name "$COSMOS_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --query documentEndpoint -o tsv)

COSMOS_KEY=$(az cosmosdb keys list \
  --name "$COSMOS_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --query primaryMasterKey -o tsv)

# Create database and containers.  Existence is checked first so that a
# genuine failure (bad indexing policy, quota, permissions) stays fatal.  The
# earlier `|| echo "already exists"` form printed a reassuring message for
# *any* error and carried on, which surfaced much later as an empty dashboard.
echo "    Creating database and containers..."
if [[ "$(az cosmosdb sql database exists \
           --account-name "$COSMOS_ACCOUNT" \
           --resource-group "$RESOURCE_GROUP" \
           --name "$COSMOS_DATABASE" -o tsv)" == "true" ]]; then
  echo "    (database $COSMOS_DATABASE already exists)"
else
  az cosmosdb sql database create \
    --account-name "$COSMOS_ACCOUNT" \
    --resource-group "$RESOURCE_GROUP" \
    --name "$COSMOS_DATABASE" \
    --output none
fi

# The cache container holds the pre-computed payloads: a 2,000-element
# `records` array per chunk document, and the insights blob under `data`.
# Nothing queries inside either - chunks are read by id - so indexing those
# subtrees would charge write RUs for an index no read ever uses.  Excluding
# them is the single cheapest performance win on the Cosmos side.
# backend/cache.py applies the same policy if it creates the container first.
# Written to a file and passed as --idx @file rather than inline: the az CLI
# accepts a JSON string, but quoting a multi-line one through the shell is the
# kind of thing that works on one CLI version and not the next, and a rejected
# policy would now be fatal.  @file sidesteps the quoting entirely.
CACHE_INDEX_POLICY_FILE=$(mktemp)
cleanup_add "$CACHE_INDEX_POLICY_FILE"
cat > "$CACHE_INDEX_POLICY_FILE" <<'POLICY'
{
  "indexingMode": "consistent",
  "automatic": true,
  "includedPaths": [{"path": "/*"}],
  "excludedPaths": [{"path": "/records/*"}, {"path": "/data/*"}]
}
POLICY

# The users container keeps the default index-everything policy: login queries
# filter on c.email, c.provider and c.provider_id, which need those paths
# indexed.
if [[ "$(az cosmosdb sql container exists \
           --account-name "$COSMOS_ACCOUNT" \
           --resource-group "$RESOURCE_GROUP" \
           --database-name "$COSMOS_DATABASE" \
           --name users -o tsv)" == "true" ]]; then
  echo "    (container users already exists)"
else
  az cosmosdb sql container create \
    --account-name "$COSMOS_ACCOUNT" \
    --resource-group "$RESOURCE_GROUP" \
    --database-name "$COSMOS_DATABASE" \
    --name users \
    --partition-key-path "/partitionKey" \
    --output none
fi

# Note: an existing cache container keeps whatever policy it already has --
# `container create` does not update one, and `container update` would be
# needed to change it.
if [[ "$(az cosmosdb sql container exists \
           --account-name "$COSMOS_ACCOUNT" \
           --resource-group "$RESOURCE_GROUP" \
           --database-name "$COSMOS_DATABASE" \
           --name cache -o tsv)" == "true" ]]; then
  echo "    (container cache already exists; indexing policy left as-is)"
else
  az cosmosdb sql container create \
    --account-name "$COSMOS_ACCOUNT" \
    --resource-group "$RESOURCE_GROUP" \
    --database-name "$COSMOS_DATABASE" \
    --name cache \
    --partition-key-path "/partitionKey" \
    --idx "@$CACHE_INDEX_POLICY_FILE" \
    --output none
fi

# ---- 4. Function App ----
echo "[4/6] Creating Function App..."
az functionapp create \
  --name "$FUNCTION_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --storage-account "$STORAGE_ACCOUNT" \
  --consumption-plan-location "$LOCATION" \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4 \
  --os-type Linux \
  --output none

# Re-running the script must not rotate the signing key: that invalidates every
# issued token, so anyone registered during the demo is silently logged out and
# has to sign in again mid-recording. Reuse the existing value when there is one.
JWT_SECRET=$(az functionapp config appsettings list \
  --name "$FUNCTION_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --query "[?name=='JWT_SECRET'].value | [0]" -o tsv 2>/dev/null || true)
if [[ -z "$JWT_SECRET" || "$JWT_SECRET" == "None" ]]; then
  JWT_SECRET=$(openssl rand -base64 32)
  echo "    Generated a new JWT signing key."
else
  echo "    Reusing the existing JWT signing key."
fi

# Configure app settings
echo "    Configuring app settings..."
az functionapp config appsettings set \
  --name "$FUNCTION_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --settings \
    "BLOB_CONNECTION_STRING=$STORAGE_CONN" \
    "BLOB_CONTAINER_RAW=raw-data" \
    "BLOB_CONTAINER_CLEAN=clean-data" \
    "COSMOS_ENDPOINT=$COSMOS_ENDPOINT" \
    "COSMOS_KEY=$COSMOS_KEY" \
    "COSMOS_DATABASE=$COSMOS_DATABASE" \
    "COSMOS_USERS_CONTAINER=users" \
    "COSMOS_CACHE_CONTAINER=cache" \
    "JWT_SECRET=$JWT_SECRET" \
    "JWT_EXPIRY_HOURS=24" \
    "ENABLE_DEMO_FALLBACK=false" \
    "GITHUB_CLIENT_ID=$GITHUB_CLIENT_ID" \
    "GITHUB_CLIENT_SECRET=$GITHUB_CLIENT_SECRET" \
    "GITHUB_REDIRECT_URI=https://$FUNCTION_APP.azurewebsites.net/api/auth/oauth/github/callback" \
    "GOOGLE_CLIENT_ID=$GOOGLE_CLIENT_ID" \
    "GOOGLE_CLIENT_SECRET=$GOOGLE_CLIENT_SECRET" \
    "GOOGLE_REDIRECT_URI=https://$FUNCTION_APP.azurewebsites.net/api/auth/oauth/google/callback" \
  --output none

# Deploy function code.
# --build remote: pandas and numpy are compiled packages, so they have to be
# built on a Linux worker matching the Function App rather than shipped from
# this machine. Remote build is the default for Linux Consumption, but stating
# it explicitly keeps the behaviour independent of the Core Tools version.
# A subshell keeps the directory change local -- a bare `cd ..` would leave the
# script in the wrong place if anything between the two lines exited early.
echo "    Deploying function code..."
( cd backend && func azure functionapp publish "$FUNCTION_APP" --build remote )

# ---- 5. Deploy frontend ----
# Done before the dataset upload so FRONTEND_URL is known: the OAuth callback
# redirects there, and without the app setting it would send users to
# localhost:8080.
echo "[5/6] Deploying frontend to storage static website..."
az storage blob service-properties update \
  --account-name "$STORAGE_ACCOUNT" \
  --static-website \
  --index-document index.html \
  --404-document login.html \
  --output none

# The static website has no /api reverse proxy, so the frontend must call the
# Function App by its absolute URL.  config.js ships with an __API_BASE__
# placeholder; substitute it into a staging copy and upload that, leaving the
# repository copy untouched.
FUNCTION_API_BASE="https://${FUNCTION_APP}.azurewebsites.net/api"
STAGING_DIR=$(mktemp -d)
cleanup_add "$STAGING_DIR"
cp -R frontend/. "$STAGING_DIR"/
sed -i "s|__API_BASE__|${FUNCTION_API_BASE}|g" "$STAGING_DIR/config.js"
grep -q "$FUNCTION_API_BASE" "$STAGING_DIR/config.js" || {
  echo "ERROR: could not set the API base in config.js; the dashboard would" >&2
  echo "       call the storage domain and every request would 404." >&2
  exit 1
}
echo "    Frontend will call $FUNCTION_API_BASE"

az storage blob upload-batch \
  --source "$STAGING_DIR" \
  --destination '$web' \
  --account-name "$STORAGE_ACCOUNT" \
  --overwrite true \
  --output none

FRONTEND_URL=$(az storage account show \
  --name "$STORAGE_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --query primaryEndpoints.web -o tsv)

# Platform CORS is deliberately NOT configured here.
#
# Azure Functions platform CORS and the application are two independent layers.
# function_app.py already emits a complete set of headers on every response --
# _cors_headers() supplies Allow-Origin (from FRONTEND_URL), Allow-Methods,
# Allow-Headers including Authorization, and Max-Age, and all fifteen response
# paths go through it, including the OPTIONS pre-flight branch on every route
# and the 401 from the auth gate. Adding `az functionapp cors add` on top makes
# the infrastructure inject the same headers again, and a response carrying
# Access-Control-Allow-Origin twice is rejected by every browser with "contains
# multiple values ... but only one is allowed". That breaks every data call from
# the deployed dashboard while working perfectly under `func start`, which has
# no platform layer -- precisely the kind of fault that only appears in the
# cloud. One owner only, and the app is the owner.
#
# This makes the FRONTEND_URL setting below load-bearing: it is the origin the
# app echoes. Unset, _cors_headers() falls back to "*", which still works here
# because authentication rides in an Authorization header rather than a cookie,
# but the exact origin is the correct configuration.
az functionapp config appsettings set \
  --name "$FUNCTION_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --settings "FRONTEND_URL=${FRONTEND_URL%/}" \
  --output none

# ---- 6. Upload the dataset, which fires the blob trigger ----
echo "[6/6] Uploading initial dataset..."
az storage blob upload \
  --container-name raw-data \
  --file ../Project1/data/All_Diets.csv \
  --name All_Diets.csv \
  --connection-string "$STORAGE_CONN" \
  --overwrite true \
  --output none

echo ""
echo "============================================"
echo " Deployment Complete!"
echo "============================================"
echo ""
echo " Frontend URL:  $FRONTEND_URL"
echo " Function App:  https://$FUNCTION_APP.azurewebsites.net"
echo " Cosmos DB:     $COSMOS_ENDPOINT"
echo ""
echo " Next steps:"
echo "   1. Wait for the blob trigger to finish, then check:"
echo "        curl https://$FUNCTION_APP.azurewebsites.net/api/health"
echo "      'recipes_cached' should be true and 'recipe_count' 7806."
echo "      On a Consumption plan the trigger polls, so this can take"
echo "      several minutes after the upload."
echo "   2. Open the frontend URL, register, and confirm the status pill"
echo "      reads 'Served from Cosmos DB'."
echo "   3. Confirm the API rejects anonymous callers:"
echo "        curl -i https://$FUNCTION_APP.azurewebsites.net/api/insights"
echo "      This must return 401 -- it is the evidence for rubric item 9."
echo ""
echo " WHEN THE DEMO IS RECORDED, DELETE EVERYTHING:"
echo "        ./teardown.sh"
echo " Resources bill by the hour whether or not anyone uses them."
echo "============================================"
