#!/usr/bin/env bash
###############################################################################
# Project 3 (Phase 3) — Delete every Azure resource this project created.
#
# Run this as soon as the demo video is recorded. Azure bills by the hour and
# by the request, so a resource group left running over a weekend costs more
# than the whole demo did. Everything lives in one resource group, so one
# delete is enough.
#
# This is irreversible: the Cosmos data, the registered users and the uploaded
# blobs all go with it. Re-running deploy.sh rebuilds the resources from
# scratch, but not their contents.
#
# Usage:
#   chmod +x teardown.sh
#   ./teardown.sh
###############################################################################

set -euo pipefail

# Must match whatever deploy.sh used, including an override.
RESOURCE_GROUP="${RESOURCE_GROUP:-cpsy300-project3-rg}"

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
  exit 0
fi

echo "About to delete the resource group '$RESOURCE_GROUP' and everything in"
echo "it: the Function App, Cosmos DB account, storage account, uploaded"
echo "dataset and all registered users."
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
