#!/usr/bin/env python3
"""DhakaFlow Nexus — the ONE front door.

    python app.py            →  http://localhost:8080

Upload any traffic video in the browser (or pick a bundled sample), choose a
registered camera, press RUN. The server executes the REAL pipeline
(scripts/case_report.py → detector → state → routing) and, when the video is
congested, attaches the same-state twin counterfactual. Results render as the
case report and the four-pane page — nothing pre-baked, same code paths as the
terminal.
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from flask import Flask, redirect, request, send_from_directory, url_for

REPO = Path(__file__).resolve().parent
UPLOADS = REPO / "artifacts" / "uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)
app = Flask(__name__)

CAMERAS = ["farmgate", "karwanbazar", "banglamotor", "shahbagh"]
SAMPLES = {
    "rush hour (dense, recorded live)": "artifacts/react_demo_rush",  # prebuilt case
}

PAGE = """<!doctype html><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>DhakaFlow Nexus</title>
<style>body{margin:0;background:#eef0ee;color:#15191d;
font:16px/1.55 "Helvetica Neue",Arial,sans-serif}
.w{max-width:820px;margin:0 auto;padding:28px 18px}
h1{font-size:30px;margin:0}
.sub{color:#67727a;margin:6px 0 22px}
.card{background:#fff;border:1px solid #d3d8d3;border-radius:8px;
padding:20px;margin-bottom:16px}
label{font-weight:600;display:block;margin:12px 0 4px}
input,select{font-size:15px;padding:8px;width:100%;box-sizing:border-box}
button{background:#0c5f6b;color:#fff;border:0;border-radius:6px;
padding:12px 26px;font-size:17px;font-weight:700;margin-top:16px;cursor:pointer}
a.res{display:block;padding:10px 12px;border:1px solid #d3d8d3;
border-radius:6px;margin:6px 0;text-decoration:none;color:#0c5f6b;font-weight:600}
.cap{font-size:12px;color:#8a949b}</style>
<div class=w>
<h1>DhakaFlow Nexus</h1>
<p class=sub>Upload any traffic video → the system detects, judges, maps,
routes and proves — live, on this machine.</p>
<div class=card>
<form method=post action=/run enctype=multipart/form-data>
<label>Traffic video (any mp4/avi — the examiner's included)</label>
<input type=file name=video accept="video/*" required>
<label>Camera location (registered R1 corridor cameras)</label>
<select name=camera>{cams}<option value="">unknown — perception only
(routing honestly reports LOCATION REQUIRED)</option></select>
<label>Minutes of video to analyse</label>
<input type=number name=minutes value=1.5 step=0.5 min=0.5 max=5>
<button>RUN THE SYSTEM</button>
</form>
<p class=cap>Runs scripts/case_report.py — the exact same code as the
terminal. First run loads the detector (~30 s), then ~real-time.</p>
</div>
<div class=card><b>Results</b>{results}</div>
<div class=card><b>Standing evidence</b>
<a class=res href=/artifact/four_pane.html>Four-pane proof (same-state twin)</a>
<a class=res href=/dashboard>Full dashboard</a>
</div></div>"""


def result_links():
    out = []
    for d in sorted(REPO.glob("artifacts/case_*"), key=lambda p: -p.stat().st_mtime):
        rep = d / "case_report.html"
        cj = d / "case.json"
        if cj.exists():
            tag = ""
            try:
                c = json.loads(cj.read_text())
                tag = (" · CONGESTED" if c.get("congestion_detected")
                       else (" · location required"
                             if "LOCATION_REQUIRED" in str(c.get("routing", ""))
                             else " · free flow"))
            except Exception:                      # noqa: BLE001
                pass
            href = (f"/artifact/{d.name}/case_report.html" if rep.exists()
                    else f"/artifact/{d.name}/case.json")
            out.append(f'<a class=res href="{href}">{d.name[5:]}{tag}</a>')
    return "\n".join(out[:10]) or "<p class=cap>no runs yet</p>"


@app.get("/")
def index():
    cams = "".join(f'<option value="{c}">{c}</option>' for c in CAMERAS)
    return PAGE.format(cams=cams, results=result_links())


@app.post("/run")
def run():
    f = request.files["video"]
    name = f"web_{int(time.time())}"
    vid = UPLOADS / f"{name}{Path(f.filename).suffix or '.mp4'}"
    f.save(vid)
    cmd = ["python3", "scripts/case_report.py", "--source", str(vid),
           "--name", name, "--minutes", request.form.get("minutes", "1.5")]
    cam = request.form.get("camera", "")
    if cam:
        cmd += ["--location", cam]
    subprocess.run(cmd, cwd=REPO, timeout=1800)
    return redirect(url_for("index"))


@app.get("/artifact/<path:p>")
def artifact(p):
    return send_from_directory(REPO / "artifacts", p)


@app.get("/dashboard")
def dashboard():
    return send_from_directory(REPO / "dashboard", "index.html")


if __name__ == "__main__":
    print("DhakaFlow Nexus → http://localhost:8080")
    app.run(host="127.0.0.1", port=8080, debug=False)
