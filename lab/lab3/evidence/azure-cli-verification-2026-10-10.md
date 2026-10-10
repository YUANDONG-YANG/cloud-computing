# Azure CLI verification transcript

Captured from real, read-only Azure CLI and HTTP checks on **2026-10-10 UTC**. No Azure resource was modified by these checks.

## VM and public API

```json
{
  "location": "eastus",
  "name": "cpsy300-lab03-vm2",
  "powerState": "VM running",
  "privateIps": "172.16.0.4",
  "publicIps": "20.84.66.238"
}
```

`GET http://20.84.66.238:5000/` returned HTTP 200:

```json
{
  "cache": "disabled",
  "rows": 354,
  "service": "uber-traffic-api",
  "status": "ok",
  "served_at_utc": "2026-10-10T00:25:47.233664+00:00",
  "request_url": "http://20.84.66.238:5000/"
}
```

## Redis

```json
{
  "enableNonSslPort": false,
  "hostName": "cpsy300-redis.redis.cache.windows.net",
  "name": "cpsy300-redis",
  "provisioningState": "Succeeded",
  "redisVersion": "6.0",
  "sku": {"capacity": 0, "family": "C", "name": "Basic"},
  "sslPort": 6380
}
```

The VM API returned `"source": "computed"` for a prediction request, consistent with the health endpoint's `"cache": "disabled"`. This proves that the managed Redis resource exists but is **not yet connected to the VM container**.

## VMSS and autoscale

```json
{
  "capacity": 1,
  "location": "canadacentral",
  "name": "cpsy300-vmss3",
  "upgradePolicy": "Automatic"
}
```

The autoscale setting is enabled with these verified rules:

| Metric | Operator | Threshold | Action |
|---|---|---:|---|
| Percentage CPU | GreaterThan | 70 | Increase by 1 |
| Percentage CPU | LessThan | 30 | Decrease by 1 |

The flexible VMSS instance `cpsy300-vmss3_53bff910` reported `VM running` in Canada Central with private IP `10.0.0.4`.

No scale event appeared in the seven-day activity-log query. Therefore this transcript must not be used to claim that load-driven scaling has been demonstrated.

## VM CPU metric

Azure Monitor returned hourly average CPU readings for the standalone VM, including 4.57% at 2026-10-09T16:26:00Z and approximately 0.3% for later idle hours. These are idle observations only, not a before/after Redis performance comparison.
