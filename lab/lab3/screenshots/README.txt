Captured evidence files (all generated from real commands or Azure Portal state):

- analysis-live.png — live Azure application /analysis JSON through an SSH tunnel
- azure-nsg.png — Azure NSG showing Allow-5000, TCP, priority 310
- jmeter-plan.png — validated JMeter plan tree
- jmeter-summary.png — JMeter dashboard: 2,500 samples, 0 errors, 2.04 ms average, 42.15 transactions/s
- verification-evidence.png — combined data preprocessing, Redis cache, JMeter, and Azure evidence

The Azure VM was deployed in East US Zone 2 and the Docker application and Redis container were run successfully. VMSS autoscale, Azure Cache for Redis, Azure Monitor before/after charts, and cleanup screenshots require additional Azure resources or a final cleanup action and are not represented by fabricated images.
