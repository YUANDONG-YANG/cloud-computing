#!/usr/bin/env bash
###############################################################################
# Project 2 (Phase 2) — Delete every Azure resource this project created.
#
# Run this as soon as the Phase 2 evidence is captured. Azure bills by the hour
# and by the request, so a resource group left running over a weekend costs
# more than the whole demo did. Everything deploy.sh creates lives in one
# resource group, so one delete is enough.
#
# Phase 2 and Phase 3 use DIFFERENT resource groups:
#     Phase 2   cpsy300-nutritional-insights-rg   (this script)
#     Phase 3   cpsy300-project3-rg               (Project3/teardown.sh)
# Running only one of the two leaves the other group billing. After both demos
# are recorded, confirm with:
#     az group list --query "[].name" -o tsv
# Neither name should appear.
#
# This is irreversible: the uploaded dataset, the Function App settings and the
# Static Web App all go with it. Re-running deploy.sh rebuilds the resources,
# but the Static Web App gets a NEW hostname, so any URL already written into
# a report or a slide stops working.
#
# Usage:
#   chmod +x teardown.sh
#   ./teardown.sh
###############################################################################

set -euo pipefail

# Must match whatever deploy.sh used, including an override. If you deployed
# with RESOURCE_GROUP=something ./deploy.sh then you must pass the same value
# here, otherwise this script looks at the default name, finds nothing, and
# reports success while the real resources keep billing.
RESOURCE_GROUP="${RESOURCE_GROUP:-cpsy300-nutritional-insights-rg}"

command -v az >/dev/null 2>&1 || {
  echo "ERROR: the Azure CLI (az) is not installed or not on PATH." >&2
  echo "       Delete the resource group from the portal instead -- until it is" >&2
  echo "       gone, the resources keep billing." >&2
  exit 1
}

# Check the login separately from the group's existence. Piping `az group
# exists` into `grep -q true` conflates them: when the CLI is not logged in the
# pipeline fails, which reads as "the group is not there" and this script would
# cheerfully report nothing to delete while the resources carried on billing.
az account show --output none 2>/dev/null || {
  echo "ERROR: not logged in to Azure, so whether '$RESOURCE_GROUP' still" >&2
  echo "       exists cannot be determined. Run 'az login' and try again." >&2
  echo "       Do not assume the resources are gone." >&2
  exit 1
}

if [[ "$(az group exists --name "$RESOURCE_GROUP" -o tsv)" != "true" ]]; then
  echo "Resource group '$RESOURCE_GROUP' does not exist. Nothing to delete."
  echo ""
  echo "If you deployed with a RESOURCE_GROUP override, re-run this script with"
  echo "the same value -- the default name is checked above and it is not there."
  echo "To see what resource groups the subscription actually has:"
  echo "    az group list --query \"[].name\" -o tsv"
  exit 0
fi

echo "About to delete the resource group '$RESOURCE_GROUP' and everything in"
echo "it: the Function App, storage account, uploaded dataset and the Static"
echo "Web App."
echo ""
az resource list --resource-group "$RESOURCE_GROUP" \
  --query "[].{name:name, type:type}" -o table 2>/dev/null || true
echo ""
read -r -p "Type the resource group name to confirm: " confirm

if [[ "$confirm" != "$RESOURCE_GROUP" ]]; then
  echo "Names do not match. Nothing was deleted."
  exit 1
fi

echo "Deleting (this runs in the background on Azure and takes a few minutes)."
az group delete --name "$RESOURCE_GROUP" --yes --no-wait

echo ""
echo "Delete requested. Confirm it finished with:"
echo "    az group exists --name $RESOURCE_GROUP"
echo "It should print false. Until then the resources may still bill."
echo ""
echo "Phase 3 lives in a separate resource group. If that demo is also done:"
echo "    cd ../Project3 && ./teardown.sh"
