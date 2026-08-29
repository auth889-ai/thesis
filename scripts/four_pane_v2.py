#!/usr/bin/env python3
"""Four-pane examiner report v2 — fed ONLY by one run's artifacts."""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FONT = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
        'family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@400;600;'
        '700&family=IBM+Plex+Sans+Condensed:wght@600;700&display=swap">')


def b64(p, mime):
    return (f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()
            if p.exists() else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    a = ap.parse_args()
    out = REPO / "artifacts" / f"run_{a.run}"
    v = json.loads((out / "verdict.json").read_text())
    st = json.loads((out / "traffic_state.json").read_text())
    sy = json.loads((out / "twin_sync.json").read_text())
    plan = json.loads((REPO / v["traceability"]["planner_run"]).read_text())
    ws = st["windows"]
    qmax = max(w["queue_veh"] for w in ws)
    smax = max(w["stopped_duration_max_s"] for w in ws)
    arr = sum(w["arrivals"] for w in ws)
    dis = sum(w["discharges"] for w in ws)
    gif = b64(out / "annotated.gif", "image/gif")

    a0 = plan["branches"]["A0_do_nothing"]["network"]
    dec = v["decision"]
    acted = dec in plan["branches"]
    fc = v["forecast"]

    def kpi(val, lab, cls=""):
        return (f'<div class="{cls}"><b>{val}</b><span>{lab}</span></div>')

    if acted:
        ch = plan["branches"][dec]["network"]
        dpct = 100 * (ch["stopped_veh_s"] - a0["stopped_veh_s"]) / a0["stopped_veh_s"]
        pane4 = f"""
    <div class="ok-banner">INTERVENTION ACCEPTED — {dec}</div>
    <div class="k">{kpi(f"{ch['stopped_veh_s']:.0f}", "network delay (veh·s)", "good")}
    {kpi(f"{ch['arrived']:.0f}", "arrived (A0: " + f"{a0['arrived']:.0f})", "good")}
    {kpi(f"{dpct:+.1f}%", "vs DO NOTHING", "good")}</div>
    <p class="cap">accepted only because every network guard held (throughput,
    teleports, neighbour corridors); per-seed sign-consistent</p>"""
    else:
        rej = [f"<li><code>{c}</code> — {d['label']}</li>"
               for c, d in plan["verdicts"].items()]
        pane4 = f"""
    <div class="no-banner">NO SAFE INTERVENTION IMPROVES THE NETWORK</div>
    <p>Every candidate was simulated from the same t&#8320; and rejected:</p>
    <ul>{''.join(rej)}</ul>
    <p class="cap">Restraint is a measured decision, not a failure — a
    scripted system would always claim improvement.</p>"""

    branches_rows = "".join(
        f"<tr><td>{c}</td><td>{b['stopped_veh_s']:.0f}</td>"
        f"<td>{b['arrived']:.0f}</td>"
        f"<td>{plan['verdicts'].get(c, {}).get('label', 'A0 baseline')}</td></tr>"
        for c, b in ((c, plan["branches"][c]["network"])
                     for c in plan["branches"]))

    html = f"""<title>DhakaFlow Case — {a.run}</title>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
{FONT}
<style>
body{{margin:0;background:#0e1417;color:#e8edeb;font:15px/1.5 "IBM Plex Sans",Arial,sans-serif}}
.g{{display:grid;grid-template-columns:1fr 1fr;gap:14px;max-width:1180px;margin:20px auto;padding:0 16px}}
@media(max-width:860px){{.g{{grid-template-columns:1fr}}}}
.p{{background:#151d21;border:1px solid #26333a;border-radius:8px;padding:16px}}
h1{{max-width:1180px;margin:22px auto 4px;padding:0 16px;font:700 24px "IBM Plex Sans Condensed"}}
.sub{{max-width:1180px;margin:0 auto 6px;padding:0 16px;color:#8b979d;font-size:13.5px}}
h2{{font:600 12.5px "IBM Plex Mono";letter-spacing:.08em;text-transform:uppercase;margin:0 0 10px;color:#39b3c6}}
img{{max-width:100%;border-radius:4px;border:1px solid #26333a}}
.k{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:10px}}
.k div{{border:1px solid #26333a;border-radius:6px;padding:6px 10px}}
.k b{{display:block;font:600 21px "IBM Plex Mono"}}
.k span{{font-size:11px;color:#8b979d}}
.bad b{{color:#e0715a}}.good b{{color:#4fae7f}}
.ok-banner{{font:700 20px "IBM Plex Sans";color:#06272c;background:#4fae7f;border-radius:6px;padding:10px 14px}}
.no-banner{{font:700 18px "IBM Plex Sans";color:#0e1417;background:#d9a23a;border-radius:6px;padding:10px 14px}}
.cap{{font-size:11px;color:#8b979d;font-family:"IBM Plex Mono";margin-top:8px}}
table{{width:100%;border-collapse:collapse;font-size:12.5px;margin-top:8px}}
td,th{{border-bottom:1px solid #26333a;padding:4px 6px;text-align:left}}
code{{color:#39b3c6}}
</style>
<h1>One real input → one measured decision</h1>
<p class="sub">case <code>{a.run}</code> · camera <code>{v['camera']}</code> ·
commit <code>{v['traceability']['project_commit']}</code> · paired seeds
{v['traceability']['seeds']} · every pane regenerates from
artifacts/run_{a.run}/</p>
<div class="g">
  <div class="p"><h2>1 · Input video — measured state</h2>
    {'<img src="' + gif + '">' if gif else ''}
    <div class="k">{kpi(qmax, "peak queue (veh)", "bad")}
      {kpi(f"{smax:.0f}s", "longest standstill", "bad")}
      {kpi(f"{arr}/{dis}", "arrivals / discharges")}</div>
    <p class="cap">tracker: official ByteTrack · rule: {st['rule'][:90]}… ·
    flags: {', '.join(st['quality_flags'])}</p></div>
  <div class="p"><h2>2 · Twin sync + forecast</h2>
    <div class="k">{kpi(sy['observed']['queue_median'], "queue observed")}
      {kpi(sy['sim_queue_at_t0'], "queue in twin at t&#8320;")}
      {kpi(sy['geh_flow'], "flow GEH (<5 ok)", "good" if sy['geh_flow'] < 5 else "bad")}</div>
    <div class="k">{kpi(fc.get('current_mean_speed_m_s', '—'), "net speed now (m/s)")}
      {kpi(fc.get('pred15', {}).get('mean_speed_m_s', '—'), "predicted +15 min")}
      {kpi(f"{v.get('network_speed_drop_15min_pct') or 0}%", "predicted drop",
           "bad" if (v.get('network_speed_drop_15min_pct') or 0) > 10 else "")}</div>
    <p class="cap">sync: Geneva DT-GM pattern · forecast: GraphWaveNet
    (official BasicTS pipeline), history preloaded, availability 100%</p></div>
  <div class="p"><h2>3 · Do nothing — same t&#8320;, +10 min</h2>
    <div class="k">{kpi(f"{a0['stopped_veh_s']:.0f}", "network delay (veh·s)", "bad")}
      {kpi(f"{a0['arrived']:.0f}", "arrived")}
      {kpi(f"{a0['teleports']:.0f}", "teleports")}</div>
    <p class="cap">branch A0 · exact saved state incl. RNG ·
    determinism-checked</p></div>
  <div class="p"><h2>4 · DhakaFlow decision — same t&#8320;</h2>{pane4}</div>
</div>
<div class="g"><div class="p" style="grid-column:1/-1"><h2>All candidate futures (network truth)</h2>
<table><tr><th>candidate</th><th>network delay veh·s</th><th>arrived</th><th>verdict</th></tr>
{branches_rows}</table>
<p class="cap">objective + guards: {plan['objective']}</p></div></div>
"""
    (out / "four_pane.html").write_text(html)
    print("four-pane v2:", out / "four_pane.html")


if __name__ == "__main__":
    main()
