#!/usr/bin/env python3
"""ONE COMMAND for the examiner's input: video → full story, correct order.

    python scripts/case_report.py --source <video|stream|webcam> \
        [--location "23.7529,90.3944"] [--minutes 1.5]

Pipeline (each step feeds the next, nothing pre-baked):
  1. DETECT+TRACK   Dhaka-fine-tuned RT-DETR on the given video
  2. STATE          congestion verdict per 5-s window (self-calibrating)
  3. MAP            the camera location snaps to its road-graph edge; a
                    CONGESTED verdict raises that edge's cost (5x)
  4. ROUTE          Dijkstra on the real 6,527-edge network: route through
                    the jam vs best diverted route — delay avoided computed
  5. PROVE          the twin's counterfactual statistics attached (the
                    network-scale version of the same decision)

Output: artifacts/case_<name>/case_report.html — a single self-contained page
telling the story for THIS input, plus all raw JSON. If the video shows free
flow, the report says so and shows the no-action route — it never invents a
jam.
"""
from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

# Registered demo cameras on the R1 corridor. An UNREGISTERED video without
# --location gets honest degradation: perception runs, road-level routing is
# marked LOCATION_REQUIRED — never a silently invented location.
REGISTERED_CAMERAS = {
    "farmgate":     (23.7573, 90.3854),
    "karwanbazar":  (23.7529, 90.3944),
    "banglamotor":  (23.7465, 90.3948),
    "shahbagh":     (23.7389, 90.3958),
}
DEFAULT_LOCATION = None
DEST = (23.7389, 90.3958)                 # Shahbagh — representative trip destination
WEIGHTS = REPO / "artifacts/p1_winner/rtdetr_r50_poribohon_best.pth"


def b64(p: Path, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--location", default=None,
                    help='camera lat,lng — e.g. "23.7529,90.3944"')
    ap.add_argument("--minutes", type=float, default=1.5)
    ap.add_argument("--name", default=None)
    args = ap.parse_args()

    name = args.name or Path(str(args.source)).stem or "live"
    out = REPO / "artifacts" / f"case_{name}"
    out.mkdir(parents=True, exist_ok=True)
    cam_name = args.location if args.location in REGISTERED_CAMERAS else None
    if cam_name:
        loc = REGISTERED_CAMERAS[cam_name]
    elif args.location:
        loc = tuple(float(x) for x in args.location.split(","))
    else:
        loc = None   # honest: routing degrades to LOCATION_REQUIRED

    # ---- steps 1-2: detection + state (Dhaka winner) --------------------
    print("[1-2/5] detection + congestion state on the given video …")
    from scripts.demo_react import run_rtdetr
    verdict = run_rtdetr(str(args.source), args.minutes, out, str(WEIGHTS))
    timeline = json.loads((out / "timeline.json").read_text())
    congested = verdict["routing_input"]["congestion_detected"]
    peak = max((w["mean_vehicles"] for w in timeline), default=0)

    # video -> gif for the report
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                    "-i", str(out / "annotated.mp4"),
                    "-vf", "fps=6,scale=440:-1:flags=lanczos",
                    str(out / "annotated.gif")], check=True)

    # ---- step 3: map the camera to its road segment ---------------------
    if loc is None:
        print("[3/5] no registered location — road-level routing SKIPPED")
        (out / "case.json").write_text(json.dumps({
            "input": str(args.source),
            "congestion_detected": congested,
            "peak_vehicles_per_frame": peak,
            "routing": "LOCATION_REQUIRED — register the camera "
                       "(--location farmgate|karwanbazar|banglamotor|shahbagh "
                       "or lat,lng); perception ran fully.",
            "detector": verdict["detector"]}, indent=2))
        print("TRAFFIC PERCEPTION: AVAILABLE · ROAD-LEVEL ROUTING: LOCATION REQUIRED")
        return
    print("[3/5] mapping camera location to road segment …")
    from research.routing.r1_router import R1Router
    router = R1Router()
    cam_edge = router.nearest_edge(*loc)

    # ---- step 4: routing before/after for THIS verdict ------------------
    print("[4/5] routing on the real network …")
    free = router.best_route(loc, DEST)
    if congested:
        # congest the camera edge and its continuation along the naive route
        naive = router._dijkstra(free["src_edge"], free["dst_edge"], {})
        k = naive.index(cam_edge) if cam_edge in naive else 0
        jam = {e: 5.0 for e in naive[k:k + 10]}
    else:
        jam = {}
    routed = router.best_route(loc, DEST, jam)

    # route map rendered fresh for THIS case
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7, 7.5))
    for e in list(router._edges.values())[::2]:
        xs, ys = zip(*e.getShape())
        ax.plot(xs, ys, color="#dcdcdc", lw=0.35, zorder=1)
    naive_p = router._dijkstra(routed["src_edge"], routed["dst_edge"], {})
    info_p = router._dijkstra(routed["src_edge"], routed["dst_edge"], jam)
    for path, col, lab in ((naive_p, "#b3432b",
                            f"through jam: {routed['naive']['experienced_s']:.0f}s"),
                           (info_p, "#2b7a4b",
                            f"best route: {routed['informed']['experienced_s']:.0f}s")):
        for i, eid in enumerate(path):
            xs, ys = zip(*router._edges[eid].getShape())
            ax.plot(xs, ys, color=col, lw=3, zorder=3,
                    label=lab if i == 0 else None)
    for eid in jam:
        xs, ys = zip(*router._edges[eid].getShape())
        ax.plot(xs, ys, color="#7a1500", lw=7, alpha=0.5, zorder=2)
    cx, cy = router.net.convertLonLat2XY(loc[1], loc[0])
    ax.scatter([cx], [cy], s=200, marker="v", c="#111", zorder=5)
    ax.annotate("CAMERA (this video)", (cx, cy), fontsize=10,
                fontweight="bold", xytext=(cx + 100, cy + 120))
    ax.legend(loc="lower left")
    state_word = "CONGESTED — rerouting engaged" if congested else "free flow — no action needed"
    ax.set_title(f"Routing decision for THIS video · {state_word}", fontsize=11)
    ax.set_aspect("equal"); ax.axis("off")
    plt.tight_layout(); plt.savefig(out / "route_map.png", dpi=140)
    plt.close(fig)

    # ---- step 5: PREDICT & PROVE on THIS road from THIS moment ----------
    cf = None
    cf_name = f"case_{name}"
    if congested and cam_name:
        print("[5/6] twin: predicting the next 10 min at this camera and "
              "testing the action from the SAME saved state (takes minutes) …")
        r = subprocess.run([sys.executable, "scripts/same_state_counterfactual.py",
                            "--camera", cam_name, "--name", cf_name,
                            "--seed", "11"], cwd=REPO)
        res_p = REPO / "artifacts" / "same_state" / cf_name / "result.json"
        if r.returncode == 0 and res_p.exists():
            cf = json.loads(res_p.read_text())
            subprocess.run([sys.executable, "scripts/four_pane_report.py",
                            "--case", name, "--counterfactual", cf_name,
                            "--out", str(out / "four_pane.html")], cwd=REPO)
    elif congested:
        print("[5/6] twin skipped — camera not registered")
    else:
        print("[5/6] free flow measured — no action warranted, twin not run "
              "(restraint is a decision; seed-13 experiment)")

    print("[6/6] attaching network-scale context …")
    dd = json.loads((REPO / "artifacts/due_dso_stats/v200/result.json").read_text())
    md = {c["metric"]: c for c in dd["comparisons"]}["mean_delay_s"]

    case = {
        "input": str(args.source), "camera_location": loc,
        "camera_edge": cam_edge, "congestion_detected": congested,
        "peak_vehicles_per_frame": peak,
        "route_through_jam_s": routed["naive"]["experienced_s"],
        "best_route_s": routed["informed"]["experienced_s"],
        "delay_avoided_s_per_vehicle": routed["delay_avoided_s"],
        "same_state_counterfactual": (
            {"t0_s": cf["t0_s"], **cf["four_pane"],
             "four_pane_page": f"artifacts/case_{name}/four_pane.html"}
            if cf else None),
        "network_scale_proof": {
            "mean_delay_reduction_pct": md["dso_improvement_percent"],
            "p_value": md["p_value"], "seeds": 10,
            "source": "artifacts/due_dso_stats/v200/result.json"},
        "detector": verdict["detector"],
    }
    (out / "case.json").write_text(json.dumps(case, indent=2))


    if cf:
        fpn = cf["four_pane"]
        dq = fpn["queue_no_action"] - fpn["queue_control"]
        qpct = 100 * dq / max(fpn["queue_no_action"], 1)
        twin_html = f"""<div class="step"><h2>Step 5 · PREDICT &amp; PROVE — this road, this moment</h2>
<p>The twin reproduced this camera's congestion (t&#8320;={cf['t0_s']:.0f}s), saved the EXACT
simulator state, and ran two futures from it:</p>
<p>PREDICTION if nothing is done: queue reaches
<b class="bad">{fpn['queue_no_action']} vehicles</b> in 10 minutes &middot;
with DhakaFlow's action from the same start:
<b class="good">{fpn['queue_control']} vehicles</b> &rarr;
<span class="big good">queue &minus;{qpct:.0f}%</span>
(network stopped {fpn['network_stopped_no_action']} &rarr; {fpn['network_stopped_control']})</p>
<p><a style="color:#39b3c6" href="four_pane.html"><b>OPEN THE FOUR-PANE PROOF PAGE &rarr;</b></a></p>
<p class="cap">identical pasts, measured difference &middot; artifacts/same_state/{cf_name}/result.json &middot; computed fresh for THIS input</p></div>"""
    elif congested:
        twin_html = ("<div class='step'><h2>Step 5 · PREDICT &amp; PROVE</h2>"
                     "<p>Camera not registered — twin needs a mapped location.</p></div>")
    else:
        twin_html = ("<div class='step'><h2>Step 5 · PREDICT &amp; PROVE</h2>"
                     "<p>This video shows FREE FLOW — the correct action is none. "
                     "The system does not invent interventions (measured: acting on a "
                     "barely-queued junction makes traffic worse — seed-13 experiment).</p></div>")
    corr = REPO / "docs/media/corridor_before_after.mp4"
    html = f"""<title>Traffic Case Report — {name}</title>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@400;600;700&family=IBM+Plex+Sans+Condensed:wght@600;700&display=swap">
<style>body{{margin:0;background:#0e1417;color:#e8edeb;font:15px/1.55 "IBM Plex Sans","Helvetica Neue",Arial,sans-serif}}
.w{{max-width:900px;margin:0 auto;padding:24px}}h1{{font:700 26px "IBM Plex Sans Condensed"}}h2{{font:600 13px "IBM Plex Mono";letter-spacing:.08em;text-transform:uppercase;color:#39b3c6;margin:0 0 8px}}
.step{{border-left:4px solid #39b3c6;background:#151d21;border:1px solid #26333a;border-left-width:4px;
padding:14px 16px;margin:14px 0;border-radius:6px}}
img,video{{max-width:100%;border:1px solid #26333a;border-radius:4px}}
.big{{font:700 30px "IBM Plex Mono"}}.good{{color:#4fae7f}}.bad{{color:#e0715a}}
.cap{{font-size:11.5px;color:#8b979d;font-family:ui-monospace,Menlo,monospace}}</style>
<div class="w">
<h1>Traffic Case Report — input: <code>{name}</code></h1>
<p>Generated {time.strftime('%d %b %Y %H:%M')} by <code>scripts/case_report.py</code>.
Steps 1–5 are computed fresh from this input — including the twin prediction and same-state proof for THIS road. Step 6 attaches the separate offline network-scale experiment for context.</p>

<div class="step"><h2>Step 1-2 · The system watches the video and judges the traffic</h2>
<img src="{b64(out / 'annotated.gif', 'image/gif')}">
<p>Peak <b>{peak:.0f} vehicles per frame</b> · verdict:
<span class="big {'bad' if congested else 'good'}">{'CONGESTED' if congested else 'FREE FLOW'}</span></p>
<p class="cap">detector: Dhaka fine-tuned RT-DETR r50 (rickshaw/CNG/easy-bike aware) · timeline.json</p></div>

<div class="step"><h2>Step 3-4 · The jam is placed on the real road map and a better route is computed</h2>
<img src="{b64(out / 'route_map.png', 'image/png')}">
<p>Camera edge <code>{cam_edge}</code> · route through the jam
<b class="bad">{routed['naive']['experienced_s']:.0f} s</b> · diverted best route
<b class="good">{routed['informed']['experienced_s']:.0f} s</b> →
<span class="big good">{routed['delay_avoided_s']:.0f} s saved per vehicle</span></p>
<p class="cap">Dijkstra on the frozen 6,527-edge Dhaka network · research/routing/r1_router.py</p></div>

{twin_html}
<div class="step"><h2>Step 6 · Network-scale context (separate OFFLINE experiment)</h2>
{'<video controls muted loop src="' + b64(corr, 'video/mp4') + '"></video>' if corr.exists() else ''}
<p>Rerouting cannot rescue vehicles already trapped — it stops the jam being <i>fed</i>:
approaching vehicles divert upstream, the queue stops growing and drains from the front.
Network-scale, with everything else held identical (same trips, same seeds), this policy gives
<span class="big good">−{md['dso_improvement_percent']:.1f}% mean delay</span>
(p = {md['p_value']:.0e}, 10 seeds).</p>
<p class="cap">artifacts/due_dso_stats/v200/result.json · video: SUMO-GUI render of the twin</p></div>

<p class="cap">DhakaFlow Nexus · report contains no generated imagery · raw data: case.json</p>
</div>"""
    (out / "case_report.html").write_text(html)
    print(f"\nCASE REPORT: {out / 'case_report.html'}")
    print(json.dumps(case, indent=2))


if __name__ == "__main__":
    main()
