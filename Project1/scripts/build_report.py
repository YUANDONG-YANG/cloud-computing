"""Build the submission PDF: required screenshots per task, Task 3 explanation, 1-page enhancement report.

Writes docs/reports/Project1-Report.html (images embedded) and prints it to
docs/reports/Project1-Report.pdf with headless Microsoft Edge.

To swap evidence (e.g. new Task 1-2 screenshots), edit SECTIONS below and rerun:
    python scripts/build_report.py
"""
import base64
import html
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "docs/reports"
OUT_HTML = REPORTS / "Project1-Report.html"
OUT_PDF = REPORTS / "Project1-Report.pdf"
ENHANCEMENT = REPORTS / "Enhancement-Report-Cold-Start.html"

TEAM = "Yuandong Yang (000949205), Ethan Bayarsaikhan (000961411), Justin Norman-Rance"

TASK3_EXPLANATION = (
    "Azurite, Microsoft's local Azure Storage emulator, runs as a Docker Compose service and exposes the "
    "Blob service at <code>http://127.0.0.1:10000/devstoreaccount1</code> with the emulator's public "
    "development account, so no real Azure resources are used. <code>upload_dataset.py</code> creates the "
    "<code>datasets</code> container and uploads <code>All_Diets.csv</code> with the Azure Blob Storage SDK "
    "(by script rather than Azure Storage Explorer); the SDK calls are the same as against real Azure, only "
    "the connection string points to Azurite, and <code>storage_config.py</code> refuses any non-local "
    "endpoint. <code>lambda_function.py</code> is the simulated serverless function: when invoked it "
    "downloads the blob with <code>BlobServiceClient</code>, cleans the data, calculates the average "
    "protein, carbs and fat per diet type, and writes one JSON document per diet to "
    "<code>simulated_nosql/results.json</code>, which stands in for a NoSQL database such as Cosmos DB. "
    "The file is replaced atomically, so a failed run never leaves a partial result. Azurite has no event "
    "triggers, so the function is invoked manually after each upload "
    "(<code>docker compose run function</code>), the local equivalent of a blob-triggered Azure Function."
)

# owner="" until that member's own evidence is in place, so nothing is misattributed.
SECTIONS = [
    {
        "title": "Task 1: Dataset Analysis and Insights",
        "owner": "",
        "files": ["data_analysis.py"],
        "shots": [
            ("docs/evidence/task1-analysis.png",
             "Data processing and calculations in Python (Pandas), run in Docker on the Ubuntu VM: average "
             "macronutrients per diet, most common cuisines, highest-protein diet, undefined ratio counts. "
             "Clock: Wed Sep 30 16:53:01."),
            ("docs/results/average_macros.png",
             "Bar chart: average protein, carbs and fat per diet type (generation timestamp bottom right)."),
            ("docs/results/macronutrient_heatmap.png",
             "Heatmap: macronutrient content by diet type (generation timestamp bottom right)."),
            ("docs/results/top5_cuisine_scatter.png",
             "Scatter plot: the top 5 protein-rich recipes per diet type by cuisine (generation timestamp "
             "bottom right)."),
        ],
    },
    {
        "title": "Task 2: Dockerizing the Data Processing Application",
        "owner": "",
        "files": ["Dockerfile"],
        "shots": [
            ("docs/evidence/task2-docker-run.png",
             "Docker container running locally and processing the data: 7,806 recipes processed, averages "
             "and summary printed. Clock: Fri Oct 2 10:08."),
            ("docs/evidence/task2-registry.png",
             "Deployment simulated with Docker Compose (Azurite and registry services up), and the image "
             "pushed to and pulled from a local registry (localhost:5001) with the same digest. "
             "Clock: Wed Sep 30 16:53:04."),
        ],
    },
    {
        "title": "Task 3: Serverless Data Processing with Azurite",
        "owner": "Yuandong Yang",
        "files": ["lambda_function.py"],
        "shots": [
            ("docs/evidence/task3-azurite-live.png",
             "Azurite Blob Storage running (healthy on 127.0.0.1:10000), All_Diets.csv uploaded (702,514 "
             "bytes), function processing it from Azurite and storing 5 diet documents in "
             "simulated_nosql/results.json. Clock: Fri Oct 2 09:59."),
            ("docs/evidence/task3-azurite.png",
             "Upload and function logs with the results saved in the simulated NoSQL store (the five JSON "
             "documents shown). Clock: Wed Sep 30 16:53:06."),
        ],
        "text": TASK3_EXPLANATION,
    },
    {
        "title": "Task 4: CI/CD Pipeline with GitHub Actions",
        "owner": "Ethan Bayarsaikhan",
        "files": [".github/workflows/deploy.yml"],
        "shots": [
            ("docs/evidence/cicd-v2-run-53.png",
             "Successful GitHub Actions run #53: lint and unit tests (Python 3.11 and 3.12) in parallel, "
             "then Docker build, integration test with Azurite, publish to GitHub Container Registry and "
             "simulated deploy, all green. Taskbar: 2026-10-03 10:20 PM."),
            ("docs/evidence/cicd-v2-deploy.png",
             "Evidence of simulated deployment (run #54 on main, after the merge): the deploy job pulled the "
             "published image from ghcr.io and ran it; the running container's output shows the averages "
             "per diet, the most common cuisines and the summary (container clock 2026-10-04 04:49:55 UTC). "
             "Taskbar: 2026-10-05 2:35 PM."),
            ("docs/evidence/cicd-v2-pr-2-merged.png",
             "Pipeline merged to main with 15 checks passed; GitHub records the deployment to the "
             "simulated-local environment. Taskbar: 2026-10-03 10:56 PM."),
        ],
    },
]

TASK5_SHOTS = [
    ("docs/evidence/task5-benchmark-before.png",
     "Cold start benchmark run #2 (before the warm path): baseline and slim image measurements. "
     "Taskbar: 2026-10-04 6:54 PM."),
    ("docs/evidence/task5-benchmark-after.png",
     "Cold start benchmark run #3 (after the warm path): baseline and slim image measurements. "
     "Taskbar: 2026-10-04 6:55 PM."),
]

CSS = """
@page { size: Letter; margin: 0.55in 0.6in }
body { font: 10.5pt/1.4 Arial, sans-serif; color: #17324d; margin: 0 }
h1 { font-size: 17pt; color: #0f766e; margin: 0 0 4px }
h2 { font-size: 13pt; color: #0f766e; margin: 0 0 4px; border-bottom: 2px solid #0f766e }
.task { break-before: page }
.meta { color: #4b6075; margin: 2px 0 8px }
table.map { border-collapse: collapse; width: 100%; margin: 8px 0 }
table.map th, table.map td { border: 1px solid #aab; padding: 4px 8px; text-align: left }
table.map th { background: #eef6f5 }
figure { margin: 8px 0 12px; break-inside: avoid }
figure img { display: block; max-width: 100%; max-height: 3.4in; border: 1px solid #aab }
figcaption { font-size: 9pt; color: #4b6075; margin-top: 3px }
.pending { border: 2px dashed #d97706; background: #fff7e6; padding: 18px; font-weight: bold }
.explain { background: #f3f8ff; border-left: 4px solid #2563eb; padding: 6px 10px; margin: 8px 0 }
code { font-size: 9pt; background: #eef; padding: 0 3px }
.enh { break-before: page; break-after: page; font-size: 9.8pt; line-height: 1.32 }
.enh h1 { font-size: 15pt; margin: 0 0 2px }
.enh h2 { font-size: 11pt; margin: 7px 0 2px; border: 0 }
.enh p, .enh ul { margin: 3px 0 }
.enh ul { padding-left: 18px }
.enh li { margin: 1px 0 }
.enh .sub { color: #4b6075; font-size: 9.5pt; margin-bottom: 6px }
.enh table { border-collapse: collapse; width: 100%; margin: 3px 0; font-size: 9pt }
.enh th, .enh td { border: 1px solid #aab; padding: 2px 6px; text-align: left }
.enh th { background: #eef6f5 }
.enh td.num { text-align: right }
.enh .refs { font-size: 8.5pt; color: #4b6075 }
"""

missing = []


def figure(rel_path, caption):
    path = ROOT / rel_path
    if not path.exists():
        missing.append(rel_path)
        return (f'<figure><div class="pending">Screenshot pending: {html.escape(rel_path)}</div>'
                f"<figcaption>{html.escape(caption)}</figcaption></figure>")
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return (f'<figure><img src="data:image/png;base64,{data}" alt="{html.escape(path.stem)}">'
            f"<figcaption>{html.escape(caption)}</figcaption></figure>")


def section(spec):
    owner = f" · Prepared by {html.escape(spec['owner'])}" if spec["owner"] else ""
    files = ", ".join(f"<code>{html.escape(f)}</code>" for f in spec["files"])
    parts = [f'<section class="task"><h2>{html.escape(spec["title"])}</h2>',
             f'<p class="meta">Deliverable submitted in the zip: {files}{owner}</p>']
    if spec.get("text"):
        parts.append(f'<div class="explain"><b>How cloud storage and serverless processing were '
                     f'simulated.</b> {spec["text"]}</div>')
    parts += [figure(path, caption) for path, caption in spec["shots"]]
    parts.append("</section>")
    return "\n".join(parts)


def enhancement_page():
    body = re.search(r"<body>(.*)</body>", ENHANCEMENT.read_text(encoding="utf-8"), re.S).group(1)
    return f'<section class="enh">{body}</section>'


def build():
    generated = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    rows = "".join(
        f"<tr><td>{html.escape(s['title'].split(':')[0])}</td>"
        f"<td>{', '.join(html.escape(f) for f in s['files'])}</td></tr>" for s in SECTIONS)
    rows += "<tr><td>Task 5</td><td>1-page enhancement report (in this PDF)</td></tr>"
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>CPSY 300 Project 1 Report</title>
<style>{CSS}</style></head><body>
<h1>CPSY 300 Project 1: Cloud-Native Nutritional Insights</h1>
<p class="meta">Team: {TEAM}<br>Report generated: {generated}</p>
<table class="map"><tr><th>Task</th><th>Deliverable file</th></tr>{rows}</table>
<p>Each section below contains the screenshots the assignment requires for that task; every caption gives
the date and time visible in the screenshot.</p>
{"".join(section(s) for s in SECTIONS)}
<section class="task"><h2>Task 5: Enhancement Report</h2>
<p class="meta">Deliverable: the 1-page report on the next page · Prepared by Ethan Bayarsaikhan</p>
<p>The screenshots below are the benchmark runs that produced the report's numbers.</p>
{"".join(figure(p, c) for p, c in TASK5_SHOTS)}</section>
{enhancement_page()}
</body></html>"""
    OUT_HTML.write_text(page, encoding="utf-8")
    print(f"Wrote {OUT_HTML.relative_to(ROOT)}")
    for rel_path in missing:
        print(f"WARNING: screenshot missing, shown as pending: {rel_path}")


def print_pdf():
    candidates = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                  r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                  shutil.which("msedge") or "", shutil.which("microsoft-edge") or ""]
    edge = next((c for c in candidates if c and Path(c).exists()), None)
    if not edge:
        print("Edge not found: open the HTML in a browser and print it to PDF.")
        return
    subprocess.run([edge, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={OUT_PDF}", str(OUT_HTML)], check=True, capture_output=True)
    print(f"Wrote {OUT_PDF.relative_to(ROOT)}")


if __name__ == "__main__":
    build()
    print_pdf()
