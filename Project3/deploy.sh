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

# ---- Configuration (edit these) ----
RESOURCE_GROUP="cpsy300-project3-rg"
LOCATION="canadacentral"
STORAGE_ACCOUNT="cpsy300p3storage"
FUNCTION_APP="cpsy300-p3-functions"
COSMOS_ACCOUNT="cpsy300-p3-cosmos"
COSMOS_DATABASE="nutritiondb"

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

# Create blob containers
echo "    Creating blob containers..."
az storage container create --name raw-data --connection-string "$STORAGE_CONN" --output none 2>/dev/null || true
az storage container create --name clean-data --connection-string "$STORAGE_CONN" --output none 2>/dev/null || true

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

# Create database and containers. Errors are shown rather than discarded: a
# silently missing container used to surface much later as an empty dashboard.
echo "    Creating database and containers..."
az cosmosdb sql database create \
  --account-name "$COSMOS_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --name "$COSMOS_DATABASE" \
  --output none || echo "    (database already exists)"

# The cache container holds the pre-computed payloads: a 2,000-element
# `records` array per chunk document, and the insights blob under `data`.
# Nothing queries inside either - chunks are read by id - so indexing those
# subtrees would charge write RUs for an index no read ever uses.  Excluding
# them is the single cheapest performance win on the Cosmos side.
# backend/cache.py applies the same policy if it creates the container first.
CACHE_INDEX_POLICY='{
  "indexingMode": "consistent",
  "automatic": true,
  "includedPaths": [{"path": "/*"}],
  "excludedPaths": [{"path": "/records/*"}, {"path": "/data/*"}]
}'

az cosmosdb sql container create \
  --account-name "$COSMOS_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --database-name "$COSMOS_DATABASE" \
  --name users \
  --partition-key-path "/partitionKey" \
  --output none || echo "    (container users already exists)"

az cosmosdb sql container create \
  --account-name "$COSMOS_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --database-name "$COSMOS_DATABASE" \
  --name cache \
  --partition-key-path "/partitionKey" \
  --idx "$CACHE_INDEX_POLICY" \
  --output none || echo "    (container cache already exists)"

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
    "JWT_SECRET=$(openssl rand -base64 32)" \
    "JWT_EXPIRY_HOURS=24" \
    "ENABLE_DEMO_FALLBACK=false" \
    "GITHUB_CLIENT_ID=$GITHUB_CLIENT_ID" \
    "GITHUB_CLIENT_SECRET=$GITHUB_CLIENT_SECRET" \
    "GITHUB_REDIRECT_URI=https://$FUNCTION_APP.azurewebsites.net/api/auth/oauth/github/callback" \
    "GOOGLE_CLIENT_ID=$GOOGLE_CLIENT_ID" \
    "GOOGLE_CLIENT_SECRET=$GOOGLE_CLIENT_SECRET" \
    "GOOGLE_REDIRECT_URI=https://$FUNCTION_APP.azurewebsites.net/api/auth/oauth/google/callback" \
  --output none

# Deploy function code
echo "    Deploying function code..."
cd backend
func azure functionapp publish "$FUNCTION_APP" --python
cd ..

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
trap 'rm -rf "$STAGING_DIR"' EXIT
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

# CORS must list the exact frontend origin: a rejected pre-flight makes fetch
# reject, which the login page reports as an unreachable server.
az functionapp cors add \
  --name "$FUNCTION_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --allowed-origins "${FRONTEND_URL%/}" \
  --output none || echo "    (origin already allowed)"

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
