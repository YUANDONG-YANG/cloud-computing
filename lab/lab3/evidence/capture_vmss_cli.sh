#!/usr/bin/env bash
set -u
export AZURE_CONFIG_DIR=/tmp/lab3-azure-config
printf '\033c'
echo 'CPSY 300 Lab 03 — VMSS and autoscale CLI verification'
date -u
echo
echo '$ az vmss show ...'
az vmss show -g dealerops-student-demo -n cpsy300-vmss3 \
  --query '{name:name,location:location,capacity:sku.capacity,upgradePolicy:upgradePolicy.mode}' -o json
echo
echo '$ az monitor autoscale show ...'
az monitor autoscale show -g dealerops-student-demo -n cpsy300-vmss3-autoscale \
  --query '{enabled:enabled,rules:profiles[0].rules[].{metric:metricTrigger.metricName,operator:metricTrigger.operator,threshold:metricTrigger.threshold,direction:scaleAction.direction,change:scaleAction.value}}' -o json
echo
echo '$ az vm show -d ... flexible VMSS instance'
az vm show -d -g dealerops-student-demo -n cpsy300-vmss3_53bff910 \
  --query '{name:name,powerState:powerState,privateIps:privateIps,location:location}' -o json
echo
read -r -p 'Verified live with Azure CLI. Press Enter to close.'
