# Submission checklist — steps that need a human

Written 2026-10-02. Everything here needs an Azure subscription, a provider
account or a camera, so none of it can be done from inside this repository.
The code for both phases is complete and was verified by execution on
2026-10-02 (Project 2: 37 tests pass, flake8 clean, all three handlers run
correctly against the real `All_Diets.csv`; Project 3: 99 tests pass on
bcrypt 5).

Ordered by marks per unit of effort.

---

## 1. Register a GitHub OAuth App — about a minute, 10 marks

Phase 3 rubric item "at least one 3rd party (OAuth) login" is binary: it is 10
marks or zero. Pick **GitHub**, not Google — the rubric asks for one provider,
and Google additionally needs a Cloud project and a consent screen.

1. github.com → Settings → Developer settings → OAuth Apps → New OAuth App
2. Authorization callback URL:
   `https://<function-app>.azurewebsites.net/api/auth/oauth/github/callback`
3. Note the Client ID, generate a Client Secret.
4. After `Project3/deploy.sh` has run, set them:

```bash
az functionapp config appsettings set \
  --name <function-app> --resource-group <rg> --settings \
  "GITHUB_CLIENT_ID=<id>" "GITHUB_CLIENT_SECRET=<secret>" \
  "FRONTEND_URL=https://<frontend-host>"
```

Never commit the secret. `local.settings.json` is git-ignored; its
`.example` sibling is the template.

---

## 2. Deploy Phase 2 — unlocks 40 marks

Needs: `az login`, Azure Functions Core Tools (`func`), and the Static Web Apps
CLI (`npm install -g @azure/static-web-apps-cli`).

```bash
cd Project2 && ./deploy.sh
```

The script does 7 steps: resource group → storage + CSV upload → Function App
+ app settings → publish backend → create Static Web App (unlinked, so no
GitHub token needed) → build the frontend with the live API URL injected →
scope CORS to the dashboard origin and smoke-test all three endpoints.

Note the Static Web App goes to **eastus2** while everything else is eastus,
because SWA is not offered in eastus. If the `swa` CLI is missing the script
warns and skips only the frontend upload; install it and re-run.

Afterwards paste the two real URLs into `Project2/README.md` and
`Project2/docs/reports/Project2-Master-Overview.html`, which currently carry
`<function-app>` / `<static-web-app>` placeholders on purpose.

---

## 3. Deploy Phase 3

```bash
cd Project3 && ./deploy.sh      # Cosmos serverless, no Redis
# when finished with the demo:
cd Project3 && ./teardown.sh    # deletes the resource group
```

---

## 4. Capture evidence — about 20 marks of Phase 3, 10 of Phase 2

Every screenshot must show the **date and time**. Do not capture any frame
that reveals a storage connection string, an account key or a client secret.

**Phase 2** — fill the nine `[PENDING SCREENSHOT]` placeholders in
`Project2/docs/Phase2-Documentation.md`, then export that file to PDF:
resource group, Function App overview, storage container showing the blob,
Static Web App overview, the live dashboard in a browser, and the three
endpoints answering in a browser or Postman.

**Phase 3**:
- Blob-trigger log excerpt showing the clean + precompute running **once**
- Cosmos Data Explorer showing the encryption-at-rest setting
- A stored user document showing the bcrypt hash (rubric item 8 wants proof
  that no plaintext password is stored)
- `curl -i https://<function-app>.azurewebsites.net/api/insights` returning
  **401** with no token — the cleanest possible evidence for the auth gate

---

## 5. Record the Phase 3 video — 20 marks, do this last

`Project3/docs/demo-plan.md` has the run sheet. Three required points:

1. **Cleaning and calculation happen only once per CSV change.** Upload the
   second version and show the recompute firing once, then show later page
   loads being served from Cosmos.

   Critical: upload `Project3/data/All_Diets_v2.csv` **under the name
   `All_Diets.csv`** with `--overwrite true`. The trigger is bound to that
   literal blob path, so uploading it under its own name fires nothing.

   ```bash
   az storage blob upload --container-name raw-data \
     --file Project3/data/All_Diets_v2.csv --name All_Diets.csv \
     --overwrite true --connection-string "<conn>"
   ```

   Plan for latency: on a Consumption plan the blob trigger polls and can take
   up to about ten minutes. Either narrate the wait or switch the binding to
   Event Grid before recording.

2. **Registration, login and the OAuth flow**, explained and demonstrated.
3. **Data interaction**: the diet filter, the keyword search and pagination.

---

## Not blocking, worth knowing

- GitHub Actions results have not been checked from this machine (`gh` is not
  installed). Project 2's `project2-tests` job runs pytest, flake8 and
  `bash -n deploy.sh`; confirm it is green in the Actions tab.
- `Project3/` has no `.flake8`, so flake8 falls back to a 79-character limit
  and reports long lines that Project 1 and Project 2 do not (both pin
  `max-line-length = 110`). Two lines in `Project3/backend/function_app.py`
  exceed 110 as well, and `Project3/backend/models.py:9` imports
  `typing.Optional` without using it. Cosmetic, no marks attached.
