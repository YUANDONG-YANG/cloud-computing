# Project 3 — independent audit, 2026-10-02

**Snapshot.** Audited against the working tree at `0554ea4` (and `209da08`
before it) **plus uncommitted edits** another session was making while this
ran. Project 3 was a moving
target: the single largest finding of the first pass was fixed mid-audit (see
"Already fixed" below). Re-check anything here against the current files before
acting on it.

**Method.** Unlike every earlier review in this folder, the toolchain was
installed this time (`get-pip.py --user`; pandas 2.3.3, pytest 9.1.1,
flake8 7.4.1, azure-functions 1.25.0, azure-cosmos 4.17.1, bcrypt 5.0.0,
PyJWT 2.3.0). So the claims below marked **executed** were run, not reasoned
about. Nothing was run against Azure — no subscription.

---

## Executed, not inferred

| Check | Result |
|---|---|
| `python -m pytest -q` (Project 3) | **109 passed**, 5.8 s |
| `python -m pytest -q` (Project 2) | **37 passed**, flake8 clean |
| `bash -n deploy.sh`, `bash -n teardown.sh` | clean |
| `node --check` on all frontend JS | clean |
| `python -m py_compile` on all backend modules | clean |

Note on the test count: this number keeps moving because the suite is still
growing. A run gave 99 against the committed state, 109 during this audit, and
143 after the OAuth-state and backend-defect tests landed.
`review/score-risk-2026-10-02.md:91` now says 143; `docs/evidence/tests.log` is
regenerated from a real run and is the figure to quote.

`Project3/` has no `.flake8`, so flake8 falls back to 79 columns and reports
long lines that Projects 1 and 2 do not (both pin `max-line-length = 110`).
Two lines in `backend/function_app.py` exceed even 110, and
`backend/models.py:9` imports `typing.Optional` without using it. Cosmetic.

---

## Verified as genuinely working — do not re-litigate

The security block (30 marks of code) was checked line by line and is real:

- Both data endpoints verify the JWT in the handler and answer 401
  (`function_app.py:259`, `:355`); `auth/me` too (`:582`). `health` is public
  by design. Platform auth level is `ANONYMOUS` everywhere, so the handler
  check is what matters — and it is present.
- `verify_token` pins the algorithm (`algorithms=[JWT_ALGORITHM]`), which
  closes `alg: none` forgery. `JWT_SECRET` has no default and is fatal on
  Azure (`auth.py:29-36`, keyed off `WEBSITE_INSTANCE_ID`).
- bcrypt at 12 rounds with a 72-byte guard rejected as a 400 before it can
  raise (`models.py:85`, backstopped at `auth.py:77-80`). Plaintext is never
  stored; `to_public()` omits the hash and both handlers use it (`:526`, `:568`).
- OAuth: the `state` is signed **and bound to the browser** — a 10-minute
  signed value mirrored in an HttpOnly `SameSite=Lax` cookie, and
  `verify_state_request` (`auth.py:200-212`) requires the signature to verify,
  the cookie to be present, and the two to match under `compare_digest` before
  the code exchange. That is genuine login-CSRF protection. The token returns
  in the **URL fragment** (`function_app.py:721`),
  consumed and scrubbed by `auth.js:149-172` via `index.html`; account linking
  requires a provider-verified email (`:699-704`).
- The client-side decode is explicitly labelled display-only
  (`auth.js:60-77`) with enforcement server-side. Correct architecture.
- Cosmos user lookups are **parameterized** (`function_app.py:85-86`,
  `:102-104`) — real injection safety.
- Output escaping on the recipe table (`app.js:473-477` via `textContent`).

Also verified correct: the diet filter, keyword search and pagination trace
cleanly end to end with matching parameter names on both sides (`diet`,
`search`, `page`, `pageSize`); the cache layer has no path that recomputes on
read; `ENABLE_DEMO_FALLBACK` defaults off and the dashboard labels sample data
as such; `teardown.sh` really does delete everything `deploy.sh` creates.

`docs/demo-plan.md` is the strongest document in the repo. Its before/after
figures were independently recomputed from both CSVs and every one matched —
row counts, all 30 average-macro cells, per-diet counts, top-5 names and
protein values, cuisine flips, and all the pager figures. The narration is
factually safe.

---

## Already fixed mid-audit — ignore any report that still lists it

The first pass found what looked like an 85-mark defect: the deployed frontend
resolved `/api` same-origin, while `deploy.sh` hosts it on a blob static
website whose origin has no API and no reverse proxy. That is **fixed**:
`frontend/config.js` resolves `window.API_BASE` from an `__API_BASE__`
placeholder, all three pages load it first, `deploy.sh:213` substitutes the
absolute Function URL into a staging copy and `:214` aborts if the
substitution did not take, and `README.md:66-79` documents the whole chain.
This is Project 2's mechanism ported over, correctly.

---

## Live findings

### Priority 1 — fabricated figures still in the submission set

These are the same failure pattern that nearly cost Project 2 its marks.
`score-risk-2026-10-02.md:115` claims the wrong figures "were corrected in the
overview report"; that claim is false — these survived.

| # | Where | Claim | Reality |
|---|---|---|---|
| 1 | `docs/reports/Project3-Master-Overview.html:1216,1218,1220,1222,1224` | pie chart: Keto 20.2 %, Med 20.0 %, Dash 19.8 %, Paleo 19.8 %, Vegan 20.2 % | mediterranean **22.5 %**, dash **22.4 %**, vegan **19.5 %**, keto **19.4 %**, paleo **16.3 %**. The printed values are the withdrawn invented counts over 7,806 (1580/7806 = 20.24 %, …). The chart contradicts the report's own correct table at `:499-519` |
| 2 | same file `:1452` | `curl /api/recipes?diet=keto` → `total: 1580` given as the acceptance criterion | keto is **1,512** (v1) / 1,513 (v2). Whoever runs this on camera will see 1,512 and think the cache is broken |
| 3 | `docs/Phase3-Analysis.md:127` | "dash ~1561, keto ~1890, mediterranean ~1752, paleo ~1553, vegan ~1050" | dash **1745**, keto **1512**, mediterranean **1753**, paleo **1274**, vegan **1522**. A *third* distinct set of invented counts, summing to 7,806 so it looks self-consistent; keto is off by 378. The macro table directly above it is correct, which makes these look authoritative |

**Status of findings 1–3: all three are now fixed.** The pie-chart wedges and
legend were redrawn from the real counts (paleo is visibly the smallest slice,
not an equal fifth), the `total: 1580` acceptance criterion is now `total: 1512`,
and `Phase3-Analysis.md` carries the exact counts with a note recording the
correction. Finding 4 (two CORS layers) is also resolved: `deploy.sh` no longer
calls `az functionapp cors add`, and the application owns the headers, which
makes the `FRONTEND_URL` setting load-bearing.

### Priority 2 — `deploy.sh` defects that strand a half-provisioned deployment

| # | Where | Problem |
|---|---|---|
| 4 | `deploy.sh:235` + `function_app.py:135` | **Two CORS layers.** `az functionapp cors add` and an in-code `Access-Control-Allow-Origin` both apply. On the Functions host these stack into a duplicated header, which browsers reject outright. This is the identical bug fixed in Project 2 by deleting the in-code headers. It was harmless while the frontend called `/api` same-origin; now that the API-URL fix makes the calls genuinely cross-origin, it is on the critical path — and its browser symptom is indistinguishable from the bug just fixed. Pick one layer |
| 5 | `deploy.sh:30` (`set -euo pipefail`) with bare `cd backend` at `:189` | Paths are relative to the **caller's** cwd. Run as `Project3/deploy.sh` from the repo root and it dies at step 4 of 6 — with the resource group, storage account, Cosmos account and Function App already created and billing. Works if you `cd Project3` first, which the README implies but never states. Project 2 avoided this with `cd "$(dirname "${BASH_SOURCE[0]}")"` plus `(cd backend && …)` |
| 6 | `deploy.sh:176` | `JWT_SECRET` is regenerated on **every** run. Re-running to re-publish code mid-rehearsal silently invalidates every issued token: logged-in browsers get bounced to `login.html`. Users survive in Cosmos; sessions do not. Read the existing setting and only generate when absent |
| 7 | `deploy.sh:190` | `func azure functionapp publish … --python`. Project 2 publishes without it and works; `--python` is a legacy Core Tools selector and v4 errors on unrecognised options, while the runtime is already fixed by `az functionapp create --runtime python`. **Unverified** (`func` is not installed here). If it is rejected the script dies at step 4 with everything provisioned. The flag is unnecessary either way |
| 8 | `teardown.sh:23-26` | An `az` failure is reported as success. With an expired login, `az group exists` writes its error to stderr, stdout is empty, `grep -q true` fails, and the script prints "does not exist. Nothing to delete." and **exits 0**. This is the one script whose silent success keeps costing money |

### Priority 3 — report snippets labelled "actual source" that quote pre-fix code

Each of these hides a real fix and makes it look like the bug is still there.

| # | Where | Shows | Actually |
|---|---|---|---|
| 9 | overview `:390`, body `:438-460` — labelled `cache.py:216-294` | missing chunk → `records = []; break`, then falls through to the process-local copy | `cache.py:284-296` returns `None` immediately and comments that it deliberately will *not* fall through "which may hold an entirely different dataset". The prose 56 lines above (`:382`) describes the correct behaviour — the snippet contradicts it |
| 10 | overview `:1364-1376` — labelled `function_app.py:363-374` | `if not recipes:` → 503 | `:363-366` is `if recipes is None:`, with a comment that an empty list is a valid answer, not a miss. `if not recipes` *is* the bug that was fixed |
| 11 | overview `:779`, body `:781-784` — labelled `auth.py:64-93` | three-line `hash_password`, no length check | `auth.py:64-81` has `MAX_PASSWORD_BYTES = 72` and raises above it. This is the long-password-500 fix, hidden |
| 12 | overview — six citations | `auth.py:108-131`, `:158-266`, `:158-170`; `function_app.py:602-711`, `:621-622`, `:501` | all exactly **+14 lines** stale (`auth.py:122-145`, `:172-280`, `:172-182`; `function_app.py:616-725`, `:635-636`, `:515`). Written before the bcrypt and cold-cache fixes lengthened those files. A marker who spot-checks `auth.py:108` lands in `verify_token` and concludes the citations are decorative |

### Priority 4 — wrong claims about what the code does

| # | Where | Claim | Reality |
|---|---|---|---|
| 13 | overview `:1750-1752`, green **Implemented** pill | cleaning "**deduplicates**" | **Verified absent**: no `drop_duplicates` or `duplicated` anywhere in `backend/` (grepped all five modules, zero hits). `clean_data` normalises text, fills blanks, imputes macros and derives two ratios. 7,806 rows in → 7,806 out, which the demo plan's own expected log confirms |
| 14 | overview `:1630`, pill **Verified in repo** | "User input never reaches a Cosmos query… the actual design avoids query construction altogether" | **False, and self-defeating.** `function_app.py:85-86` and `:102-104` bind user-supplied email and OAuth identifiers into `SELECT … WHERE c.email = @email` via `parameters=[…]`. User input does reach a query — safely. The row denies the one piece of genuine injection-safety engineering in the repo. Rewrite it to *claim* the parameterized queries |
| 15 | overview `:492-495`, `:499-515` | Redis keys in a `diet:*` hash form | `cache.py` writes exactly two Redis **string** keys, `insights_cache` (`:25,176`) and `recipes_cache` (`:260`). No `hset`/`hgetall`, no `diet:` prefix anywhere. Residue from the withdrawn Redis-first draft |
| 16 | overview `:1137`, `:1553-1554` | look for a status pill reading `Cache: cosmosdb`, not `Demo Mode` | `app.js:545-552` can only emit `Served from Redis` / `Served from Cosmos DB` / `Served from in-process cache` / `Sample data (ENABLE_DEMO_FALLBACK is on)` / `Cache empty` / `API unreachable`. Neither string exists in the frontend. The report quotes the correct string at `:1378`, contradicting itself. Hunting a pill that cannot appear will waste demo takes |
| 17 | overview `:1133-1134` caption and the §5 mock | "numbers inside the mock are placeholders drawn from the local dataset" | A `Calories` column the dataset does not have (`:1252`); two recipe names absent from the CSV entirely; "Vegan Buddha Bowl" with macros 18.4/52.3/15.8 against its real 57.85/227.15/105.16; a 3×3 "Nutrient Correlation" heatmap when the implementation renders a 5-diet × 3-macro **average-value** grid (`nutrition.py:95-99`, `dashboard.html:98`). §3's mocks were cleaned properly; §5 was missed |
| 18 | `docs/demo-plan.md:152-159` | delete the Cosmos documents, then `/api/health` "must read `insights_cached: false`" | `cache.py:181`, `:265` also write to the process-local `_memory_store`, and `get_cache_status()` reports `bool(meta) or bool(local)` (`:321-322`). On a still-warm instance health will report `insights_cached: true` with `source: "memory"` after the documents are gone. The run sheet needs "restart the Function App, or wait for scale-to-zero" or the demo's opening beat fails on camera |
| 19 | `docs/demo-plan.md:391-393` | the OAuth user document has "**no** `password_hash`" | `User.to_dict()` uses `asdict`, so the field is serialized with its empty-string default. Cosmos will show `"password_hash": ""`. Say "an empty `password_hash`" or the presenter is contradicted by their own screen |
| 20 | overview `:890` and `:1625` | "`state` is not bound to the browser session (no nonce or cookie pairing), so it is not full login-CSRF protection" — flagged as a residual gap | **Now outdated in the opposite direction: the report under-claims.** Commits `f902f6d` and `0554ea4` moved both callbacks to `verify_state_request` (`auth.py:200-212`), which checks the signature, requires the HttpOnly `p3_oauth_state` cookie and compares the two with `compare_digest`. The gap the report discloses has been closed, so the disclosure now understates the implementation. `demo-plan.md:383-384`'s "CSRF protection" wording, flagged as overstated in the first pass, is **correct as written** — leave it alone |
| 21 | `docs/demo-plan.md:482-483` | the Event Grid fix is `@app.event_grid_trigger` | In the Python v2 model it is `@app.blob_trigger(…, source=BlobSource.EVENT_GRID)`. `@app.event_grid_trigger` receives an `EventGridEvent`, not an `InputStream`, and is not a drop-in. The design point is right; the API name is wrong, and it is scripted to be said out loud |
| 22 | `docs/demo-plan.md:304-305` | "exactly **two** invocations for the whole recording" | `deploy.sh:211-219` uploads `All_Diets.csv` at deploy time, firing the trigger once before recording starts. The Invocations blade will show **three**. Narrate it or filter by timestamp |
| 23 | overview `:660-662`, `:1460` | "The result count for any given keyword is currently unknown, because the search has never run against the real dataset in a deployed environment" | It is knowable now and already known: `demo-plan.md:140` tabulates `search=chicken` → 732 results / 37 pages (v1), 680 / 34 (v2), independently recomputed as exact. The counts are a property of the dataset and the filter code, not of a deployment. The report tells the marker the team cannot predict its own results while the sister document predicts them correctly |
| 24 | `README.md:256-292` | a flat "Features Implemented" list including OAuth and "DB Encryption: Cosmos DB encrypts all data at rest" | No OAuth client is registered and no Cosmos account exists, so nothing is encrypted at rest yet. Much milder than Project 2 — the README sets no rubric statuses — but it is the document a marker opens first. One sentence near `:256` closes it |
| 25 | `docs/Phase3-Analysis.md:179`, `:133`, `:143`, `:158`, `:12` | Redis as the cache of record; frontend as "Azure Static Web App" | Settled architecture is Cosmos-only, and the frontend is blob static-website hosting. Low severity (pre-implementation requirements doc) but it contradicts the other documents on the core design decision |

### Priority 5 — small code defects, no marks attached

| # | Where | Problem |
|---|---|---|
| 26 | `models.py:72-101`, `function_app.py:493-500`, `:540-547` | A non-object JSON body (`null`, `"x"`, `[]`) reaches `body.get(...)` and raises `AttributeError` → unhandled **500** instead of 400. Only `ValueError` from `get_json()` is caught. One `isinstance(body, dict)` guard closes it |
| 27 | `function_app.py:48-71` | `_get_users()` caches only the success case — no `_tried` flag, unlike `cache.py:82-90` which gets this right. With Cosmos misconfigured, every call from `_find_user_by_email`, `_find_user_by_provider`, `_save_user` and `health_check` pays the connect failure again |
| 28 | `function_app.py:118-127` | A failed Cosmos user write falls back to `_memory_users` and register still returns **201 with a token**. The user then exists on one instance only; a later login elsewhere says "Invalid email or password." A failed durable write during registration should be a 503 |
| 29 | `function_app.py:364` | `/api/recipes` hardcodes `"source": "cache"` while `/api/insights` honestly reports `cosmosdb`/`redis`/`memory`/`fallback`. `demo-plan.md` **c5** points the camera at this field as proof the data came from the DB — it is a constant, so it proves nothing |
| 30 | `app.js:579-580`, `:462` | An expired token renders `Valid (-3h remaining)`. The `#` column uses the client's `currentPage` rather than the server's clamped `result.page` |
| 31 | `function_app.py:636`, `:640`, `:644` | An OAuth failure returns bare JSON at the `azurewebsites.net` URL with no way back into the app — a dead end on camera. Redirect to `login.html?error=…` |

---

## Real work the documents fail to claim — cheapest marks available

No Azure, no screenshots, no code needed for any of these.

1. **The 109-test suite is invisible.** The word "test" does not appear in the
   overview, the README, Phase3-Analysis or the demo plan. It is direct
   evidence for the *"demonstrate understanding of good coding practice"*
   learning objective and for the presentation: `test_auth.py:138` rejects
   `alg: none`, `:121` rejects a foreign-secret signature, `:131` rejects a
   tampered signature, `:198` proves a session token cannot double as an OAuth
   state; `test_cache.py:194-238` proves a missing chunk never yields a
   partial or stale set; `:270` proves the meta document is written last.
   `conftest.py` isolates `JWT_SECRET` and scrubs `REDIS_HOST`/`COSMOS_*` so
   tests can never touch real infrastructure. **It runs green today.**
2. **The two-version demo dataset is never mentioned** in the overview or the
   README. `data/make_v2.py` + `data/All_Diets_v2.csv` are exactly the
   artifact rubric items 1 and 2 demand ("Create 2 versions of the file"), and
   the demo plan tabulates correct before/after values for every chart. The
   overview's "Evidence still needed" blocks and its deliverables list never
   say this preparation exists, so a marker reading only the overview
   concludes the two-version demo has not been prepared. **20 marks of
   completed prep presented as absent.** `README.md`'s project structure also
   omits `data/`, `tests/`, `pytest.ini`, `docs/` and `review/`.
3. **`/api/health` and `/api/auth/me` are absent from the overview entirely.**
   `/api/health` reports live security configuration — `password_hashing`,
   `user_store`, `encryption_at_rest`, `token` — and `app.js:569-595` fills
   the dashboard's security cards from it, degrading to "Unknown (API
   unreachable)" rather than asserting anything. The overview criticises the
   old hardcoded "AES-256" but never says what replaced it.
4. **The bcrypt 72-byte boundary**, **the parameterized Cosmos queries** (see
   finding 14), and **the recipe-table output escaping** are all real
   engineering the documents either omit or actively deny.

---

## What the honesty pass got right — preserve verbatim

The overview has clearly been through a deliberate cleanup and is far better
than Project 2's was. Keep all of it: the three-level status legend, "No item
on this page is marked as working in production", the withdrawal of the 231×
and 1,850 ms figures and of the 80/100 self-score, every "Hand-drawn mockup,
not a screenshot" label, the removal of the Node.js snippets, and the explicit
disclosures that the JWT lives in `localStorage` rather than an HttpOnly
cookie, that there is no rate limiting,
and that `get_recipes()` reads every chunk per request and has never been
timed. That last one is the right call: the per-request full-dataset read is a
settled, accepted trade-off, not a defect.

---

## Still outstanding — where the marks actually are

Unchanged, and larger than everything above: nothing is deployed, no OAuth
client is registered (10 marks, binary), no evidence is captured (~20 marks),
and the video is not recorded (20 marks). See `/SUBMISSION-CHECKLIST.md` at
the repository root for the ordered run sheet.
