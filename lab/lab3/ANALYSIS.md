# CPSY 300 Lab 03 Analysis

> Inputs analysed: `CPSY_300_Lab03-Performance-Testing-and-Optimization-Updated.docx`, `Uber-Jan-Feb-FOIL.csv`, and the existing `app.py`, `Dockerfile`, `requirements.txt`, `docker-compose.yml` and `jmeter_test_plan.jmx` in this folder.
> Analysis date: 2026-10-09

---

## 1. Summary

1. **The grade depends entirely on screenshot evidence.** There are 11 subtasks worth 5 marks each, 55 marks in total. Every subtask has an explicit screenshot list, and **every screenshot must show the date and time**. This is the easiest way to lose marks across the board.
2. **The supplied dataset does not match the handout** (the most important finding). The handout's code assumes trip-level data (a `Date/Time` column, accurate to the minute). The file provided on Brightspace is **aggregated by date and dispatching base**, with the columns `dispatching_base_number,date,active_vehicles,trips`. It has dates only, no time of day.
   - Copying the handout code verbatim raises `KeyError: 'Date/Time'`.
   - After switching to the `date` column, `Hour` is always 0, so "trips by hour", "peak hour" and the "day-of-week × hour heatmap" lose their meaning.
   - Each row is "total trips for one base on one day", so every statistic must be **weighted by the `trips` column**. Counting rows with `.size()` gives wrong conclusions.
3. **The existing code mostly works, but six issues directly affect marks or execution** (see section 4). The three most serious: the Dockerfile uses `python:3.11-slim` while the handout requires Python 3.8 slim; the JMeter CSV config does not skip the header row, which produces bad requests; and the cache key is hashed, so a screenshot cannot show "timestamp used as the key".
4. **This machine is Apple Silicon (`uname -m` prints `arm64`).** Images built on this machine, or in an Ubuntu VM running on it, are arm64 by default. Pushed to an Azure x86 VM they fail with `exec format error`. Build with `docker buildx --platform linux/amd64`.
5. **Task 3.2 (VMSS autoscaling) and Task 5.1 (performance comparison) take the longest and carry the highest risk of failure.**
   - Azure autoscale only fires under sustained load: average CPU must stay above 70% over a 5–10 minute window, followed by a cooldown. The current JMeter plan (500 threads × 5 loops) finishes in under 2 minutes, which is not enough to trigger a scale-out.
   - The dataset has only 354 rows, so each "prediction" is already cheap. Redis, especially Azure Redis over the network with TLS, may give little or even negative response-time benefit. The comparison must be reported honestly, with an explanation.
   - The built-in VM/VMSS metrics in Azure Monitor **do not include response time**. Use JMeter results or Application Insights to cover it.

---

## 2. Marking breakdown (55 marks)

| # | Subtask | Marks | Required screenshot evidence | Implicit requirements / common pitfalls |
|---|---|---|---|---|
| 1 | 1.1 Data preprocessing | 5 | Output of `df.head()`, `df.info()`, `df.describe()` | Show dropna, de-duplication, date conversion, and the four feature columns Hour/Day/DayOfWeek/IsWeekend; edit `app.py` with nano in the Ubuntu VM |
| 2 | 1.2 Traffic analysis | 5 | Daily and hourly aggregates; busiest day and peak hours; daily and hourly bar charts; heatmap | Must use `.idxmax()`; heatmap title "Trip Frequency by Day and Hour" |
| 3 | 1.3 JMeter | 5 | ① Test plan layout (Thread Group, CSV Data Set Config, HTTP Request, two listeners); ② Summary Report or View Results Tree after the run | 500–1000 threads; timestamps from the CSV as the parameter; path `/predict_traffic?timestamp=${timestamp}`; the summary must show average response time, Error % and throughput |
| 4 | 2.1 Dockerfile | 5 | Dockerfile and requirements.txt open in an editor | **Base image Python 3.8 slim**; requirements must list "all necessary packages" |
| 5 | 2.2 Build and run | 5 | ① `docker build` log; ② server live after `docker run`; ③ successful response from curl, a browser or Postman | Commands are `docker build -t uber-app .` and `docker run -p 5000:5000 uber-app` |
| 6 | 3.1 Azure VM | 5 | ① VM terminal showing Docker running the container; ② successful API call via the **public IP** | NSG allows port 5000; image pulled from Docker Hub |
| 7 | 3.2 VMSS | 5 | ① Autoscale rules in the Portal; ② instance count increasing or decreasing live | Rules: scale out at CPU > 70%, scale in at < 30%; startup script runs the container; Load Balancer in front; load generated with JMeter |
| 8 | 4.1 Local Redis | 5 | ① Cache keys listed by redis-cli; ② a response containing `"source": "cache"` | **Timestamp as the key**; 1-hour TTL; call twice with the same timestamp |
| 9 | 4.2 Azure Redis | 5 | ① Azure Redis resource overview (name and status); ② API on the VM returning `"source": "cache"` | Basic C0; same resource group and region as the VM; SSL on 6380; code matches the handout's `redis.Redis(host, port, password, ssl=True)` form |
| 10 | 5.1 Performance comparison | 5 | Azure Monitor charts for response time, CPU and autoscale actions, **labelled before/after caching** | Use the time filter to isolate the two periods; the expected conclusion is "better after caching" — if measurements disagree, explain why |
| 11 | 5.2 Cleanup | 5 | ① Local terminal evidence of cleanup (Docker and Redis); ② Portal showing resources deleted or deallocating | Delete the VM, VMSS and Azure Redis; locally stop and remove containers and run FLUSHALL |

**Submission (one zip):** report PDF (screenshots with date and time), `Dockerfile`, `app.py`, `requirements.txt`, `jmeter_test_plan.jmx`, and any Redis scripts.

**Marks that apply everywhere**
- Keep the system clock visible in every screenshot, or run `date` in the terminal first.
- Give every screenshot in the report a caption naming the subtask and requirement it covers, so the marker can tick items off one by one.
- The handout expects parts 1.x and 2.x to be done in an **Ubuntu VM** (nano, JMeter GUI, Docker); the screenshots should make the Ubuntu environment visible.

---

## 3. Dataset analysis (measured)

| Item | Result |
|---|---|
| Rows | 354 (no missing values, no duplicates, so still 354 after dropna and de-duplication) |
| Columns | `dispatching_base_number`, `date` (format `M/D/YYYY`), `active_vehicles`, `trips` |
| Date range | 2015-01-01 to 2015-02-28, 59 days |
| Bases | 6 |
| Total trips (weighted by trips) | **4,130,230** |
| Busiest day | **2015-02-20 (Friday), 100,915**; then 02-14 (Valentine's Day, Saturday) 100,345 and 02-21 (Saturday) 98,380 |
| Quietest day | **2015-01-27, 25,244** (matches the 26–27 January 2015 New York blizzard and travel ban; can be explained as an outlier) |
| Largest base | B02764, 1,914,449 (about 46%) |
| Mean daily trips by weekday | Sat 83,481 > Fri 79,021 > Thu 73,961 > Wed 66,408 > Sun 65,493 > Tue 60,383 > Mon 57,975 |
| Weekend effect | Saturday is highest; Sunday sits mid-week — a Friday/Saturday night-out pattern |
| Hour dimension | **Not available**: no time of day, `Hour` is always 0 |

**How the report handles this (honestly, without inventing hourly data)**
- Generate `Hour` and the other features as the handout instructs, and state in the report that the dataset is aggregated by day, so Hour is always 0 and a "peak hour" cannot be derived from it.
- The handout's heatmap has a single column (Hour = 0); screenshot it anyway, and add an **informative** alternative heatmap: weekday × base (or weekday × week number), weighted by trips. This meets the "heatmap" requirement and shows an understanding of the data.
- "Busiest day" uses `groupby('Day')['trips'].sum().idxmax()`; "peak hours" uses the same method and yields hour 0, with a note. Also report the "peak weekday" (Saturday) as a meaningful substitute.

---

## 4. Review of the existing code

| # | File | Problem | Impact | Recommendation |
|---|---|---|---|---|
| 1 | `Dockerfile` | Base image is `python:3.11-slim`; the handout requires **Python 3.8 slim** | Does not meet the 2.1 marking point; may lose marks | Switch to `python:3.8-slim` and pin dependencies compatible with 3.8 (pandas 2.2.2 needs Python ≥ 3.9, so use pandas 2.0.3) |
| 2 | `requirements.txt` | Missing `matplotlib` and `seaborn` (needed for the 1.2 plots) | The handout asks for "all necessary packages"; the marker may compare against the imports in `app.py` | Add both, pinned to 3.8-compatible versions |
| 3 | `jmeter_test_plan.jmx` | CSV Data Set sets `variableNames` but not `ignoreFirstLine=true` | The header row is read as data and sends `timestamp=date`, which returns 400, so Error % in the summary is not 0 | Add `ignoreFirstLine=true` |
| 4 | `jmeter_test_plan.jmx` | 500 threads × 5 loops = 2,500 requests, finished in about a minute | Fine for 1.3, but not enough to trigger VMSS scale-out (3.2) or produce comparable Monitor curves (5.1) | Create a "sustained load" variant: enable the Scheduler, Duration 15–20 minutes, infinite loops, server parameterised as `${__P(host,localhost)}` |
| 5 | `app.py` | Cache key is `uber:prediction:<sha256>` | The handout requires "the request timestamp as the key"; the redis-cli screenshot will not show the timestamp | Use a readable key such as `predict:<timestamp>` |
| 6 | `app.py` | Redis is configured only through `REDIS_URL`; no connection timeout; no fallback when `get`/`setex` fails | The handout's 4.2 uses the host/port/password/ssl form and the marker will compare; if Azure Redis is unreachable, requests may hang or return 500, and it is hard to notice that caching is not working | Use `REDIS_HOST/PORT/PASSWORD/SSL` environment variables to build `redis.Redis(...)` as in the handout; set `socket_connect_timeout`/`socket_timeout`; fall back to direct computation on errors; show `cache: enabled/disabled` in the response or health check |
| 7 | `app.py` | `predict()` matches on Hour, which is always 0: an hour-0 timestamp returns the mean of all rows, any other hour goes to the fallback, and the result is identical either way | The prediction barely depends on the input, which is unconvincing in the report | Use "historical mean daily trips for the same weekday (or same day) and base", so different timestamps give different results |
| 8 | `app.py` | The 1.2 plotting code (`plt.show()`) is not in `app.py`; the handout says "Add into your app.py" | The submitted `app.py` does not match the screenshots | Add `run_analysis()`, triggered by `python app.py --analyze`, saving the plots as PNG (and showing them when a GUI is available); skip plotting in Flask server mode |
| 9 | `docker-compose.yml` | Fine as is; it solves the "localhost inside a container is not the host's Redis" problem | The handout's 4.1 uses `docker run -d -p 6379:6379 redis`. If the app also runs in a container and connects to `localhost`, it cannot reach Redis, `get_redis()` silently returns None, and `source: cache` never appears | For 4.1, use compose, or put the app and Redis on the same `docker network`; or run `python3 app.py` directly in the VM |

The statistics in `report.html` (4,130,230; 02-20 / 100,915; B02764 / 1,914,449) match these measurements and can be kept. However, it contains no real screenshots yet and must still be exported to PDF.

---

## 5. Risks and notes

| Risk | Details | Mitigation |
|---|---|---|
| CPU architecture mismatch | This machine is arm64; common Azure B-series VMs are x86_64 | Use `docker buildx build --platform linux/amd64 -t <user>/uber-app:latest --push .`; on the VM, confirm with `docker image inspect` that Architecture is amd64 |
| VMSS scale-out is hard to trigger | Autoscale uses average CPU with a default 10-minute window plus cooldown, so one scale cycle takes about 15–25 minutes; a single-core B1s with two gunicorn workers and very light requests may never reach 70% CPU | Use a small instance size (e.g. B1s); run high-concurrency JMeter load for 15+ minutes; set the rule window to 5 minutes; if needed, add an optional `?work=N` parameter to `/predict_traffic` for controlled CPU load during load testing only, and state this in the report |
| Sandbox limits | Azure sandbox or student subscriptions often restrict regions, VM sizes and vCPU quota, and the resource group may be pre-created | Check available regions and quota in the Portal first; set the VMSS maximum to 2–3 instances |
| Whether Azure Cache for Redis can be created | Microsoft has announced the migration from Azure Cache for Redis to Azure Managed Redis, so new Basic C0 instances may be restricted on some subscriptions (**confirm in the Portal**); even when allowed, deployment takes 15–20 minutes; new instances may have access-key authentication disabled by default | Create it early; if Basic C0 cannot be created, screenshot the error, use the smallest Azure Managed Redis tier instead and explain in the report; make sure access keys are enabled |
| Azure Redis connection | Port 6380 requires `ssl=True`; 6379 is disabled by default | Inject connection parameters through environment variables; never put the primary key in committed code |
| Small caching benefit | The data is tiny and computation is cheap; remote Redis adds a network round trip per request | Compare honestly in 5.1, focusing on CPU and the number of scale actions; compare response times using two JMeter summaries, before and after |
| Source of the response-time metric | None of the built-in VM/VMSS/Load Balancer metrics include HTTP latency | Option A: compare JMeter summaries before and after, plus Azure Monitor CPU charts; Option B: add Application Insights (OpenTelemetry) to get server response time directly in Azure Monitor |
| Credential leaks | Redis primary key, Docker Hub credentials | Keep them only in environment variables or a `.env` file on the VM (permissions 600); never commit them or show them in screenshots; hide the Access keys page before capturing |
| Screenshots without a time | Their authenticity may be questioned across the board | Include the system clock, or `date` output in the terminal, in every screenshot |

---

## 6. Recommended order and time estimates

1. Locally: fix the code (Python 3.8 image, cache key, Redis config, JMeter) → 1.1 / 1.2 / 1.3 / 2.1 / 2.2 / 4.1 (about 2–3 hours)
2. Build the amd64 image and push it to Docker Hub (about 15 minutes)
3. Azure: create Azure Redis as early as possible (it deploys in the background) while creating the VM → 3.1 → 4.2 (about 1 hour)
4. **First** run a sustained load test with Redis disabled and record the "before caching" window; **then** enable Redis and run the same test to record the "after caching" window (this covers both 3.2 and 5.1, about 1.5–2 hours)
5. 5.2 cleanup, finish the report, export to PDF and zip it (about 1 hour)

> Note: the handout's order is 3.2 → 4.x → 5.1, but 5.1 needs "before caching" data. Record the cache-free window and JMeter results during the 3.2 load test; otherwise you will have to disable caching and test again later.
