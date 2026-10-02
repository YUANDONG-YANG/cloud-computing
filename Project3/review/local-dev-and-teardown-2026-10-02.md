# Local Dev, Teardown and Cost Findings (2026-10-02)

Recorded from the Windows host (not the Ubuntu VM). Everything below was executed and verified, not
inferred. Written because two sessions are working this repo from two machines and these findings are
not in any doc yet.

## 1. Blocker: the documented Quick Start fails on current tool versions

`README.md` -> Local Development -> Quick Start step 5 uploads `All_Diets.csv` with the Azure CLI. On
Azure CLI 2.90.0 against Azurite 3.35.0, all three `az storage` commands fail:

```
ERROR: The API version 2026-04-06 is not supported by Azurite. Please upgrade Azurite to
latest version and retry. ... Azurite command line parameter "--skipApiVersionCheck" ... can
skip this error.
ErrorCode:InvalidHeaderValue
```

The CLI sends a newer Storage API version than Azurite accepts. Azurite must be started with
`--skipApiVersionCheck`:

```bash
azurite --silent --skipApiVersionCheck --location <data-dir>
```

With the flag, all three commands succeed: both containers created, `All_Diets.csv` uploaded at
702,493 bytes (byte-identical to `Project1/data/All_Diets.csv`).

**This is not a Docker-vs-npm difference.** `docker-compose.yml` has the same gap -- its azurite
service `command:` does not pass the flag either, so starting Azurite through Compose hits the same
error. Two places need the flag:

| File | What to change |
|---|---|
| `docker-compose.yml` | azurite service `command:` -- add `--skipApiVersionCheck` |
| `README.md` | Quick Start step 1, and the prerequisites note |

Why it matters beyond convenience: step 5 is what fires the blob trigger on
`raw-data/All_Diets.csv`. Until it runs, `/api/insights` and `/api/recipes` answer 503 by design.
The blob trigger is the Phase 3 ingestion path the first two rubric rows (20 marks) are scored on, so
a dead step 5 blocks the whole demo.

## 2. Docker is not needed on the host for Phase 3 local dev

Docker is installed in the Ubuntu VM, not on the Windows host. Phase 3 does not need it:

- `Project Phase 3.docx` mentions Docker **0 times**.
- The only required service in `docker-compose.yml` is Azurite. Redis is behind an opt-in profile and
  the deployed app does not use it; the Cosmos emulator is deliberately absent.
- `npm i -g azurite` is a drop-in replacement. Verified: Compose maps 10000/10001/10002, which are
  also the npm default ports, and `local.settings.json.example` uses `UseDevelopmentStorage=true`,
  which resolves to the same endpoints either way. No docker-specific hostname appears in the
  settings example.

So only Quick Start step 1 changes; steps 2-7 are unchanged.

Host toolchain, verified working:

```
az       D:\Tools\AzureCLI\CLI2\wbin\az.cmd      2.90.0
azurite  C:\Program Files\nodejs\azurite         3.35.0
func     C:\Users\...\Programs\Azure\func.exe    4.1.0
python 3.11.9   node v20.19.5   npm 10.8.2   git 2.31.1
```

Two notes on the Windows host specifically:

- The Azure CLI MSI ignores `TARGETDIR`; it always installs to `C:\Program Files\Microsoft SDKs\Azure\CLI2`.
  The install above is an `msiexec /a` extraction instead, so it is not a registered install:
  `az upgrade` does not work and it is absent from Add/Remove Programs. Upgrading means
  re-extracting a newer MSI over the same directory.
- `wbin` ships an extensionless `az` shell wrapper alongside `az.cmd`, so Git Bash resolves a bare
  `az`. Without it, every `az` call in a `.sh` script would fail, because Git Bash does not append
  `.cmd`.

Debugging gotcha hit while testing: `pkill -f azurite` from Git Bash does not kill the Windows
process. A stale Azurite keeps the ports, the new one fails to bind, and `--silent` swallows the
error -- so the flag looks like it had no effect. Use `Stop-Process`, and drop `--silent` when
debugging.

## 3. Teardown: Phase 2 had no script, Phase 3's is not executable

Phase 2 and Phase 3 deploy into **different resource groups**, so one teardown does not cover both:

```
Phase 2   cpsy300-nutritional-insights-rg
Phase 3   cpsy300-project3-rg
```

- Phase 2 had no teardown script at all. Added `Project2/teardown.sh`, modelled on this project's,
  plus two things that one misses: it warns when a `RESOURCE_GROUP` override is the likely reason the
  group was not found, and it cross-references the other phase's group.
- `Project3/teardown.sh` is mode **100644** in git, not executable (`Project2/deploy.sh` is 100755).
  Its own usage comment says to `chmod +x` first, so this is friction rather than a bug -- but the
  friction lands at the exact moment someone is trying to stop the billing. One
  `git update-index --chmod=+x Project3/teardown.sh` fixes it for everyone.

The silent-failure class this project already guards against applies to the override too: deploy with
`RESOURCE_GROUP=x ./deploy.sh` and forget it at teardown, and the script prints "Nothing to delete"
and exits 0 while the resources keep billing. Simplest mitigation: do not override the defaults.

Final check after both demos are recorded:

```bash
az group list --query "[].name" -o tsv     # neither group should appear
```

## 4. Cost audit: both scripts are already at the floor

Audited for resources that bill hourly while idle. None found.

| Resource | Setting | Bills while idle |
|---|---|---|
| P2 Static Web App | `--sku Free` (`Project2/deploy.sh:159`) | No |
| P2 / P3 Function App | `--consumption-plan-location` | No -- per execution, 1M/month free |
| P3 Cosmos DB | `--capabilities EnableServerless` (`Project3/deploy.sh:167`) | No -- per request unit |
| P3 frontend | `--static-website` on the storage account | No -- no Static Web App is created |
| Storage accounts | `Standard_LRS` | Cents per month |

No App Service Plan, no Cosmos provisioned throughput, no Standard Static Web App SKU anywhere --
those three are the ones that charge while nothing is happening. `az functionapp create` may also
create an Application Insights component; its 5 GB/month free grant covers demo volume and it is
deleted with the resource group.

Conclusion: **there is no cheaper configuration to switch to. The only cost variable is how long the
resources exist.** Do not deploy before you are ready to record. Two changes that look like savings
are not: moving Cosmos to the free tier requires provisioned throughput, which is the mode that bills
hourly, and swapping Cosmos for Table Storage would save a fraction of a cent while rewriting the
data layer and its tests.

## 5. Two sessions, one repo

Commits authored by `Lab Admin <labadmin@lab1-ubuntu.local>` come from the Ubuntu VM; this file comes
from the Windows host. The repo moved under this session twice today, once mid-task.

Consequences already observed:

- `Project2/review/score-review-2026-10-02.md` is **stale**. All three blockers it reports were fixed
  by the VM session: the broken `sed` is gone (replaced by an `__FUNCTION_API_URL__` placeholder
  substituted at build time), the silent demo fallback is now an explicit `setOfflineBanner()`, and
  every fabricated `DEMO_DATA` value was replaced with the real Project 1 results (verified against
  `Project1/docs/results/` -- all now match). Anyone reading that doc may go fix what is already
  fixed.
- What remains open for Phase 2 is unchanged and unrelated to code: no real deployment, no evidence,
  and `Project2-Master-Overview.html` still marks all six rubric categories "Done" while describing a
  system that does not exist (v1 function model, an `/api/clusters` endpoint, server-side pagination,
  Azure CI/CD, scoped CORS).

Practice: one session owns the repo at a time, and `git pull` before starting.

## Agreed plan

Deploy from the Ubuntu VM, not the host -- both `deploy.sh` and `teardown.sh` are bash, and Git Bash
on Windows mangles arguments that look like absolute paths, which Azure resource IDs do. One
deployment, one set of resources, deleted the same day. The host keeps its Azure CLI for read-only
verification, Azurite local dev, and screen recording.
