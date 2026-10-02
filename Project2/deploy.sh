#!/usr/bin/env bash
# deploy.sh -- Deploy Nutritional Insights Dashboard to Azure
# CPSY 300 Phase 2: Cloud Dashboard Development
#
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh
#
# Prerequisites:
#   - Azure CLI installed and logged in (az login)
#   - Azure Functions Core Tools v4 (func)
#   - Static Web Apps CLI (npm install -g @azure/static-web-apps-cli)
#
# The script is idempotent: re-running it updates the existing resources.
# It never prints the storage connection string -- the value is written
# straight into the Function App settings instead.

set -euo pipefail

# Always run relative to this script, so the dataset path resolves no matter
# where the script is invoked from.
cd "$(dirname "${BASH_SOURCE[0]}")"

# ---------------------------------------------------------------------------
# Configuration -- edit these values for your environment
# ---------------------------------------------------------------------------
RESOURCE_GROUP="${RESOURCE_GROUP:-cpsy300-nutritional-insights-rg}"
LOCATION="${LOCATION:-eastus}"
# Static Web Apps is only available in a handful of regions; eastus is not one.
SWA_LOCATION="${SWA_LOCATION:-eastus2}"
STORAGE_ACCOUNT="${STORAGE_ACCOUNT:-}"
FUNCTION_APP_NAME="${FUNCTION_APP_NAME:-cpsy300-nutrition-api}"
STATIC_WEB_APP_NAME="${STATIC_WEB_APP_NAME:-cpsy300-nutrition-dashboard}"
BLOB_CONTAINER="${BLOB_CONTAINER:-datasets}"
CSV_FILE="${CSV_FILE:-../Project1/data/All_Diets.csv}"
PYTHON_VERSION="${PYTHON_VERSION:-3.11}"
BUILD_DIR="build"

echo "=============================================="
echo " Nutritional Insights Dashboard -- Deployment"
echo "=============================================="
echo ""

if [[ ! -f "$CSV_FILE" ]]; then
    echo "ERROR: dataset not found at $CSV_FILE" >&2
    echo "Set CSV_FILE=/path/to/All_Diets.csv and re-run." >&2
    exit 1
fi

for tool in az func; do
    command -v "$tool" >/dev/null || { echo "ERROR: '$tool' is not installed." >&2; exit 1; }
done

# ---------------------------------------------------------------------------
# Step 1: Resource Group
# ---------------------------------------------------------------------------
echo "[1/7] Creating resource group: $RESOURCE_GROUP"
az group create \
    --name "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --output none
echo "  OK"

# ---------------------------------------------------------------------------
# Step 2: Storage Account + dataset upload
# ---------------------------------------------------------------------------
# Storage account names are globally unique, so reuse the one already in the
# resource group when re-running instead of creating a new random name.
if [[ -z "$STORAGE_ACCOUNT" ]]; then
    STORAGE_ACCOUNT=$(az storage account list \
        --resource-group "$RESOURCE_GROUP" \
        --query "[?starts_with(name,'cpsy300nutrition')].name | [0]" \
        --output tsv 2>/dev/null || true)
fi
if [[ -z "$STORAGE_ACCOUNT" || "$STORAGE_ACCOUNT" == "None" ]]; then
    STORAGE_ACCOUNT="cpsy300nutrition$(openssl rand -hex 3)"
fi

echo ""
echo "[2/7] Creating storage account: $STORAGE_ACCOUNT"
az storage account create \
    --name "$STORAGE_ACCOUNT" \
    --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --sku Standard_LRS \
    --kind StorageV2 \
    --min-tls-version TLS1_2 \
    --allow-blob-public-access false \
    --output none

CONN_STRING=$(az storage account show-connection-string \
    --name "$STORAGE_ACCOUNT" \
    --resource-group "$RESOURCE_GROUP" \
    --query connectionString \
    --output tsv)

echo "  Creating blob container: $BLOB_CONTAINER (private)"
az storage container create \
    --name "$BLOB_CONTAINER" \
    --connection-string "$CONN_STRING" \
    --output none

echo "  Uploading $(basename "$CSV_FILE") to blob storage"
az storage blob upload \
    --container-name "$BLOB_CONTAINER" \
    --file "$CSV_FILE" \
    --name "All_Diets.csv" \
    --connection-string "$CONN_STRING" \
    --overwrite \
    --output none
echo "  Dataset uploaded."

# ---------------------------------------------------------------------------
# Step 3: Function App
# ---------------------------------------------------------------------------
echo ""
echo "[3/7] Creating Function App: $FUNCTION_APP_NAME"
az functionapp create \
    --name "$FUNCTION_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --storage-account "$STORAGE_ACCOUNT" \
    --consumption-plan-location "$LOCATION" \
    --runtime python \
    --runtime-version "$PYTHON_VERSION" \
    --functions-version 4 \
    --os-type Linux \
    --output none

echo "  Configuring app settings (connection string stays out of the repo and the log)"
az functionapp config appsettings set \
    --name "$FUNCTION_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --settings \
        "AZURE_STORAGE_CONNECTION_STRING=$CONN_STRING" \
        "BLOB_CONTAINER_NAME=$BLOB_CONTAINER" \
        "BLOB_NAME=All_Diets.csv" \
    --output none
echo "  OK"

FUNCTION_URL="https://${FUNCTION_APP_NAME}.azurewebsites.net"

# ---------------------------------------------------------------------------
# Step 4: Deploy the backend
# ---------------------------------------------------------------------------
echo ""
echo "[4/7] Publishing backend to Azure Functions"
(cd backend && func azure functionapp publish "$FUNCTION_APP_NAME")
echo "  Function App URL: $FUNCTION_URL"

# ---------------------------------------------------------------------------
# Step 5: Static Web App (created unlinked, so no GitHub token is needed)
# ---------------------------------------------------------------------------
echo ""
echo "[5/7] Creating Static Web App: $STATIC_WEB_APP_NAME"
az staticwebapp create \
    --name "$STATIC_WEB_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --location "$SWA_LOCATION" \
    --sku Free \
    --output none

SWA_HOSTNAME=$(az staticwebapp show \
    --name "$STATIC_WEB_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query defaultHostname \
    --output tsv)
DASHBOARD_URL="https://${SWA_HOSTNAME}"
echo "  Dashboard URL: $DASHBOARD_URL"

# ---------------------------------------------------------------------------
# Step 6: Build and deploy the frontend
# ---------------------------------------------------------------------------
echo ""
echo "[6/7] Building frontend with the live API endpoint"
# Build into a separate directory so the committed sources keep their
# placeholder and the repository stays clean.
rm -rf "$BUILD_DIR"
cp -r frontend "$BUILD_DIR"
cp staticwebapp.config.json "$BUILD_DIR/" 2>/dev/null || true

# '#' is used as the sed delimiter because the replacement contains '/'.
sed -i "s#__FUNCTION_API_URL__#${FUNCTION_URL}/api#" "$BUILD_DIR/index.html"
grep -q "${FUNCTION_URL}/api" "$BUILD_DIR/index.html" \
    || { echo "ERROR: failed to inject the API URL into index.html" >&2; exit 1; }
echo "  Frontend configured to call: $FUNCTION_URL/api"

if command -v swa >/dev/null; then
    SWA_TOKEN=$(az staticwebapp secrets list \
        --name "$STATIC_WEB_APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query properties.apiKey \
        --output tsv)
    swa deploy "$BUILD_DIR" --deployment-token "$SWA_TOKEN" --env production
    echo "  Frontend deployed."
else
    echo "  WARNING: the 'swa' CLI was not found, so the frontend was NOT deployed." >&2
    echo "  Install it and re-run, or deploy the build manually:" >&2
    echo "    npm install -g @azure/static-web-apps-cli" >&2
    echo "    swa deploy $BUILD_DIR --deployment-token \$(az staticwebapp secrets list \\" >&2
    echo "      --name $STATIC_WEB_APP_NAME --resource-group $RESOURCE_GROUP \\" >&2
    echo "      --query properties.apiKey -o tsv) --env production" >&2
fi

# ---------------------------------------------------------------------------
# Step 7: Scope CORS to the dashboard origin, then smoke-test
# ---------------------------------------------------------------------------
echo ""
echo "[7/7] Scoping CORS to $DASHBOARD_URL"
# Remove any wildcard left over from an earlier run, then allow only the
# dashboard origin. CORS is handled entirely at the host level; the function
# code deliberately sends no Access-Control-Allow-* headers of its own.
az functionapp cors remove \
    --name "$FUNCTION_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --allowed-origins "*" \
    --output none 2>/dev/null || true
az functionapp cors add \
    --name "$FUNCTION_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --allowed-origins "$DASHBOARD_URL" \
    --output none
echo "  Allowed origin: $DASHBOARD_URL"

echo ""
echo "  Smoke-testing the API (the first call pays the cold start)"
for endpoint in health "insights" "recipes?page=1&limit=5"; do
    printf '    %-28s ' "/api/${endpoint%%\?*}"
    if curl -fsS --max-time 180 "$FUNCTION_URL/api/$endpoint" >/dev/null; then
        echo "OK"
    else
        echo "FAILED"
    fi
done

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "=============================================="
echo " Deployment Complete"
echo "=============================================="
echo ""
echo " Resource Group:  $RESOURCE_GROUP"
echo " Storage Account: $STORAGE_ACCOUNT (container: $BLOB_CONTAINER, private)"
echo " Function App:    $FUNCTION_URL"
echo " Dashboard:       $DASHBOARD_URL"
echo ""
echo " API Endpoints:"
echo "   - Health:   $FUNCTION_URL/api/health"
echo "   - Insights: $FUNCTION_URL/api/insights"
echo "   - Recipes:  $FUNCTION_URL/api/recipes?page=1&limit=50&diet_type=keto"
echo ""
echo " The storage connection string was written to the Function App settings."
echo " Retrieve it when needed with:"
echo "   az functionapp config appsettings list --name $FUNCTION_APP_NAME \\"
echo "     --resource-group $RESOURCE_GROUP --query \"[?name=='AZURE_STORAGE_CONNECTION_STRING']\""
echo ""
echo " To run locally:"
echo "   cd backend && func start   # then open frontend/index.html"
echo ""
