#!/usr/bin/env python3
"""FOUR-PANE report — the audit's target front-end, from real artifacts only.

  Pane 1  what the examiner gave      (annotated video + measured state)
  Pane 2  what the system understands (map: camera, jam edges, routes)
  Pane 3  do nothing                  (same-state twin branch A)
  Pane 4  our action                  (same-state twin branch B + actions)

    python scripts/four_pane_report.py --case rush_test \
        --counterfactual kb_mild_gated_s11 [--out artifacts/four_pane.html]

Panes 3-4 come from ONE saved twin state (saveState t0) — identical pasts,
measured difference. If the counterfactual chose NO action (queue below the
act-threshold), pane 4 says so — restraint is a decision too.
"""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def b64(p: Path, mime: str) -> str | None:
    return (f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()
            if p.exists() else None)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True, help="artifacts/case_<name>")
    ap.add_argument("--counterfactual", required=True,
                    help="artifacts/same_state/<name>")
    ap.add_argument("--out", type=Path,
                    default=REPO / "artifacts" / "four_pane.html")
    a = ap.parse_args()

    case_dir = REPO / "artifacts" / f"case_{a.case}"
    ss = json.loads((REPO / "artifacts" / "same_state" / a.counterfactual /
                     "result.json").read_text())
    case = json.loads((case_dir / "case.json").read_text())
    tl = json.loads((case_dir / "timeline.json").read_text())

    peak = max((w["mean_vehicles"] for w in tl), default=0)
    congested = sum(1 for w in tl if w["state"] == "CONGESTED")
    stopped_frac = max((w["stopped_fraction"] for w in tl), default=0)

    gif = b64(case_dir / "annotated.gif", "image/gif")
    rmap = b64(case_dir / "route_map.png", "image/png")

    na, ct = ss["no_action"], ss["control"]
    fp = ss["four_pane"]
    acted = ss.get("action_taken", True)
    dq = fp["queue_no_action"] - fp["queue_control"]
    qpct = 100 * dq / max(fp["queue_no_action"], 1)

    html = f"""<title>Four-Pane Case — {a.case}</title>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@400;600;700&family=IBM+Plex+Sans+Condensed:wght@600;700&display=swap">
<style>
body{{margin:0;background:#0e1417;color:#e8edeb;font:15px/1.5 "IBM Plex Sans","Helvetica Neue",Arial,sans-serif}}
.g{{display:grid;grid-template-columns:1fr 1fr;gap:14px;max-width:1150px;margin:20px auto;padding:0 16px}}
.p{{background:#151d21;border:1px solid #26333a;border-radius:8px;padding:16px}}
h1{{max-width:1150px;margin:22px auto 4px;padding:0 16px;font-size:24px;font-family:"IBM Plex Sans Condensed"}}
.sub{{max-width:1150px;margin:0 auto 6px;padding:0 16px;color:#8b979d;font-size:13.5px}}
h2{{font:600 13px "IBM Plex Mono";letter-spacing:.08em;text-transform:uppercase;margin:0 0 10px;color:#39b3c6}}
img{{max-width:100%;border-radius:4px;border:1px solid #26333a}}
.k{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:10px}}
.k div{{border:1px solid #26333a;border-radius:6px;padding:6px 10px}}
.k b{{display:block;font:600 22px "IBM Plex Mono"}}
.k span{{font-size:11.5px;color:#8b979d}}
.bad b{{color:#e0715a}}.good b{{color:#4fae7f}}
.verdict{{font-size:26px;font-weight:800}}
.act{{background:#14231b;border:1px solid #2c4636;border-radius:6px;padding:8px 12px;margin-top:10px;font-size:13.5px}}
.cap{{font-size:11px;color:#8b979d;font-family:ui-monospace,Menlo,monospace;margin-top:8px}}
.delta{{font-size:30px;font-weight:800;color:#4fae7f}}
</style>
<h1>One input → measured decision → proven difference</h1>
<p class="sub">Panes 3 and 4 branch from ONE saved simulator state
(traci.saveState at t₀={ss['t0_s']:.0f}s) — identical pasts, so the difference
is caused by the control. Twin scope v1: fair fixed demand; the video selects
site &amp; trigger (declared in docs/SYSTEM_DESIGN.md).</p>
<div class="g">
  <div class="p"><h2>1 · What you gave</h2>
    {'<img src="' + gif + '">' if gif else ''}
    <div class="k">
      <div class="bad"><b>{peak:.0f}</b><span>peak vehicles/frame</span></div>
      <div class="bad"><b>{congested}/{len(tl)}</b><span>windows CONGESTED</span></div>
      <div class="bad"><b>{stopped_frac:.0%}</b><span>max stopped fraction</span></div>
    </div>
    <p class="cap">artifacts/case_{a.case}/ · detector: {case.get('detector',{}).get('label','')}</p></div>
  <div class="p"><h2>2 · What the system understands</h2>
    {'<img src="' + rmap + '">' if rmap else ''}
    <p class="cap">camera edge {case.get('camera_edge','—')} · route options computed for THIS case</p></div>
  <div class="p"><h2>3 · PREDICTED future — do nothing (+10 min from t₀)</h2>
    <div class="k">
      <div class="bad"><b>{fp['queue_no_action']}</b><span>target queue (veh)</span></div>
      <div class="bad"><b>{fp['network_stopped_no_action']}</b><span>network stopped</span></div>
      <div><b>{fp['arrived_no_action']}</b><span>arrived in horizon</span></div>
    </div>
    <p class="cap">branch A · mean timeLoss of horizon arrivals: {na['mean_time_loss_of_horizon_arrivals_s']} s</p></div>
  <div class="p"><h2>4 · DhakaFlow acts — same t₀, +10 min</h2>
    {"<div class='k'>"
     f"<div class='good'><b>{fp['queue_control']}</b><span>target queue (veh)</span></div>"
     f"<div><b>{fp['network_stopped_control']}</b><span>network stopped</span></div>"
     f"<div><b>{fp['arrived_control']}</b><span>arrived in horizon</span></div></div>"
     f"<p class='delta'>queue −{qpct:.0f}%</p>"
     "<div class='act'>ACTIONS: extend green on the jammed approach (min-green "
     "respected) · reroute approaching vehicles only, 50% bounded, "
     "capacity-gated · trapped vehicles never touched</div>"
     if acted else
     "<p class='verdict'>NO ACTION WARRANTED</p>"
     "<div class='act'>Target queue below the action threshold at t₀ — "
     "intervening at a barely-queued junction measurably makes traffic worse "
     "(seed-13 experiment). Restraint is a decision.</div>"}
    <p class="cap">branch B · mean timeLoss: {ct['mean_time_loss_of_horizon_arrivals_s']} s ·
    rule: {ss.get('action_rule','')}</p></div>
</div>
<p class="sub">Every number regenerates: scripts/same_state_counterfactual.py ·
scripts/case_report.py · no generated imagery anywhere on this page.</p>"""
    a.out.write_text(html)
    print(f"four-pane report: {a.out}")


if __name__ == "__main__":
    main()
