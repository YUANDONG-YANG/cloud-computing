# Phase 3 — Video Demo Plan

Run sheet and verified numbers for the graded Phase 3 video.

The spec requires: *"Create 2 versions of the file by making some changes in the
original file, update the file with 2nd version and demonstrate how the data
cleaning and result calculation is being done only once. And for all the
subsequent request for visualization is fulfilled via cache or DB query."*

| Item | Value |
| --- | --- |
| Version 1 (original) | `Project1/data/All_Diets.csv` — 7,806 rows |
| Version 2 (modified) | `Project3/data/All_Diets_v2.csv` — 7,272 rows |
| v2 generator | `Project3/data/make_v2.py` (`python Project3/data/make_v2.py`) |
| Function App | `https://cpsy300-p3-functions.azurewebsites.net` |
| Blob trigger path | `raw-data/All_Diets.csv` |
| Resource group | `cpsy300-project3-rg` |

> **Both versions must be uploaded under the blob name `All_Diets.csv`.** The
> trigger in `backend/function_app.py` is bound to the literal path
> `raw-data/All_Diets.csv`. Uploading the second version as
> `All_Diets_v2.csv` will not fire anything and the dashboard will not move.

---

## 1. What changed between v1 and v2

Three deliberate edits, applied by `Project3/data/make_v2.py`. Everything else
in the file is byte-identical: same 8 columns, same order, same dtypes, same
UTF-8 encoding, same CRLF line endings, no nulls.

| # | Edit | Rows affected |
| --- | --- | --- |
| A | `Protein(g)` tripled on every **vegan** row | 1,522 modified |
| B | One new **keto** recipe appended: `DEMO V2 Ultra Protein Power Bowl`, american, 1500 g protein / 12 g carbs / 40 g fat | 1 added |
| C | Every **paleo** row with cuisine `american` removed | 535 deleted |

Net row count: 7,806 − 535 + 1 = **7,272**.

### 1.1 Verified before/after numbers

All figures below were produced by running `Project3/backend/nutrition.py`'s
`clean_data()` + `precompute_all()` over each file. They are the exact values
the blob trigger writes to Cosmos DB, so they are what the dashboard will show.

**Header pill — total recipes** (`total_recipes`)

| v1 | v2 |
| --- | --- |
| 7,806 recipes | 7,272 recipes |

**Bar chart + heatmap — average macros per diet** (`average_macros`,
`heatmap.values`)

| Diet | Protein v1 | Protein v2 | Carbs v1 | Carbs v2 | Fat v1 | Fat v2 |
| --- | --- | --- | --- | --- | --- | --- |
| dash | 69.28 | 69.28 | 160.54 | 160.54 | 101.15 | 101.15 |
| keto | 101.27 | **102.19** | 57.97 | 57.94 | 153.12 | 153.04 |
| mediterranean | 101.11 | 101.11 | 152.91 | 152.91 | 101.42 | 101.42 |
| paleo | 88.67 | **87.34** | 129.55 | **116.58** | 135.67 | **129.36** |
| vegan | **56.16** | **168.47** | 254.00 | 254.00 | 103.30 | 103.30 |

The headline number to narrate: **vegan average protein 56.16 g → 168.47 g.**
The protein ranking inverts — vegan goes from last to first:

- v1: keto > mediterranean > paleo > dash > **vegan**
- v2: **vegan** > keto > mediterranean > paleo > dash

paleo's carbs and fat move as a side effect of edit C (the removed
american-cuisine paleo recipes were above-average in both).

**Pie chart — recipe count per diet** (`recipe_counts`)

| Diet | v1 | v2 | Change |
| --- | --- | --- | --- |
| dash | 1,745 | 1,745 | — |
| keto | 1,512 | **1,513** | +1 (edit B) |
| mediterranean | 1,753 | 1,753 | — |
| paleo | **1,274** | **739** | −535 (edit C) |
| vegan | 1,522 | 1,522 | — |

The paleo slice drops from 16.3 % to 10.2 % of the pie.

**Scatter plot — top 5 protein recipes per diet** (`top_recipes`)

New #1 overall, and the keto list shifts down by one:

| Rank (keto) | v1 | v2 |
| --- | --- | --- |
| 1 | Sara Louise's Keto Smoked Holiday Turkey — 1092.00 | **DEMO V2 Ultra Protein Power Bowl — 1500.00** |
| 2 | Mayo Free Deviled Eggs (Paleo, Whole30 + Keto) — 766.99 | Sara Louise's Keto Smoked Holiday Turkey — 1092.00 |
| 3 | Low Carb Beef and Cheddar Cauliflower Bake — 710.81 | Mayo Free Deviled Eggs (Paleo, Whole30 + Keto) — 766.99 |
| 4 | Orange and Five-Spice Roasted Chicken Legs — 677.22 | Low Carb Beef and Cheddar Cauliflower Bake — 710.81 |
| 5 | Low Carb Salmon Cakes (Keto, Grain Free) — 656.95 | Orange and Five-Spice Roasted Chicken Legs — 677.22 |

1500.00 g is above the v1 dataset maximum of 1273.61 g, so the new point sits
alone at the far right of the scatter plot.

Paleo loses its #2 ("Turkey Soup", american cuisine) to edit C:

| Rank (paleo) | v1 | v2 |
| --- | --- | --- |
| 1 | Swiss Paleo's Homemade Italian & Chorizo Sausage — 1273.61 | Swiss Paleo's Homemade Italian & Chorizo Sausage — 1273.61 |
| 2 | **Turkey Soup — 1142.58** | Orange and Five-Spice Roasted Chicken Legs — 677.22 |
| 3 | Orange and Five-Spice Roasted Chicken Legs — 677.22 | Vietnamese Pho Pressure Cooker (Noodle Soup) — 602.91 |
| 4 | Vietnamese Pho Pressure Cooker (Noodle Soup) — 602.91 | Paleo Slow Cooker Honey Garlic Chicken and Vegetables — 501.65 |
| 5 | Paleo Slow Cooker Honey Garlic Chicken and Vegetables — 501.65 | **Pad Thai Recipe (Grain-Free, Paleo, Gluten Free) — 496.20** |

Vegan's five entries keep the same names and order but every protein value
triples — a clean visual of edit A:

| Vegan recipe | v1 | v2 |
| --- | --- | --- |
| Tangy Teriyaki Salmon | 431.10 | 1293.30 |
| Mini nut roasts with candied carrots | 421.72 | 1265.16 |
| Vegan Pinto Bean Chili | 381.55 | 1144.65 |
| Vegan Chili and Cornbread Casserole | 319.54 | 958.62 |
| Kentucky fried seitan | 317.43 | 952.29 |

**Most common cuisine per diet** (`common_cuisines`)

| Diet | v1 | v2 |
| --- | --- | --- |
| dash | american (639) | american (639) |
| keto | american (663) | american (664) |
| mediterranean | mediterranean (1,274) | mediterranean (1,274) |
| paleo | **american (535)** | **italian (171)** |
| vegan | american (925) | american (925) |

**Filter dropdowns** — unchanged on purpose, so the filter UI stays stable
across the two uploads: 5 diet types, 19 cuisine types in both versions.

**Recipe table — totals the presenter can read off the pager**

| View (pageSize 20) | v1 | v2 |
| --- | --- | --- |
| No filter | 7,806 results / 391 pages | 7,272 results / 364 pages |
| `diet=paleo` | 1,274 results / 64 pages | **739 results / 37 pages** |
| `diet=vegan` | 1,522 results / 77 pages | 1,522 results / 77 pages |
| `search=chicken` | 732 results / 37 pages | 680 results / 34 pages |
| `search=demo v2` | **0 results** | **1 result** |

---

## 2. Run sheet

### Before you hit record

1. `./deploy.sh` has been run and finished. Resources exist.
2. `curl https://cpsy300-p3-functions.azurewebsites.net/api/health` returns
   `"cosmosdb": "connected"`.
3. **Clear the cache** so point (a) starts from an honest empty state. In the
   Azure Portal → Cosmos DB `cpsy300-p3-cosmos` → Data Explorer →
   `nutritiondb` → `cache`, delete `insights_cache`, `recipes_meta` and every
   `recipes_chunk_***` document. Then confirm:
   ```bash
   curl https://cpsy300-p3-functions.azurewebsites.net/api/health
   ```
   `insights_cached` must read `false` and `recipe_count` `0`.
4. Confirm `ENABLE_DEMO_FALLBACK` is `false` in the Function App settings. If
   it is `true`, an empty cache looks identical to a working one and the demo
   proves nothing.
5. Open a log stream and leave it visible in a second window — this is the
   evidence for "computed only once":
   ```bash
   cd Project3/backend
   func azure functionapp logstream cpsy300-p3-functions
   ```
   Portal alternative: Function App → Functions → `blob_trigger_clean` →
   **Invocations**. The invocation count is the cleanest on-camera proof.
6. Keep a shell open with the storage connection string exported:
   ```bash
   STORAGE_CONN=$(az storage account show-connection-string \
     --name cpsy300p3storage --resource-group cpsy300-project3-rg \
     --query connectionString -o tsv)
   ```
7. Have a browser DevTools window ready on the **Network** tab. The `source`
   and `updated_at` fields of the `/api/insights` response are the hard
   evidence; the UI pill shows `source` but not `updated_at`.

---

### (a) Caching: computed once, served from the DB thereafter

**a1 — Show the API refuses anonymous callers (also covers rubric item 9).**

```bash
curl -i https://cpsy300-p3-functions.azurewebsites.net/api/insights
```

Expected on camera:

```
HTTP/1.1 401 Unauthorized
Content-Type: application/json
{"error": "Authentication required. Please log in."}
```

Same for the recipe endpoint:

```bash
curl -i https://cpsy300-p3-functions.azurewebsites.net/api/recipes
```

**a2 — Show the cache is empty before any upload.**

```bash
curl -s https://cpsy300-p3-functions.azurewebsites.net/api/health
```

Point at `"insights_cached": false`, `"recipe_count": 0`.

**a3 — Upload version 1. This fires the blob trigger.**

```bash
az storage blob upload \
  --container-name raw-data \
  --file Project1/data/All_Diets.csv \
  --name All_Diets.csv \
  --connection-string "$STORAGE_CONN" \
  --overwrite true
```

**a4 — Narrate the log stream.** The cleaning and pre-computation happen here,
once, inside the trigger. Expected lines, in order:

```
Blob trigger fired: raw-data/All_Diets.csv (... bytes)
Loaded 7806 rows from blob
Cleaned data: 7806 rows
Insights stored in Cosmos DB
Pre-computed insights cached
Stored 7806 recipes across 4 Cosmos documents
Stored 7806 recipe records for search
Cleaned CSV saved to clean-data/cleaned_recipes.csv
Blob trigger completed in ...s
```

Say out loud: *"`Cleaned data: 7806 rows` is the only place cleaning happens.
Watch for it not appearing again."*

**a5 — Show the cleaned output.** Storage account → Containers → `clean-data` →
`cleaned_recipes.csv` exists, with a timestamp matching the trigger.

**a6 — Log in and show the dashboard.** Open the static-website frontend URL,
log in (see section (b) — do the registration there or reuse the account), and
let the charts render. Status pill should read **"Served from Cosmos DB"**.
Confirm the v1 numbers from section 1.1: 7,806 recipes, vegan protein 56.16,
paleo 1,274.

**a7 — The key beat: refresh repeatedly, nothing recomputes.** Hard-refresh the
dashboard 4–5 times. Each time, point at:

- the status pill: still **"Served from Cosmos DB"** (never "fallback", never
  "memory");
- the response-time pill: tens of milliseconds, not the seconds the trigger
  took;
- DevTools → Network → `insights` → Response: `"source": "cosmosdb"` and an
  `"updated_at"` timestamp that is **identical on every refresh** — the data is
  the same stored document, not a fresh calculation;
- the log stream: **no new `Cleaned data:` or `Blob trigger fired` line.**

Every refresh is a Cosmos DB read. `get_insights()` in `backend/cache.py` has
no code path that recalculates — if the document is missing it returns 503, it
does not fall back to computing.

Optional contrast shot:

```bash
TOKEN=<paste the JWT from DevTools / localStorage>
curl -s -H "Authorization: Bearer $TOKEN" \
  https://cpsy300-p3-functions.azurewebsites.net/api/insights \
  | python -m json.tool | head -20
```

Run it twice. `updated_at` is the same both times; `response_time_ms` is small.

**a8 — Upload version 2 over the same blob name.**

```bash
az storage blob upload \
  --container-name raw-data \
  --file Project3/data/All_Diets_v2.csv \
  --name All_Diets.csv \
  --connection-string "$STORAGE_CONN" \
  --overwrite true
```

**a9 — Show the trigger firing exactly once.** The log stream should produce
one new block, not a loop:

```
Blob trigger fired: raw-data/All_Diets.csv (... bytes)
Loaded 7272 rows from blob
Cleaned data: 7272 rows
Insights stored in Cosmos DB
Pre-computed insights cached
Stored 7272 recipes across 4 Cosmos documents
Stored 7272 recipe records for search
Cleaned CSV saved to clean-data/cleaned_recipes.csv
Blob trigger completed in ...s
```

Then show Function App → `blob_trigger_clean` → **Invocations**: exactly **two**
invocations for the whole recording — one per upload, none for the refreshes.

**a10 — Refresh the dashboard once and narrate the new numbers.** Read them
straight off section 1.1:

- header pill: 7,806 → **7,272 recipes**
- bar chart / heatmap: vegan protein 56.16 → **168.47** — vegan is now the
  highest-protein diet instead of the lowest
- pie chart: paleo 1,274 → **739**
- scatter plot: new #1 at the far right, **"DEMO V2 Ultra Protein Power Bowl",
  1500.00 g** (previous keto leader was 1092.00)
- most common paleo cuisine: **american → italian**
- status pill: still **"Served from Cosmos DB"**, and `updated_at` in the
  Network tab is now the *new* trigger's timestamp

**a11 — Refresh several more times.** Numbers stay on the v2 values, pill stays
"Served from Cosmos DB", log stream stays silent. One computation, many cached
reads.

---

### (b) Authentication: registration, login, GitHub OAuth

**b1 — Dashboard is gated.** Paste the dashboard URL directly into a fresh
incognito window with no token. It redirects to `login.html`.

**b2 — API is gated, not just the UI.** Re-run the a1 `curl` if it was not
already shown, and say that the redirect is cosmetic while the 401 is the real
control:

```bash
curl -i https://cpsy300-p3-functions.azurewebsites.net/api/insights
# HTTP/1.1 401 Unauthorized
# {"error": "Authentication required. Please log in."}
```

**b3 — Register.** On `login.html`, switch to the Register tab and submit:

| Field | Value |
| --- | --- |
| Name | `Demo Student` |
| Email | `demo.student@example.com` |
| Password | `CloudDemo2026!` (minimum 8 characters, enforced in `models.py`) |

Registration returns HTTP 201 with a JWT and logs you straight in. Show the
DevTools Network response: `token` present, and the `user` object contains **no
password field**.

**b4 — Show the password is hashed, not stored.** Azure Portal → Cosmos DB →
Data Explorer → `nutritiondb` → `users` → the new document. Point at
`password_hash` starting with `$2b$12$` — bcrypt, 12 rounds. There is no
plaintext password anywhere in the document.

**b5 — Log out, then log in.** Click Logout (token discarded), then log in with
the same email/password. Show the header now displays `Demo Student` and a
Logout button.

**b6 — Show the live security panel.** Scroll to the security cards on the
dashboard — they are filled from `/api/health`, not hardcoded:

```bash
curl -s https://cpsy300-p3-functions.azurewebsites.net/api/health \
  | python -m json.tool
```

Expected: `"password_hashing": "bcrypt (12 rounds)"`,
`"user_store": "Cosmos DB"`,
`"encryption_at_rest": "AES-256 (Cosmos DB, service-managed)"`,
`"token": "JWT HS256, 24h"`.

**b7 — GitHub OAuth flow.** Log out. On `login.html`, click **"Sign in with
GitHub"**. Narrate each hop:

1. Browser goes to `/api/auth/oauth/github`, which 302-redirects to
   `github.com/login/oauth/authorize` with a `state` parameter.
2. GitHub's authorization screen appears — approve it.
3. GitHub redirects back to
   `https://cpsy300-p3-functions.azurewebsites.net/api/auth/oauth/github/callback?code=...&state=...`.
4. The function verifies `state` (CSRF protection), exchanges the code for an
   access token, reads the GitHub profile, creates or finds the user, and
   302-redirects to `<frontend>/index.html#token=<JWT>`.
5. Point out that the token arrives in the URL **fragment** — browsers never
   send fragments to the server, so the JWT stays out of server logs and
   referrer headers.
6. The dashboard loads with the GitHub display name in the header.

**b8 — Show the OAuth user in the database.** Cosmos DB → `users` → the new
document has `"provider": "github"`, a `provider_id`, and **no**
`password_hash` — there is no password to store for a federated login.

> If the GitHub OAuth app is not registered, `GITHUB_CLIENT_ID` will be empty
> and this button will fail. Register it before recording: GitHub → Settings →
> Developer settings → OAuth Apps → New OAuth App, with the callback URL
> exactly `https://cpsy300-p3-functions.azurewebsites.net/api/auth/oauth/github/callback`,
> then set `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` in the Function App
> settings and restart the app.

---

### (c) Data interaction: filter, search, pagination

Do this section after the v2 upload so the numbers match the v2 column in
section 1.1.

**c1 — Diet filter.** Recipe table → diet dropdown → `paleo`. The result count
reads **739**, pager reads **37 pages**. Switch to `vegan` → **1,522 results,
77 pages**. Clear the filter → **7,272 results, 364 pages**.

Say that this is served from the cached recipe records in Cosmos DB — filtering
happens over the already-cleaned dataset, with no recomputation. The log stream
stays silent throughout.

**c2 — Keyword search.** Type `chicken` into the search box. It is debounced,
so pause after typing. Result: **680 results, 34 pages**. Note that the search
spans recipe name, cuisine and diet.

Then search `demo v2` → exactly **1 result**: `DEMO V2 Ultra Protein Power
Bowl`, keto, american, 1500 g protein. This is the row added in v2, so it also
proves the recipe cache was refreshed by the second trigger, not just the
chart cache.

**c3 — Filter and search together.** Set diet `keto` and search `demo v2` →
1 result. Set diet `paleo` and search `demo v2` → 0 results, with the empty
state message. This shows the filters compose.

**c4 — Pagination.** With the filter cleared (7,272 results / 364 pages):

- click **Next** a few times and show the page indicator and the changing rows;
- jump to a numbered page;
- click **Previous** back;
- go to page 1 and show **Previous** is disabled; go to the last page and show
  **Next** is disabled.

**c5 — Show the endpoint behind it.** Optional but strong:

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://cpsy300-p3-functions.azurewebsites.net/api/recipes?diet=paleo&page=2&pageSize=20" \
  | python -m json.tool | head -15
```

Point at `"source": "cache"`, `"total": 739`, `"totalPages": 37`,
`"page": 2`, `"hasPrev": true`.

---

## 3. Timing: the Consumption-plan trigger polls

**On the Functions Consumption plan the blob trigger is not instant.** It works
by scanning the storage logs and the container for changes, and when the app has
scaled to zero the scan only resumes once the host is running again. The delay
after `az storage blob upload` is typically seconds to a couple of minutes, but
**it can take up to about 10 minutes**, and it is longest for the *first*
upload after the app has been idle.

Plan for this rather than being surprised by it on camera. Pick one:

- **Wait on camera.** Keep the log stream visible and narrate the wait: *"On
  the Consumption plan the blob trigger polls for changes rather than being
  pushed an event, so this takes a few minutes to fire."* This is the most
  honest option and shows you understand the platform.
- **Say so and cut.** State the same sentence, stop recording, wait for the
  trigger, resume once the new log block has appeared, and show the invocation
  timestamps to prove nothing was faked.

Practical tips:

- **Warm the app first.** Call `curl .../api/health` right before the upload.
  The host is then already running and picks up the change much sooner than if
  it has to cold-start.
- **Do not re-upload while waiting.** Each overwrite changes the blob's ETag
  and queues another invocation, which would show up as two firings and
  undercut the "exactly once" claim.
- **Do not refresh frantically either.** The dashboard will keep serving the
  *previous* version's cached numbers until the trigger finishes, which is
  correct behaviour and worth saying out loud — but a viewer who sees old
  numbers without that explanation will read it as a bug.
- Mention, as the production fix, that an **Event Grid-based blob trigger**
  (`@app.event_grid_trigger`) or a Premium/Always-On plan would make this
  push-based and near-instant. Saying this earns the design point even though
  the Consumption plan is the right choice for a student credit.

---

## 4. After recording

Resources bill by the hour whether or not anyone uses them:

```bash
cd Project3
./teardown.sh
```
