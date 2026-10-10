#!/usr/bin/env bash
set -u
export AZURE_CONFIG_DIR=/tmp/lab3-azure-config
printf '\033c'
echo 'CPSY 300 Lab 03 — Azure Cache for Redis CLI verification'
date -u
echo
echo '$ az redis show ...'
az redis show -g dealerops-student-demo -n cpsy300-redis \
  --query '{name:name,provisioningState:provisioningState,hostName:hostName,sslPort:sslPort,nonSslEnabled:enableNonSslPort,sku:sku.name}' -o json
echo
echo '$ curl public VM health endpoint'
curl --connect-timeout 10 --max-time 20 -sS http://20.84.66.238:5000/
echo
echo 'Note: this output proves Redis provisioning. Cache-hit evidence requires the VM container to be configured with REDIS_* variables.'
read -r -p 'Verified live with Azure CLI. Press Enter to close.'
