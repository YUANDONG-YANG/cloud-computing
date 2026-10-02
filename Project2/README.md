# Project 2: Cloud Dashboard Development

**CPSY 300 -- Cloud Computing**
**Phase 2: Azure Cloud Dashboard for Nutritional Insights**

## Overview

This project moves the Nutritional Insights application from Project 1 to Azure Cloud, adding a web-based dashboard with interactive data visualizations. The backend runs as Azure Functions (HTTP triggers) that read recipe data from Azure Blob Storage, and the frontend is a responsive HTML/CSS/JS dashboard deployed via Azure Static Web Apps.

## Architecture

```
Browser (Dashboard)
    |
    | HTTP GET /api/insights, /api/recipes, /api/health
    v
Azure Functions (Python v2)
    |
    | azure-storage-blob SDK
    v
Azure Blob Storage
    |
    datasets/All_Diets.csv (7,806 recipes)
```

## Project Structure

```
Project2/
  backend/
    function_app.py       # Azure Functions v2 app (3 HTTP endpoints)
    nutrition.py          # Data cleaning and aggregation (from P1)
    host.json             # Azure Functions host configuration
    local.settings.json   # Local development settings
    requirements.txt      # Python dependencies
  frontend/
    index.html            # Dashboard page (Tailwind CSS)
    app.js                # Chart.js visualizations and API integration
    styles.css            # Custom component styles
  deploy.sh               # Azure CLI deployment script
  README.md               # This file
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check -- returns service status |
| `/api/insights` | GET | Aggregate data: average macros, top recipes, common cuisines, summary stats |
| `/api/recipes` | GET | All recipes; optional `?diet_type=keto` filter |

All responses include `metadata.execution_time_seconds` for performance monitoring.

## Dashboard Features

- **4 Interactive Visualizations**: Bar chart (average macros), doughnut chart (recipe distribution), heatmap (macronutrient intensity), scatter plot (protein vs. carbs)
- **Diet Type Filter**: Dropdown to filter all charts and tables by diet
- **Refresh Button**: Re-fetches data from the Azure Function
- **Execution Time Display**: Shows API response time in milliseconds
- **Top Recipes Table**: Highest-protein recipes per diet with pagination
- **Common Cuisines Table**: Most frequent cuisine per diet type
- **Full Recipe Browser**: Paginated table of all 7,806 recipes
- **Demo Mode**: Falls back to built-in data when the API is unavailable

## Local Development

### Prerequisites

- Python 3.9+
- Azure Functions Core Tools v4 (`npm install -g azure-functions-core-tools@4`)
- Azure CLI (for deployment)

### Run the Backend Locally

```bash
cd backend
pip install -r requirements.txt

# Start Azure Functions locally (requires Azurite or Azure Storage)
func start
```

The API will be available at `http://localhost:7071/api/`.

### Run the Frontend Locally

Open `frontend/index.html` in a browser. If the backend is not running, the dashboard automatically falls back to demo mode with real dataset values.

To connect to the local backend, the frontend uses `/api` as the base URL by default. When serving both from the same origin (e.g., via a local server), this works automatically. Otherwise, set the API URL:

```javascript
// In the browser console or before loading app.js:
window.NUTRITIONAL_API_URL = "http://localhost:7071/api";
```

### Using Azurite for Local Blob Storage

```bash
# Install and start Azurite
npm install -g azurite
azurite --silent --location ./azurite-data

# Upload the dataset
az storage container create --name datasets --connection-string "UseDevelopmentStorage=true"
az storage blob upload --container-name datasets --file ../Project1/data/All_Diets.csv \
    --name All_Diets.csv --connection-string "UseDevelopmentStorage=true"
```

## Deploy to Azure

```bash
# Login to Azure
az login

# Run the deployment script
chmod +x deploy.sh
./deploy.sh
```

The script will:
1. Create a resource group
2. Create a storage account and upload the CSV dataset
3. Create and deploy the Azure Function App
4. Configure CORS and environment variables
5. Deploy the frontend as a Static Web App

## Dataset

- **Source**: All_Diets.csv (7,806 recipes across 5 diet types)
- **Diet types**: Dash, Keto, Mediterranean, Paleo, Vegan
- **Columns**: Diet_type, Recipe_name, Cuisine_type, Protein(g), Carbs(g), Fat(g)

## Key Findings

| Diet | Avg Protein (g) | Avg Carbs (g) | Avg Fat (g) |
|------|-----------------|----------------|-------------|
| Dash | 69.28 | 160.54 | 101.15 |
| Keto | 101.27 | 57.97 | 153.12 |
| Mediterranean | 101.11 | 152.91 | 101.42 |
| Paleo | 88.67 | 129.55 | 135.67 |
| Vegan | 56.16 | 254.00 | 103.30 |

- **Highest mean protein**: Keto (101.27g)
- **Highest total protein**: Mediterranean (177,249.89g)

## Technologies

- **Backend**: Azure Functions (Python v2), Azure Blob Storage, pandas, numpy
- **Frontend**: HTML5, Tailwind CSS (CDN), Chart.js (CDN), vanilla JavaScript
- **Deployment**: Azure CLI, Azure Static Web Apps
