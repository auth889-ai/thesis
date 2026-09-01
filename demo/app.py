#!/usr/bin/env python3
"""DhakaFlow demo — `streamlit run demo/app.py`

Four panels, all read from pipeline outputs (nothing typed by hand):
  1. Map      — the real Dhaka R1 network, sensor nodes, NLP incident edges
  2. Live     — Google live/reference derived congestion states
  3. Predict  — twin floors + BasicTS benchmark tables
  4. Route    — arms x seeds + network-wide decision guard
  5. Network  — V2X penetration sweep + latency table
Missing outputs are shown as "not produced yet" with the command that produces them.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from demo.evidence import latest_arms_file, read_jsonl

REPO = Path(__file__).resolve().parents[1]
NET = REPO / "paper_labs/02_dhaka_osm/outputs/lab02_v2/network/dhaka_r1.net.xml"

st.set_page_config(page_title="DhakaFlow", layout="wide")
st.title("DhakaFlow — forecast-aware route guidance on real Dhaka roads")


def md_or_missing(rel: str, cmd: str):
    p = REPO / rel
    if p.exists():
        st.markdown(p.read_text())
    else:
        st.info(f"`{rel}` not produced yet — run `{cmd}`")


@st.cache_data(show_spinner="loading R1 network")
def net_paths(max_edges: int = 7000):
    import sumolib
    net = sumolib.net.readNet(str(NET))
    paths = []
    for e in net.getEdges()[:max_edges]:
        pts = [list(net.convertXY2LonLat(x, y)) for x, y in e.getShape()]
        paths.append({"id": e.getID(), "path": pts, "prio": e.getPriority()})
    return paths


tab_chain, tab_map, tab_live, tab_pred, tab_route, tab_net, tab_nlp = st.tabs([
    "Live chain", "Map", "Live reference", "Predict", "Route", "Network", "NLP events"
])

with tab_chain:
    st.markdown("#### live Dhaka APIs → state → forecast → edge times → router → SUMO counterfactual → decision")
    man = REPO / "artifacts/live_dhaka/RECORDER_MANIFEST.json"
    series_man = REPO / "predict/data/live_dhaka/MANIFEST.json"
    c1, c2, c3, c4 = st.columns(4)
    if man.exists():
        m = json.loads(man.read_text())
        c1.metric("Live captures", m["rows_ok"], f"{m['rows_failed']} failed" if m["rows_failed"] else "0 failed")
        c2.metric("Recorder", m["reality"], f"every {m['interval_s']}s")
    if series_man.exists():
        sm = json.loads(series_man.read_text())
        c3.metric("History", f"{sm['span_hours']:.1f} h", f"{sm['bins']} bins x {len(sm['corridors'])} corridors")
        c4.metric("Coverage", f"{sm['coverage']:.0%}", sm["reality"])
    lc = REPO / "route/results/live_chain.json"
    if lc.exists():
        d = json.loads(lc.read_text())
        dec = d["decision"]["decision"]
        (st.success if dec == "ACT" else st.warning)(f"**{dec}** — {d['decision']['reason']}")
        st.caption(f"source {d['source']['reality']} · {d['edges_congested']} congested edges · "
                   f"demand {d['demand']}")
        lv = d["source"].get("levels", {})
        if lv:
            st.dataframe(pd.DataFrame([{"corridor": k, "level": v,
                                        "state": ["FREE_FLOW", "SLOW", "CONGESTED", "SEVERE"][int(min(3, max(0, round(v))))]}
                                       for k, v in sorted(lv.items())]), width="stretch", hide_index=True)
    else:
        st.info("no live-chain run yet — `python route/live_chain.py --seeds 11,12,13`")
    sweep = sorted(REPO.glob("route/results/live_chain_c*.json"))
    if sweep:
        st.markdown("**Advised-share sweep** — the decision rule is not one-sided:")
        rows = []
        for f in sweep:
            d = json.loads(f.read_text())
            rows.append({"advised share": d["compliance"], "decision": d["decision"]["decision"],
                         "mean veh-h change %": d["decision"].get("mean_pct"),
                         "seeds improved": f"{sum(1 for x in d['decision'].get('vehicle_hours_pct_per_seed', []) if x < 0)}"
                                           f"/{len(d['decision'].get('vehicle_hours_pct_per_seed', []))}",
                         "source": d["source"]["reality"]})
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    md_or_missing("route/results/live_chain.md", "python route/live_chain.py --seeds 11,12,13")

with tab_map:
    try:
        import pydeck as pdk
        paths = net_paths()
        layers = [pdk.Layer("PathLayer", paths, get_path="path", get_color=[120, 130, 140], width_min_pixels=1)]
        ev = REPO / "nlp/results/events.jsonl"
        if ev.exists():
            events = read_jsonl(ev)
            hot = {e for x in events for e in x.get("edges", [])}
            layers.append(pdk.Layer("PathLayer", [p for p in paths if p["id"] in hot], get_path="path",
                                    get_color=[220, 80, 40], width_min_pixels=4))
            pts = [x for x in events if x.get("lat")]
            layers.append(pdk.Layer("ScatterplotLayer", pts, get_position="[lon, lat]", get_radius=60,
                                    get_fill_color=[220, 80, 40], pickable=True))
            st.caption(f"{len(events)} NLP events, {len(hot)} affected edges (red)")
        sn = REPO / "predict/data/dhaka_twin/sensor_nodes.json"
        if sn.exists():
            nodes = json.loads(sn.read_text())
            nodes = nodes.get("sensors", nodes) if isinstance(nodes, dict) else nodes
            pts = [n for n in nodes if isinstance(n, dict) and "lon" in n]
            if pts:
                layers.append(pdk.Layer("ScatterplotLayer", pts, get_position="[lon, lat]", get_radius=35,
                                        get_fill_color=[20, 140, 140]))
                st.caption(f"{len(pts)} twin sensors (teal)")
        st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=pdk.ViewState(latitude=23.75, longitude=90.39, zoom=12.3),
                                 map_style=None, tooltip={"text": "{text}"}))
    except Exception as ex:  # keep the demo alive without the net
        st.warning(f"map unavailable: {ex}")

with tab_live:
    md_or_missing("artifacts/p_live/live_reference_summary.md",
                  "make live-capture or python predict/summarize_live_reference.py")

with tab_pred:
    md_or_missing("predict/results/live_floors.md",
                  "python predict/record_live.py --live --yes  (recorder) && python predict/live_state.py --report")
    sf = REPO / "predict/data/live_dhaka/series.npz"
    if sf.exists():
        import numpy as np
        z = np.load(sf, allow_pickle=True)
        vals, mask, corridors = z["values"], z["mask"], [str(c) for c in z["corridors"]]
        if vals.shape[0] > 1:
            st.markdown("**Live Dhaka congestion level** (0 free-flow → 3 severe)")
            st.line_chart(pd.DataFrame(np.where(mask, vals, np.nan), columns=corridors))
        else:
            st.caption(f"live series: {vals.shape[0]} bin so far — the recorder needs ~2 h for a chart")
    md_or_missing("predict/results/twin_floors.md", "make data && python predict/baselines_twin.py")
    md_or_missing("predict/results/twin_models.md", "notebooks/Predict_Twin_Colab.ipynb (Colab GPU)")
    md_or_missing("predict/results/benchmark.md", "notebooks/Predict_BasicTS_Colab.ipynb")

with tab_route:
    arms_file = latest_arms_file(REPO)
    if not arms_file:
        st.info("no `route/results/arms_h*.json` yet — run `make route`")
    else:
        st.caption(f"routing source: `{arms_file.relative_to(REPO)}`")
        arms = json.loads(arms_file.read_text())
        rows = [{"arm": a, "seed": s, **m.get("metrics", m)} for a, seeds in arms.items() for s, m in seeds.items()]
        df = pd.DataFrame(rows)
        cols = [c for c in ["total_vehicle_hours", "mean_travel_time_all", "mean_travel_time_s", "p95_travel_time_s", "total_waiting_s", "mean_time_loss_s", "arrived", "teleports"] if c in df]
        st.dataframe(df.groupby("arm")[cols].mean().round(1), width="stretch")
        chart_col = "total_vehicle_hours" if "total_vehicle_hours" in df else "mean_travel_time_s"
        st.bar_chart(df.groupby("arm")[chart_col].mean())
        md_or_missing("route/results/decision_guard.md", "python route/decision_guard.py --horizon 7200")
        md_or_missing("route/results/stats.md", "python route/stats.py --horizon 7200")
    md_or_missing("route/results/incident.md", "python route/incident_scenario.py --seeds 11,12,13")
    md_or_missing("route/results/gridlock_check.md", "see route/results/gridlock_check.md")

with tab_net:
    md_or_missing("network/results/event_sweep.md", "python network/event_sweep.py --source nlp_event --p 0.25")
    md_or_missing("network/results/penetration.md", "make network")
    md_or_missing("network/results/latency.md", "python network/latency_injection.py")

with tab_nlp:
    md_or_missing("nlp/results/classifier.md", "make nlp")
    ev = REPO / "nlp/results/events.jsonl"
    if ev.exists():
        st.dataframe(pd.DataFrame(read_jsonl(ev)), width="stretch")
    txt = st.text_input("Try a traffic post", "Heavy jam at Karwan Bazar after a bus breakdown")
    if txt and (REPO / "nlp/event_feed.py").exists():
        import subprocess, sys
        r = subprocess.run([sys.executable, str(REPO / "nlp/event_feed.py"), "--text", txt], capture_output=True, text=True)
        st.code(r.stdout or r.stderr)
