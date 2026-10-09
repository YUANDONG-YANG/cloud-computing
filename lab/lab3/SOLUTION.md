# CPSY 300 Lab 03 Solution Plan

> Companion document: `ANALYSIS.md` (marking points, dataset issues, code review, risks).
> Principles: every step maps to a graded screenshot; every screenshot shows the date and time; never invent information the dataset does not contain.

---

## 0. Preparation

### 0.1 Code fixes (change the code before running experiments)

| File | Change |
|---|---|
| `Dockerfile` | Base image changed to `python:3.8-slim` |
| `requirements.txt` | Pinned Python 3.8-compatible versions, plus the plotting packages |
| `app.py` | ① Readable cache key `predict:<timestamp>`; ② Redis built in the handout's host/port/password/ssl form, with timeouts and a fallback to direct computation on errors; ③ prediction changed to "historical mean daily trips for the same weekday"; ④ `--analyze` mode added (1.1 and 1.2 output and plots) |
| `jmeter_test_plan.jmx` | Add `ignoreFirstLine=true`; parameterise host/port; create a separate sustained-load plan |

### 0.2 `requirements.txt` (Python 3.8 compatible)

```text
Flask==3.0.3
pandas==2.0.3
numpy==1.24.4
redis==5.0.7
gunicorn==22.0.0
matplotlib==3.7.5
seaborn==0.13.2
```

### 0.3 `Dockerfile`

```dockerfile
FROM python:3.8-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MPLBACKEND=Agg
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py Uber-Jan-Feb-FOIL.csv ./
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "app:app"]
```

### 0.4 Key structure of `app.py`

```python
from flask import Flask, jsonify, request
import pandas as pd
import json, os, sys

app = Flask(__name__)

# ---------- Subtask 1.1 Preprocessing ----------
df = pd.read_csv("Uber-Jan-Feb-FOIL.csv")
df.dropna(inplace=True)
df.drop_duplicates(inplace=True)
# The handout's column is 'Date/Time'; the supplied dataset is aggregated by day and uses 'date'
DATE_COL = "Date/Time" if "Date/Time" in df.columns else "date"
df[DATE_COL] = pd.to_datetime(df[DATE_COL])
df["Hour"] = df[DATE_COL].dt.hour
df["Day"] = df[DATE_COL].dt.date
df["DayOfWeek"] = df[DATE_COL].dt.day_name()
df["IsWeekend"] = df["DayOfWeek"].isin(["Saturday", "Sunday"])
# Each aggregated row represents many trips, so weight by trips; trip-level rows count as 1
df["Trips"] = df["trips"] if "trips" in df.columns else 1

# ---------- Redis (Subtask 4.1 / 4.2) ----------
redis_client = None
def get_redis():
    global redis_client
    if redis_client is None and os.getenv("REDIS_HOST"):
        import redis
        try:
            client = redis.Redis(
                host=os.getenv("REDIS_HOST"),                  # local: localhost / redis
                port=int(os.getenv("REDIS_PORT", "6379")),    # Azure: 6380
                password=os.getenv("REDIS_PASSWORD") or None, # Azure: primary key
                ssl=os.getenv("REDIS_SSL", "false").lower() == "true",
                decode_responses=True,
                socket_connect_timeout=2, socket_timeout=2,
            )
            client.ping()
            redis_client = client
        except Exception as exc:
            app.logger.warning("Redis unavailable: %s", exc)
    return redis_client

# Precompute mean daily trips per weekday (sum per day first, then average)
daily_totals = df.groupby("Day")["Trips"].sum()
dow_avg = daily_totals.groupby(pd.to_datetime(daily_totals.index).day_name()).mean()

def predict(ts):
    parsed = pd.to_datetime(ts)
    dow = parsed.day_name()
    actual = daily_totals.get(parsed.date())
    return {
        "timestamp": parsed.isoformat(),
        "day_of_week": dow,
        "predicted_trips": round(float(dow_avg[dow]), 2),
        "actual_trips": int(actual) if actual is not None else None,
        "model": "historical mean daily trips for same day-of-week",
    }

@app.get("/")
def health():
    return jsonify({"status": "ok", "rows": len(df), "cache": "enabled" if get_redis() else "disabled"})

@app.get("/predict_traffic")
def predict_traffic():
    ts = request.args.get("timestamp")
    if not ts:
        return jsonify({"error": "timestamp is required"}), 400
    key = f"predict:{ts}"                      # handout requirement: timestamp as the key
    client = get_redis()
    if client:
        try:
            cached = client.get(key)
            if cached:
                return jsonify({**json.loads(cached), "source": "cache"})
        except Exception as exc:
            app.logger.warning("Redis get failed: %s", exc)
    try:
        result = predict(ts)
    except (ValueError, TypeError):
        return jsonify({"error": "invalid timestamp"}), 400
    if client:
        try:
            client.setex(key, 3600, json.dumps(result))   # expires after 1 hour
        except Exception as exc:
            app.logger.warning("Redis set failed: %s", exc)
    return jsonify({**result, "source": "computed"})

# ---------- Subtask 1.1 / 1.2 Analysis (python app.py --analyze) ----------
def run_analysis():
    import matplotlib.pyplot as plt
    import seaborn as sns
    print(df.head()); df.info(); print(df.describe(include="all"))
    daily_trips = df.groupby("Day")["Trips"].sum()
    hourly_trips = df.groupby("Hour")["Trips"].sum()
    print("Busiest day:", daily_trips.idxmax(), daily_trips.max())
    print("Peak hour:", hourly_trips.idxmax(), "(dataset is daily aggregate, Hour is always 0)")
    # Bar charts by day and by hour; heatmaps: handout version + weekday × base supplement
    ...  # savefig to daily_trips.png / hourly_trips.png / heatmap_*.png; plt.show() when a GUI is available

if __name__ == "__main__":
    if "--analyze" in sys.argv:
        run_analysis()
    else:
        app.run(host="0.0.0.0", port=5000)
```

> The actual implementation makes incremental changes to the existing `app.py` (keeping the `/analysis` endpoint). Only the structure relevant to marking is shown above.

### 0.5 Environment setup
- Ubuntu VM: Python 3.8+ (or a venv), Docker, JMeter (the GUI needs Java 8+; JMeter 5.6.3 recommended).
- Docker Hub account: this machine is arm64, so image builds **must** specify `--platform linux/amd64`.
- Azure: confirm the sandbox's available regions, VM sizes and vCPU quota, and **create Azure Redis as early as possible** (deployment takes 15–20 minutes).

---

## Task 1: Local analysis and traffic simulation (15 marks)

### 1.1 Data preprocessing (5 marks)
```bash
date                       # put the time in the screenshot
nano app.py                # the handout requires nano; capture the editor as supporting evidence
python3 app.py --analyze
```
**Screenshots**
- [ ] `df.head()` output (showing the new Hour/Day/DayOfWeek/IsWeekend columns)
- [ ] `df.info()` output (`date` column as `datetime64`, 354 non-null rows)
- [ ] `df.describe()` output

**Report note:** still 354 rows after dropna and de-duplication (the raw data has no missing or duplicate rows); the supplied dataset is aggregated by day and base, so statistics are weighted by the `trips` column.

### 1.2 Traffic pattern analysis (5 marks)
**Screenshots**
- [ ] Aggregates: `daily_trips` (59 days), `hourly_trips`, and the `idxmax()` result: **busiest day 2015-02-20 (100,915 trips)**
- [ ] Daily bar chart (59 bars)
- [ ] Hourly bar chart (a single bar for Hour = 0; explain why in the report)
- [ ] Handout heatmap "Trip Frequency by Day and Hour"
- [ ] Supplementary weekday × base heatmap (the informative version)

**Key conclusions for the report**
- Saturday has the highest mean daily trips (83,481) and Monday the lowest (57,975); Friday and Saturday are the peaks.
- February is higher overall than January; 01-27 is an outlier low (25,244, blizzard travel ban).
- Base B02764 alone accounts for about 46% of trips.
- Relevance to load testing: use the Friday/Saturday peaks as the basis for the test load.

### 1.3 JMeter load test (5 marks)
Test plan structure:
```
Test Plan: Uber Traffic API Load Test
└─ Thread Group  (Threads=500~1000, Ramp-up=60s, Loop=5)
   ├─ CSV Data Set Config  (Filename=Uber-Jan-Feb-FOIL.csv,
   │                        Variable Names=base,timestamp,active_vehicles,trips,
   │                        Ignore first line=True, Recycle on EOF=True)
   ├─ HTTP Request  (Server=${__P(host,localhost)}, Port=${__P(port,5000)},
   │                 GET /predict_traffic, parameter timestamp=${timestamp}, URL Encode checked)
   ├─ Summary Report
   └─ View Results Tree
```
- `timestamp` maps to the CSV's second column `date`, e.g. `1/1/2015`. It contains slashes, so URL Encode must be checked.
- Confirm the API is up before running: `curl "localhost:5000/predict_traffic?timestamp=1/1/2015"`.
- 500 threads in GUI mode is resource-heavy; set View Results Tree to "Errors only", or disable it after taking the screenshot.

**Screenshots**
- [ ] Test plan tree (all 5 elements expanded, Thread Group selected showing 500 threads)
- [ ] Summary Report (# Samples, Average, Error % = 0.00%, Throughput)

**Save a separate sustained-load plan** (for 3.2 and 5.1): `jmeter_soak_plan.jmx`, with the Scheduler enabled, Duration 1200 seconds, Loop Infinite, 500 threads. Run it in non-GUI mode:
```bash
jmeter -n -t jmeter_soak_plan.jmx -Jhost=<LB-public-IP> -Jport=5000 -l soak_nocache.jtl -e -o report_nocache/
```

---

## Task 2: Dockerization (10 marks)

### 2.1 Dockerfile and dependencies (5 marks)
**Screenshots**
- [ ] `Dockerfile` open in nano or VS Code (showing `FROM python:3.8-slim`)
- [ ] `requirements.txt` open in an editor

### 2.2 Build and run (5 marks)
```bash
docker build -t uber-app .
docker run -p 5000:5000 uber-app
# in another terminal
curl "http://localhost:5000/predict_traffic?timestamp=2/20/2015"
```
**Screenshots**
- [ ] Build log (including `FROM python:3.8-slim` and the final `naming to docker.io/library/uber-app`)
- [ ] gunicorn printing `Listening at: http://0.0.0.0:5000` after run
- [ ] JSON returned by curl, a browser or Postman (`"source": "computed"`)

**Push an amd64 image for Azure** (an Ubuntu VM on Apple Silicon is also arm64):
```bash
docker login
docker buildx create --use                      # first time only
docker buildx build --platform linux/amd64 -t <dockerhub-user>/uber-app:latest --push .
```

---

## Task 3: Azure deployment and autoscaling (10 marks)

### 3.1 Deploy to a single VM (5 marks)
1. Portal → Virtual machines → Create: Ubuntu 22.04/24.04 LTS, size B1s or B2s, SSH public key authentication.
2. Networking → add an NSG inbound rule: TCP 5000, source your own IP or Any (for the lab).
3. Connect and deploy:
```bash
ssh azureuser@<VM-public-IP>
# install Docker following the Lab 1 steps
sudo docker pull <dockerhub-user>/uber-app:latest
sudo docker image inspect <dockerhub-user>/uber-app --format '{{.Architecture}}'   # should be amd64
sudo docker run -d --name uber-app --restart unless-stopped -p 5000:5000 <dockerhub-user>/uber-app:latest
sudo docker ps
```
**Screenshots**
- [ ] VM terminal with `docker ps` showing the running container (run `date` as well)
- [ ] Browser or Postman calling `http://<VM-public-IP>:5000/predict_traffic?timestamp=2/20/2015` successfully (public IP visible in the address bar)

### 3.2 VMSS + load balancer + autoscaling (5 marks)
1. Portal → Virtual machine scale sets → Create
   - Ubuntu image, size B1s (smaller is easier to push to 70%), initial instance count 1.
   - Scaling: choose Autoscaling, minimum 1, maximum 3 (subject to sandbox quota).
   - Networking: create a new **Azure Load Balancer** with a rule from frontend TCP 5000 → backend 5000; HTTP health probe on 5000, path `/`; NSG allows 5000.
   - Advanced → Custom data (cloud-init):
```yaml
#cloud-config
package_update: true
packages: [docker.io]
runcmd:
  - systemctl enable --now docker
  - docker run -d --name uber-app --restart always -p 5000:5000 <dockerhub-user>/uber-app:latest
```
2. Autoscale rules (Scaling → Custom autoscale):
   - Scale out: Percentage CPU, average > 70%, 5-minute window, +1 instance, 5-minute cooldown.
   - Scale in: Percentage CPU, average < 30%, 5-minute window, −1 instance, 5-minute cooldown.
3. Verify: `curl http://<LB-public-IP>:5000/`; then run the sustained-load JMeter plan (**with Redis disabled**, as the "before caching" baseline) and record the start and end times.
4. If CPU never reaches 70%: add threads, or run JMeter from several machines at once; or add a load-test-only `?work=N` parameter to the endpoint for controlled CPU cost, and state this honestly in the report.

**Screenshots**
- [ ] Autoscale rules page (both the >70% and <30% rules visible)
- [ ] Instances page: count rising from 1 to 2 or 3 (during the test); about 10–15 minutes after the test ends, another capture showing it falling back
- [ ] Supporting: Autoscale Run history, or scale events in the Activity log (also usable for 5.1)

---

## Task 4: Redis caching (10 marks)

### 4.1 Local Redis (5 marks)
Recommended setup (app and Redis on the same Docker network):
```bash
docker network create uber-net
docker run -d --name redis --network uber-net -p 6379:6379 redis
docker run -d --name uber-app --network uber-net -p 5000:5000 -e REDIS_HOST=redis uber-app
curl "localhost:5000/predict_traffic?timestamp=2/20/2015"   # "source":"computed"
curl "localhost:5000/predict_traffic?timestamp=2/20/2015"   # "source":"cache"
docker exec -it redis redis-cli KEYS 'predict:*'
docker exec -it redis redis-cli TTL 'predict:2/20/2015'     # about 3600, proving the 1-hour expiry
```
(Alternatively use `docker compose up`, with `REDIS_HOST: redis` in the compose file's environment.)

**Screenshots**
- [ ] redis-cli output: `KEYS` listing `predict:2/20/2015` and others, plus the TTL
- [ ] Both calls in one screenshot: the first `computed`, the second `cache`

### 4.2 Azure Cache for Redis (5 marks)
1. Portal → Azure Cache for Redis → Create: **same resource group and region** as the VM, Basic C0, unique DNS name.
   - If Basic C0 cannot be created on this subscription, screenshot the error, use the smallest Azure Managed Redis tier instead and explain in the report.
2. After deployment, confirm access-key authentication is enabled under Authentication / Access keys, and copy the host name, port 6380 and primary key (**never capture the key itself**).
3. Restart the app on the 3.1 VM:
```bash
cat > ~/redis.env <<'EOF'
REDIS_HOST=<name>.redis.cache.windows.net
REDIS_PORT=6380
REDIS_SSL=true
REDIS_PASSWORD=<primary-key>
EOF
chmod 600 ~/redis.env
sudo docker rm -f uber-app
sudo docker pull <dockerhub-user>/uber-app:latest
sudo docker run -d --name uber-app --restart unless-stopped -p 5000:5000 --env-file ~/redis.env <dockerhub-user>/uber-app:latest
curl http://localhost:5000/                     # "cache":"enabled"
curl "http://<VM-public-IP>:5000/predict_traffic?timestamp=2/14/2015"   # computed
curl "http://<VM-public-IP>:5000/predict_traffic?timestamp=2/14/2015"   # cache
```
4. Apply the same change to the VMSS: update the cloud-init to pass the env file to `docker run`, then Upgrade or Reimage the instances. With caching enabled, run the same sustained-load JMeter plan again as the "after caching" data.

**Screenshots**
- [ ] Azure Redis Overview page (name, status Running, location, tier)
- [ ] Two calls via the VM's public IP, the second returning `"source": "cache"`

---

## Task 5: Monitoring and cleanup (10 marks)

### 5.1 Performance comparison (5 marks)
Data sources and method:

| Metric | Source | Method |
|---|---|---|
| CPU usage | Azure Monitor → VMSS → Metrics → Percentage CPU (average, can split by instance) | Use the time filter to select the "before caching" and "after caching" test windows and capture each; or annotate the boundary on one chart |
| Autoscale actions | Monitor → Autoscale → Run history; "Autoscale scale up/down" events in the Activity log; the Instance count metric | Compare the number of scale-outs in the two windows |
| Response time | Not in the built-in VM metrics. **Option A (recommended, cheapest):** the two JMeter runs (HTML reports `report_nocache/` and `report_cache/`, or the Summary Reports). **Option B:** add Application Insights and view Server response time in Azure Monitor | Place the two screenshots side by side in the report, clearly labelled |

**Screenshots**
- [ ] CPU chart labelled "Before caching / After caching"
- [ ] Autoscale actions (Run history or Instance count chart) labelled before/after
- [ ] Response-time comparison (JMeter or Application Insights) labelled before/after

**How to write the conclusion:** report the real numbers. If the response-time improvement is small, explain why: the dataset has only 354 rows and computation is already cheap, while remote Redis over TLS adds a network round trip per request; the main benefit of caching shows up as lower CPU and fewer scale-outs.

### 5.2 Resource cleanup (5 marks)
```bash
# local
docker exec redis redis-cli FLUSHALL
docker stop uber-app redis && docker rm uber-app redis
docker network rm uber-net
docker ps -a        # confirm it is empty
date
```
Azure: delete the VMSS (with its Load Balancer and public IP), the VM (with its disk, NIC, NSG and public IP), and Azure Redis. If you created the resource group yourself, delete the whole group; in a sandbox-provided group, delete only the lab resources. Confirm with the CLI:
```bash
az resource list -g <resource-group> -o table
```
**Screenshots**
- [ ] Local terminal: FLUSHALL returns OK and `docker ps -a` is empty
- [ ] Portal: resources showing Deleting or Deallocating, or an empty resource group; the delete events in the Activity log also work

---

## 6. Report and submission

**Report structure** (based on `report.html`; insert screenshots, then export to PDF)
1. Cover: name, student ID, date
2. One section per subtask: what was done (1–2 sentences) + screenshots (numbered and captioned, mapped to the marking items) + key findings
3. A "Dataset notes" section: how the aggregated data differs from the handout and how it was handled
4. Performance comparison conclusions
5. Appendix: list of code files

**Zip contents**
```
CPSY300_Lab03_<name>.zip
├─ Lab03_Report.pdf
├─ app.py
├─ Dockerfile
├─ requirements.txt
├─ docker-compose.yml          # Redis integration script
├─ jmeter_test_plan.jmx
├─ jmeter_soak_plan.jmx        # sustained-load plan (optional)
└─ redis.env.example           # placeholders only, no real keys
```

**Pre-submission checklist**
- [ ] All 22+ screenshots show the date and time
- [ ] No Redis primary key or Docker Hub token appears in any screenshot
- [ ] `Dockerfile` uses python:3.8-slim
- [ ] JMeter Error % is 0 and the thread count is between 500 and 1000
- [ ] All Azure resources are deleted
