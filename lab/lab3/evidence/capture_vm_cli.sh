#!/usr/bin/env bash
set -u
export AZURE_CONFIG_DIR=/tmp/lab3-azure-config
printf '\033c'
echo 'CPSY 300 Lab 03 — Azure VM CLI verification'
date -u
echo
echo '$ az vm show -d ...'
az vm show -d -g dealerops-student-demo -n cpsy300-lab03-vm2 \
  --query '{name:name,powerState:powerState,publicIps:publicIps,location:location}' -o json
echo
echo '$ curl http://20.84.66.238:5000/'
curl --connect-timeout 10 --max-time 20 -sS http://20.84.66.238:5000/
echo
read -r -p 'Verified live with Azure CLI and public API. Press Enter to close.'
