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
#   - Azure Functions Core Tools installed (func)
#   - Node.js installed (for Static Web Apps CLI, optional)

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration -- edit these values for your environment
# ---------------------------------------------------------------------------
RESOURCE_GROUP="cpsy300-nutritional-insights-rg"
LOCATION="eastus"
STORAGE_ACCOUNT="cpsy300nutrition$(openssl rand -hex 3)"
FUNCTION_APP_NAME="cpsy300-nutrition-api"
STATIC_WEB_APP_NAME="cpsy300-nutrition-dashboard"
BLOB_CONTAINER="datasets"
CSV_FILE="../Project1/data/All_Diets.csv"
PYTHON_VERSION="3.11"

echo "=============================================="
echo " Nutritional Insights Dashboard -- Deployment"
echo "=============================================="
echo ""

# ---------------------------------------------------------------------------
# Step 1: Create Resource Group
# ---------------------------------------------------------------------------
echo "[1/6] Creating resource group: $RESOURCE_GROUP"
az group create \
    --name "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --output table

# ---------------------------------------------------------------------------
# Step 2: Create Storage Account and upload dataset
# ---------------------------------------------------------------------------
echo ""
echo "[2/6] Creating storage account: $STORAGE_ACCOUNT"
az storage account create \
    --name "$STORAGE_ACCOUNT" \
    --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --sku Standard_LRS \
    --kind StorageV2 \
    --output table

# Get connection string
CONN_STRING=$(az storage account show-connection-string \
    --name "$STORAGE_ACCOUNT" \
    --resource-group "$RESOURCE_GROUP" \
    --query connectionString \
    --output tsv)

echo "  Creating blob container: $BLOB_CONTAINER"
az storage container create \
    --name "$BLOB_CONTAINER" \
    --connection-string "$CONN_STRING" \
    --output table

echo "  Uploading All_Diets.csv to blob storage"
az storage blob upload \
    --container-name "$BLOB_CONTAINER" \
    --file "$CSV_FILE" \
    --name "All_Diets.csv" \
    --connection-string "$CONN_STRING" \
    --overwrite \
    --output table

echo "  Dataset uploaded successfully."

# ---------------------------------------------------------------------------
# Step 3: Create Function App
# ---------------------------------------------------------------------------
echo ""
echo "[3/6] Creating Function App: $FUNCTION_APP_NAME"
az functionapp create \
    --name "$FUNCTION_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --storage-account "$STORAGE_ACCOUNT" \
    --consumption-plan-location "$LOCATION" \
    --runtime python \
    --runtime-version "$PYTHON_VERSION" \
    --functions-version 4 \
    --os-type Linux \
    --output table

# Configure application settings
echo "  Configuring app settings"
az functionapp config appsettings set \
    --name "$FUNCTION_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --settings \
        "AZURE_STORAGE_CONNECTION_STRING=$CONN_STRING" \
        "BLOB_CONTAINER_NAME=$BLOB_CONTAINER" \
        "BLOB_NAME=All_Diets.csv" \
    --output table

# Enable CORS for all origins (adjust for production)
echo "  Configuring CORS"
az functionapp cors add \
    --name "$FUNCTION_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --allowed-origins "*" \
    --output table

# ---------------------------------------------------------------------------
# Step 4: Deploy Backend (Azure Functions)
# ---------------------------------------------------------------------------
echo ""
echo "[4/6] Deploying backend to Azure Functions"
cd backend
func azure functionapp publish "$FUNCTION_APP_NAME" --python
cd ..

FUNCTION_URL="https://${FUNCTION_APP_NAME}.azurewebsites.net"
echo "  Function App URL: $FUNCTION_URL"

# ---------------------------------------------------------------------------
# Step 5: Update frontend API URL
# ---------------------------------------------------------------------------
echo ""
echo "[5/6] Updating frontend API configuration"
# Inject the API URL into app.js for production
sed -i "s|const API_BASE_URL = window.NUTRITIONAL_API_URL || \"/api\";|const API_BASE_URL = window.NUTRITIONAL_API_URL || \"${FUNCTION_URL}/api\";|" \
    frontend/app.js
echo "  Frontend configured to use: $FUNCTION_URL/api"

# ---------------------------------------------------------------------------
# Step 6: Deploy Frontend (Azure Static Web App)
# ---------------------------------------------------------------------------
echo ""
echo "[6/6] Deploying frontend as Azure Static Web App"

# Option A: Using Azure Static Web Apps CLI (swa)
if command -v swa &> /dev/null; then
    echo "  Using SWA CLI for deployment"
    cd frontend
    swa deploy \
        --app-name "$STATIC_WEB_APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --env production
    cd ..
else
    # Option B: Create via Azure CLI and deploy
    echo "  Creating Static Web App via Azure CLI"
    az staticwebapp create \
        --name "$STATIC_WEB_APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --location "$LOCATION" \
        --source "." \
        --output table 2>/dev/null || true

    echo ""
    echo "  NOTE: For Static Web App deployment without SWA CLI,"
    echo "  you can also deploy using one of these methods:"
    echo ""
    echo "  Method 1: Install SWA CLI and re-run this script"
    echo "    npm install -g @azure/static-web-apps-cli"
    echo ""
    echo "  Method 2: Deploy frontend as Azure Storage static website"
    echo "    az storage blob service-properties update \\"
    echo "      --account-name $STORAGE_ACCOUNT \\"
    echo "      --static-website \\"
    echo "      --index-document index.html"
    echo "    az storage blob upload-batch \\"
    echo "      --source frontend \\"
    echo "      --destination '\$web' \\"
    echo "      --account-name $STORAGE_ACCOUNT"
    echo ""
    echo "  Method 3: Use GitHub Actions with the Static Web App"
    echo "    Push code to GitHub and connect it to the Static Web App"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "=============================================="
echo " Deployment Complete"
echo "=============================================="
echo ""
echo " Resource Group:  $RESOURCE_GROUP"
echo " Storage Account: $STORAGE_ACCOUNT"
echo " Function App:    $FUNCTION_URL"
echo " API Endpoints:"
echo "   - Health:   $FUNCTION_URL/api/health"
echo "   - Insights: $FUNCTION_URL/api/insights"
echo "   - Recipes:  $FUNCTION_URL/api/recipes"
echo ""
echo " Connection String (save this):"
echo "   $CONN_STRING"
echo ""
echo " To test the API:"
echo "   curl $FUNCTION_URL/api/health"
echo ""
echo " To run locally:"
echo "   cd backend && func start"
echo "   # Then open frontend/index.html in a browser"
echo ""
