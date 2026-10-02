#!/usr/bin/env bash
###############################################################################
# Project 3 (Phase 3) — Azure Deployment Script
#
# Provisions all required Azure resources and deploys the application:
#   - Resource Group
#   - Storage Account (Blob containers: raw-data, clean-data)
#   - Azure Cache for Redis
#   - Cosmos DB (SQL API, encrypted at rest)
#   - Azure Functions (Python, Consumption plan)
#   - Static Web App (frontend)
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
REDIS_NAME="cpsy300-p3-redis"
COSMOS_ACCOUNT="cpsy300-p3-cosmos"
COSMOS_DATABASE="nutritiondb"
STATIC_WEB_APP="cpsy300-p3-frontend"

echo "============================================"
echo " Project 3 (Phase 3) — Azure Deployment"
echo "============================================"

# ---- 1. Resource Group ----
echo "[1/7] Creating resource group..."
az group create \
  --name "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --output none

# ---- 2. Storage Account ----
echo "[2/7] Creating storage account..."
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

# ---- 3. Azure Cache for Redis ----
echo "[3/7] Creating Azure Cache for Redis (may take a few minutes)..."
az redis create \
  --name "$REDIS_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --sku Basic \
  --vm-size C0 \
  --output none

REDIS_HOST=$(az redis show \
  --name "$REDIS_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query hostName -o tsv)

REDIS_KEY=$(az redis list-keys \
  --name "$REDIS_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query primaryKey -o tsv)

# ---- 4. Cosmos DB ----
echo "[4/7] Creating Cosmos DB account (encrypted at rest by default)..."
az cosmosdb create \
  --name "$COSMOS_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --locations regionName="$LOCATION" failoverPriority=0 \
  --default-consistency-level Session \
  --output none

COSMOS_ENDPOINT=$(az cosmosdb show \
  --name "$COSMOS_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --query documentEndpoint -o tsv)

COSMOS_KEY=$(az cosmosdb keys list \
  --name "$COSMOS_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --query primaryMasterKey -o tsv)

# Create database and containers
echo "    Creating database and containers..."
az cosmosdb sql database create \
  --account-name "$COSMOS_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --name "$COSMOS_DATABASE" \
  --output none 2>/dev/null || true

az cosmosdb sql container create \
  --account-name "$COSMOS_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --database-name "$COSMOS_DATABASE" \
  --name users \
  --partition-key-path "/partitionKey" \
  --output none 2>/dev/null || true

az cosmosdb sql container create \
  --account-name "$COSMOS_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --database-name "$COSMOS_DATABASE" \
  --name cache \
  --partition-key-path "/partitionKey" \
  --output none 2>/dev/null || true

# ---- 5. Function App ----
echo "[5/7] Creating Function App..."
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
    "REDIS_HOST=$REDIS_HOST" \
    "REDIS_PORT=6380" \
    "REDIS_PASSWORD=$REDIS_KEY" \
    "REDIS_SSL=true" \
    "COSMOS_ENDPOINT=$COSMOS_ENDPOINT" \
    "COSMOS_KEY=$COSMOS_KEY" \
    "COSMOS_DATABASE=$COSMOS_DATABASE" \
    "COSMOS_USERS_CONTAINER=users" \
    "COSMOS_CACHE_CONTAINER=cache" \
    "JWT_SECRET=$(openssl rand -base64 32)" \
    "JWT_EXPIRY_HOURS=24" \
  --output none

# Deploy function code
echo "    Deploying function code..."
cd backend
func azure functionapp publish "$FUNCTION_APP" --python
cd ..

# ---- 6. Upload initial data ----
echo "[6/7] Uploading initial dataset..."
az storage blob upload \
  --container-name raw-data \
  --file ../Project1/data/All_Diets.csv \
  --name All_Diets.csv \
  --connection-string "$STORAGE_CONN" \
  --overwrite true \
  --output none 2>/dev/null || true

# ---- 7. Deploy frontend (Static Web App or Storage static site) ----
echo "[7/7] Deploying frontend to storage static website..."
az storage blob service-properties update \
  --account-name "$STORAGE_ACCOUNT" \
  --static-website \
  --index-document index.html \
  --404-document login.html \
  --output none

az storage blob upload-batch \
  --source frontend/ \
  --destination '$web' \
  --account-name "$STORAGE_ACCOUNT" \
  --overwrite true \
  --output none

FRONTEND_URL=$(az storage account show \
  --name "$STORAGE_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --query primaryEndpoints.web -o tsv)

# Update CORS and frontend URL
az functionapp cors add \
  --name "$FUNCTION_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --allowed-origins "${FRONTEND_URL%/}" \
  --output none 2>/dev/null || true

echo ""
echo "============================================"
echo " Deployment Complete!"
echo "============================================"
echo ""
echo " Frontend URL:  $FRONTEND_URL"
echo " Function App:  https://$FUNCTION_APP.azurewebsites.net"
echo " Redis:         $REDIS_HOST:6380"
echo " Cosmos DB:     $COSMOS_ENDPOINT"
echo ""
echo " Next steps:"
echo "   1. Configure OAuth client IDs in Function App settings"
echo "   2. Upload All_Diets.csv to the raw-data blob container"
echo "      (the blob trigger will process it automatically)"
echo "   3. Open the frontend URL in your browser"
echo "============================================"
