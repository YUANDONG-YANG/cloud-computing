# Project 3 (Phase 3) — Improve Cloud Dashboard: Requirements Analysis

**Course:** CPSY 300 Cloud Computing | **Team:** Yuandong Yang, Ethan Bayarsaikhan, Justin Norman-Rance
**Date:** 2026-10-02 | **Repo:** https://github.com/YUANDONG-YANG/cloud-computing/tree/main/Project3

---

## 1. Phase Overview

Phase 3 builds on Phase 2's deployed dashboard. Focus areas: **performance optimization** and **security (authentication)**.

The Azure Function reads All_Diets.csv from Blob Storage, performs data cleaning and visualization, displayed on a static dashboard. Phase 3 improves this with caching, user auth, and data interaction.

> Note on hosting: this phase ships the frontend as static files on the storage account's
> Blob Storage **static website** (`$web`), not on Azure Static Web Apps. The difference
> matters because static website hosting does not proxy `/api` to the Function App, so the
> frontend calls it by absolute URL — see `frontend/config.js` and the `__API_BASE__`
> substitution in `deploy.sh`.

---

## 2. Rubric Breakdown (Total: 100 marks)

| Category                                    | Marks | Description                                                        |
|---------------------------------------------|-------|--------------------------------------------------------------------|
| **Performance: Data Cleaning**              | 10    | Data cleaning done once, triggered only when All_Diets.csv changes |
| **Performance: Result Calculation**         | 10    | Results calculated once on file change, stored in Redis/Cosmos DB  |
| **Data Interaction: Diet Type Filter**      | 5     | User can search recipes using diet type filter                     |
| **Data Interaction: Keyword Search**        | 10    | User can search recipes using keyword                              |
| **Data Interaction: Pagination**            | 5     | Proper pagination in search results                                |
| **Security: Email/Password Auth**           | 10    | Email/password registration and login implemented                  |
| **Security: OAuth Login**                   | 10    | At least one 3rd party OAuth login (Google/GitHub/LinkedIn)        |
| **Security: DB Encryption & Password Hash** | 10    | Database encrypted at rest, password hash stored (not plaintext)   |
| **Dashboard UI: Auth Gate**                 | 10    | User must log in to see dashboard; name + logout button at top     |
| **Presentation**                            | 20    | Video explaining all implementations with demo                     |

---

## 3. Detailed Requirements

### 3.1 Performance Optimization

**Blob Trigger for Data Cleaning:**
- Update Azure Function to listen for blob trigger on All_Diets.csv
- When file changes → perform data cleaning → save cleaned data to another CSV in blob storage
- Cleaning only runs once per file update, not on every request

**Result Caching:**
- Pre-calculate all visualization results when All_Diets.csv changes
- Store results in external cache (Redis) or database (Cosmos DB)
- All subsequent visualization requests served from cache/DB, not re-computed
- Demonstrate with 2 versions of the file

### 3.2 Data Interaction

**Diet Type Filter:**
- Dropdown or similar UI element to filter recipes by diet type
- API endpoint: `/api/recipes?diet=keto`

**Keyword Search:**
- Text input for searching recipes by keyword (recipe name, cuisine, etc.)
- API endpoint: `/api/recipes?search=chicken`

**Pagination:**
- Search results paginated (e.g., 20 per page)
- UI shows page numbers, previous/next buttons
- API endpoint: `/api/recipes?page=1&pageSize=20`

### 3.3 Authentication & Security

**Email/Password Auth:**
- Registration form (email, password, name)
- Login form (email, password)
- Password hashed with bcrypt before storing
- Never store plaintext password

**OAuth Login:**
- At least one: Google, GitHub, or LinkedIn
- Standard OAuth 2.0 flow: redirect → authorization → callback → token exchange
- Create/link user account from OAuth profile

**Database Security:**
- Use Cosmos DB (or similar) for user profiles
- Data at rest encrypted (Azure-managed encryption)
- Store password hash value only

**Dashboard Auth Gate:**
- Dashboard hidden behind login
- After login: show user's name at top-right corner
- Logout button next to user name
- Unauthenticated users redirected to login page

---

## 4. Presentation Requirements

Video must demonstrate:
1. Data cleaning + result calculation triggered only on file change (show 2 versions of All_Diets.csv)
2. User registration and login process (email/password + OAuth)
3. Data interaction: diet filter, keyword search, pagination

---

## 5. UI Reference (from UI-for-project3.html)

The provided UI skeleton includes:
- **4 chart slots:** Bar Chart, Scatter Plot, Heatmap, Pie Chart
- **Filters:** Search by Diet Type, dropdown selector
- **API buttons:** Get Nutritional Insights, Get Recipes, Get Clusters
- **Security & Compliance:** Encryption Enabled, Access Control Secure, GDPR Compliant
- **OAuth & 2FA:** Login with Google, Login with GitHub, 2FA code input
- **Cloud Resource Cleanup:** cleanup button
- **Pagination:** Previous / 1 / 2 / Next

---

## 6. Available Data (from P1 analysis)

**Dataset:** All_Diets.csv — 7,806 recipes, 5 diet types

**Average macros per diet:**
| Diet           | Protein (g) | Carbs (g) | Fat (g)  |
|----------------|-------------|-----------|----------|
| dash           | 69.28       | 160.54    | 101.15   |
| keto           | 101.27      | 57.97     | 153.12   |
| mediterranean  | 101.11      | 152.91    | 101.42   |
| paleo          | 88.67       | 129.55    | 135.67   |
| vegan          | 56.16       | 254.00    | 103.30   |

**Key findings:**
- Highest mean protein: keto (101.27 g)
- Highest total protein: mediterranean (177,249.89 g)
- Recipe counts: dash 1,745, keto 1,512, mediterranean 1,753, paleo 1,274, vegan 1,522 (exact, counted from `All_Diets.csv`; an earlier revision of this document gave ~1561/~1890/~1752/~1553/~1050, which was wrong)

---

## 7. What Needs to Be Built (Report Plan)

1. **Enhanced architecture diagram** — Blob Trigger → Azure Function → Cosmos DB (serverless; Redis optional, only when `REDIS_HOST` is set) → Blob Storage static website (with auth enforced in the Function App)
2. **Performance section** — blob trigger code, caching strategy, before/after comparison
3. **Data interaction section** — filter, search, pagination with code and mock UI
4. **Auth & Security section:**
   - Login/Register page mock (inline SVG)
   - OAuth flow diagram
   - Password hashing code (bcrypt)
   - DB encryption explanation
   - Dashboard with user name + logout mock
5. **Dashboard with charts** — inline SVG visualizations using real data
6. **Code snippets** — blob trigger function, Redis caching, auth middleware, OAuth callback, search API, password hashing
7. **Rubric mapping table** with status badges
8. **Security analysis** — encryption at rest, hashing, token handling
9. **Team contribution** section
10. **Challenges & solutions** section

---

## 8. Key Technical Components

### Backend

**Blob-Triggered Function:**
```
Trigger: Azure Blob Storage (All_Diets.csv)
Action: Clean data → compute aggregations → store in Redis/Cosmos DB
```

**HTTP API Functions** (reconciled with the routes actually in
`backend/function_app.py`; this list was drafted before the code existed):
- `GET /api/insights` — cached visualization data. **Requires a bearer token**: 401 without one, 503 when nothing is cached
- `GET /api/recipes?diet=X&search=Y&page=N&pageSize=M` — filter, search, pagination. Same token requirement and same 503 behaviour
- `GET /api/health` — cache and security status (public, no token)
- `POST /api/auth/register` — register new user
- `POST /api/auth/login` — login with email/password
- `GET /api/auth/me` — current user, from the bearer token
- `POST /api/auth/logout` — logout (the client discards the token)
- `GET /api/auth/oauth/google` and `GET /api/auth/oauth/google/callback`
- `GET /api/auth/oauth/github` and `GET /api/auth/oauth/github/callback`

### Frontend
- Login/Register page (shown first)
- Dashboard (shown after auth)
- User name + Logout button in top-right header
- Charts rendered with real data from cache
- Diet filter dropdown, keyword search input, pagination controls

### Data Layer
- **Azure Blob Storage** — raw CSV files
- **Redis Cache** — pre-computed chart data, aggregations
- **Cosmos DB** — user profiles (encrypted at rest, password hashes)

### Security
- bcrypt for password hashing (cost factor 12+)
- OAuth 2.0 with Google (or GitHub)
- JWT tokens for session management
- Azure-managed encryption at rest for Cosmos DB
- HTTPS for all communication
