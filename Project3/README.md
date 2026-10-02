# Project 3 — Phase 3: Improved Cloud Dashboard

CPSY 300 Cloud Computing — Nutritional Insights Application

## Overview

Phase 3 builds on the Phase 2 cloud dashboard with performance optimization
(blob triggers, result caching) and full authentication/security (email/password,
OAuth, encrypted DB, bcrypt password hashing, JWT-gated dashboard).

## Architecture

```
Browser (frontend/)
  |
  |--- login.html        Login / Register / OAuth
  |--- dashboard.html    Protected dashboard (charts, search, pagination)
  |--- index.html        Router (redirects based on auth state)
  |
  v
Azure Functions (backend/)
  |
  |--- Blob Trigger      Fires when All_Diets.csv changes in Blob Storage
  |--- /api/insights     Serves pre-computed analytics from cache
  |--- /api/recipes      Filtered, searchable, paginated recipe endpoint
  |--- /api/auth/*       Registration, login, OAuth (Google/GitHub)
  |--- /api/health       Health check with cache status
  |
  v
Azure Services
  |--- Blob Storage      Raw CSV + cleaned CSV containers
  |--- Redis Cache       Pre-computed insights and recipe data
  |--- Cosmos DB         User accounts (encrypted at rest) + cache fallback
```

## Local Development

### Prerequisites

- Python 3.11+
- Azure Functions Core Tools v4 (`npm i -g azure-functions-core-tools@4`)
- Docker and Docker Compose

### Quick Start

```bash
# 1. Start infrastructure (Redis, Azurite, Cosmos DB emulator)
docker-compose up -d

# 2. Install Python dependencies
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Start the Azure Functions host
func start

# 4. Open frontend in a browser
# Open frontend/login.html directly, or serve with:
cd ../frontend
python -m http.server 8080
# Then visit http://localhost:8080/login.html
```

### Demo Mode

The frontend works without a live backend. If the backend is unreachable,
it falls back to demo data and simulated authentication so you can see the
full UI and interaction flow.

## Azure Deployment

```bash
# Login to Azure
az login

# Deploy all resources
./deploy.sh
```

The deploy script provisions: Resource Group, Storage Account (with blob
containers), Azure Cache for Redis, Cosmos DB, Function App, and deploys
the frontend as a static website.

## Features Implemented

### Performance Optimization
- **Blob Trigger**: Azure Function triggers when All_Diets.csv is uploaded
  or modified. Data cleaning runs automatically and results are cached.
- **Result Caching**: All analytics are pre-computed on file change and stored
  in Redis (with Cosmos DB fallback). API requests serve cached data, not
  re-computed results.

### Data Interaction
- **Diet Type Filter**: Dropdown to filter recipes by diet type
- **Keyword Search**: Debounced search across recipe name, cuisine, and diet
- **Pagination**: 20 results per page with Previous/Next and page numbers

### Authentication & Security
- **Email/Password Auth**: Registration and login with validation
- **OAuth Login**: Google and GitHub OAuth 2.0 integration
- **DB Encryption**: Cosmos DB encrypts all data at rest (AES-256)
- **Password Hashing**: bcrypt with 12 salt rounds — plaintext never stored
- **Dashboard Auth Gate**: JWT required to access dashboard; user name and
  logout button displayed in the header

## Project Structure

```
Project3/
  backend/
    function_app.py       Main Azure Functions app (all endpoints)
    nutrition.py          Data cleaning and aggregation (from P1)
    auth.py               Password hashing, JWT, OAuth helpers
    cache.py              Redis / Cosmos DB caching layer
    models.py             User model, validation schemas
    host.json             Azure Functions host configuration
    local.settings.json   Local environment settings
    requirements.txt      Python dependencies
  frontend/
    index.html            Router page
    login.html            Login / Register page with OAuth
    dashboard.html        Protected analytics dashboard
    app.js                Chart rendering, search, pagination
    auth.js               JWT management, auth state
    styles.css            Custom styles
  docker-compose.yml      Local dev stack (Redis, Azurite, Cosmos)
  deploy.sh               Azure CLI deployment script
  README.md               This file
```

## Technologies

- **Backend**: Azure Functions (Python v2), Azure Blob Storage, Azure Cache
  for Redis, Azure Cosmos DB
- **Frontend**: HTML5, CSS3, JavaScript, Chart.js
- **Security**: bcrypt, JWT (PyJWT), OAuth 2.0 (Google, GitHub)
- **Data**: pandas, numpy (cleaning and aggregation)
