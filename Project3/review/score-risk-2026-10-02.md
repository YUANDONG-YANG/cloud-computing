# Project 3 (Phase 3) — Mark-Loss Analysis, 2026-10-02

> **Half of this is now fixed.** The analysis below was written against the implementation as it
> stood at commit `1049cbd`. The code defects it identifies in items 2, 4, 5, 6 and 9, and the
> `JWT_SECRET` default, were fixed afterwards — see the **Status** section at the end for what
> changed and what is still outstanding. The findings about deployment, OAuth registration,
> evidence and the video all still stand, and they are the ones that carry the marks.

Basis: rubric in `Project3/Project Phase 3.docx`, verified line by line against the code in
`Project3/backend/` and `Project3/frontend/` at commit `1049cbd`.

**These are estimates, not grades.** What matters is the *driver* column: each estimate is tied to a
defect that was confirmed in the code, and most drivers are binary — either a persistent store is
configured or the demo runs on fabricated data; either the OAuth app is registered or the button
errors out. The spread between the two scenarios below is almost entirely configuration and four
code fixes, not missing features.

## Per-item analysis

| # | Rubric item | Marks | At risk | Driver (confirmed defect) |
|---|---|---|---|---|
| 1 | Data cleaning once per CSV change | 10 | 0–3 | Blob trigger is correct (`function_app.py:158`). Risk is evidence only: nothing deployed, and on a Consumption plan the trigger polls (up to ~10 min), which can stall the live demo. |
| 2 | Result calculation once per change | 10 | 0–3 | `precompute_all` + `store_insights` are correct, and `store_insights` has a Cosmos fallback, so insights survive a Redis outage. Residual risk: `_get_fallback_insights()` returns the *real* 7806-row numbers, so an empty cache is visually identical to a working one. |
| 3 | Diet type filter | 5 | 0–5 | Depends on item 4's root cause. |
| 4 | Keyword search | 10 | 0–10 | `store_recipes`/`get_recipes` (`cache.py:171-203`) have **no Cosmos fallback** — only Redis and a process-local dict. The blob trigger and the HTTP handler are not guaranteed to share a process on Azure Functions, so without Redis `get_recipes()` returns `None` and the API serves the 15-row `_get_fallback_recipes()` demo list. Search and filter then operate on fabricated data. |
| 5 | Pagination | 5 | 0–5 | Same root cause, with a sharper consequence: 15 rows at `pageSize=20` gives `totalPages=1`, and `renderPagination` (`app.js:516`) takes the `totalPages <= 1` branch — **no pagination controls render at all**. The feature becomes invisible on video. |
| 6 | Email/password authentication | 10 | 3–10 | bcrypt-12 and JWT are genuine, so partial credit is likely. But `simulateDemoLogin` (`login.html:235-257`) forges a token whenever `fetch` rejects, and `isAuthenticated()` (`auth.js:83-99`) never verifies the signature — any password works when the backend is unreachable or CORS is misconfigured. Separately, `_memory_users` (`function_app.py:74`) means register-then-login can fail across instances if Cosmos is unset. |
| 7 | Third-party OAuth | 10 | 0–10 | Code for Google and GitHub is complete and correct. But `deploy.sh` never sets `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GITHUB_CLIENT_ID` or `GITHUB_CLIENT_SECRET`, so after deployment the consent redirect goes out with an empty `client_id` and the provider returns an error page. Binary: registered and configured, or zero. |
| 8 | DB encrypted, password hash stored | 10 | 0–10 | Hashing is correct and plaintext is never stored. Encryption at rest is a Cosmos platform default — true, but currently "evidenced" only by a hardcoded `AES-256` string in `app.js:602`, which is not evidence. If Cosmos is never provisioned, users live in `_memory_users` and there is no database to show. |
| 9 | Login required to see dashboard; name shown | 10 | 3–10 | Name and logout button are present (`dashboard.html:18-21`). But the gate is client-side only and bypassable per item 6, and `/api/insights` and `/api/recipes` are `ANONYMOUS` with no token check (`function_app.py:228`, `:304`) while the frontend sends none (`app.js:163`, `:206`). The endpoints can be read with `curl` and no credentials. |
| 10 | Presentation | 20 | 0–20 | Not started. The three required demo points each depend on the items above actually working. |

## Two scenarios

**Submit as-is** — no fixes, nothing deployed, video recorded against local fallback data:
roughly **35/100**. Items 3, 4, 5 and 7 go to zero because the features either run on fabricated
data or do not function at all; 6, 8 and 9 take partial credit for real code with a broken or
absent backing store.

**Fix four things and provision** — roughly **90+/100**. No new features are required.

## Fix order, by marks per unit of effort

1. **Give `store_recipes` a persistent backing store** (Cosmos fallback, mirroring `store_insights`).
   ~20 lines. Unlocks **20 marks** (items 3, 4, 5) and is the single highest-leverage change in the
   project. For large payloads, chunk the records or write the cleaned CSV reference instead of one
   document.
2. **Close the auth bypass.** Delete `simulateDemoLogin` and both `catch` branches that call it; add
   a `get_current_user(req)` guard returning 401 to the `insights` and `recipes` handlers; switch the
   frontend to the existing `authFetch` and redirect to `login.html` on 401. ~30 lines. Protects
   **about 20 marks** (items 6, 9).
3. **Register the Google and GitHub OAuth apps** and set the four client ID/secret app settings, plus
   `FRONTEND_URL` and the two redirect URIs. No code. **10 marks** (item 7).
4. **Provision Cosmos DB** and capture a portal screenshot of the encryption-at-rest setting, plus one
   of a stored user document showing the bcrypt hash. **10 marks** of evidence (item 8).
5. **Make the fallbacks opt-in** via an environment flag, default off, returning 503 with a visible
   banner when the cache is empty. Does not add marks directly, but it is what makes items 1 and 2
   (20 marks) *provable* on video instead of merely claimed.

Items 1, 2 and 5 are code and can be done now. Items 3 and 4 need an Azure subscription and
provider accounts.

## Demo-specific risks

- Record **after** fixing, not before — the status bar reading `Demo Mode` instead of `Cache: redis`
  is the one signal that distinguishes a working cache from a broken one, and it is on screen.
- Blob-trigger polling on a Consumption plan can delay the version-2 upload demo by minutes. Either
  switch to an Event Grid blob trigger or script the wait into the narration.
- Have `curl` output ready showing a 401 from `/api/insights` without a token. It is the cleanest
  possible evidence for item 9.

## Secrets

`JWT_SECRET` defaults to `"dev-secret-change-in-production"` (`auth.py:22`). `deploy.sh` generates a
random one, but any manual deployment that skips that step ships a publicly known signing key.
Make the app fail to start when the variable is unset outside local development. No client secret
should ever reach this repository.

## Related

- `review/gap-review-2026-10-02.md` predates the implementation and is stale.
- `docs/reports/Project3-Master-Overview.html` has since been rewritten: the fabricated Node.js
  snippets, the unmeasured "231x" figure and the 80/100 self-score are gone, and each rubric row
  now names the evidence it still needs.

---

# Status after the fixes

Everything in this section is code that exists in the repository and is covered by
`Project3/tests/` (99 tests, run with `python -m pytest Project3/tests -q`). None of it has run
against real Azure infrastructure.

## Fixed

| Was | Now |
|---|---|
| Recipes lived only in Redis and a process-local dict, so without Redis the API served a 15-row sample list and pagination collapsed to one page (items 3, 4, 5 — 20 marks) | Cosmos DB is the durable store, written in chunks under the 2 MB document limit and readable from any function instance. Redis is optional and skipped unless `REDIS_HOST` is set |
| `login.html` minted an unsigned token whenever `fetch` rejected, and `isAuthenticated()` never checked a signature, so any password worked with the API down or CORS misconfigured | The forged-token path is deleted. `/api/insights` and `/api/recipes` verify the JWT and answer 401; the page uses `authFetch` and redirects on 401 |
| Sample data mirrored the real result set, making a broken cache indistinguishable from a working one | Both endpoints answer 503 when nothing is cached. The sample data is behind `ENABLE_DEMO_FALLBACK`, default off, and the dashboard names the store it was served from |
| `JWT_SECRET` defaulted to a published string | No default. Fatal if unset on Azure, warned locally |
| OAuth had no CSRF defence, linked accounts on an unverified email, and returned the token in the query string | Signed 10-minute `state`; only a provider-verified email may claim an existing account; the token comes back in the URL fragment |
| The security cards asserted "AES-256" in markup | They read live configuration from `/api/health`, which says plainly when no database is configured |
| `deploy.sh` provisioned Redis Basic C0 and two Cosmos containers at default provisioned throughput, roughly $62/month and billing while idle | No Redis; Cosmos is serverless. `teardown.sh` deletes the resource group |
| `deploy.sh` never set `FRONTEND_URL` or the OAuth client settings, so the callback redirected to localhost and consent went out with an empty `client_id` | Both are set, and the frontend deploys first so its URL is known |

Three further defects surfaced while writing the tests and are fixed: `hash_password` passed
passwords straight to bcrypt, which accepts 72 bytes — bcrypt 4 truncated silently and bcrypt 5
raises, so on bcrypt 5 a long password returned a 500 rather than a 400; an empty-but-cached
dataset read back as a cache miss; and a missing Cosmos chunk fell through to the process-local
copy, which can hold a different dataset than the metadata describes.

The per-diet counts in the sample data were also invented — it claimed dash 1,546, keto 1,580,
mediterranean 1,564, paleo 1,543, vegan 1,573, while the dataset holds 1,745, 1,512, 1,753, 1,274
and 1,522. Corrected, and the same wrong figures were corrected in the overview report.

## Still outstanding — this is where the marks are

| # | What | Marks at stake | Needs |
|---|---|---|---|
| 1 | Nothing is deployed | gates everything | An Azure subscription, then `./deploy.sh` |
| 2 | No OAuth app registered | 10, binary | A GitHub OAuth App (about a minute) and four app settings. GitHub rather than Google: the rubric asks for at least one, and Google additionally requires a Cloud project and a consent screen |
| 3 | No evidence captured | ~20 across items 1, 2, 8 | Trigger log excerpts, a Cosmos Data Explorer screenshot of the encryption setting and of a stored bcrypt hash, and `curl -i /api/insights` returning 401 |
| 4 | No video | 20 | Record last, after 1–3. `docs/demo-plan.md` has the run sheet and the measured before/after numbers |

`data/All_Diets_v2.csv` is ready for the "cleaning runs once per change" demo. It must be uploaded
**as `All_Diets.csv`** with `--overwrite true`, because the trigger is bound to that literal blob
path; uploading it under its own name fires nothing.
