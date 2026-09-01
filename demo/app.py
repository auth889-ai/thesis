#!/usr/bin/env python3
"""DhakaFlow demo — `streamlit run demo/app.py`

Four panels, all read from pipeline outputs (nothing typed by hand):
  1. Map      — the real Dhaka R1 network (sumolib -> lon/lat), sensor nodes, NLP incident edges
  2. Predict  — twin floors + BasicTS benchmark tables
  3. Route    — arms x seeds: mean / p95 travel time, waiting, teleports (route/results/arms_h*.json)
  4. Network  — V2X penetration sweep + latency table
Missing outputs are shown as "not produced yet" with the command that produces them.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import pandas as pd
import streamlit as st

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


tab_map, tab_pred, tab_route, tab_net, tab_nlp = st.tabs(["Map", "Predict", "Route", "Network", "NLP events"])

with tab_map:
    try:
        import pydeck as pdk
        paths = net_paths()
        layers = [pdk.Layer("PathLayer", paths, get_path="path", get_color=[120, 130, 140], width_min_pixels=1)]
        ev = REPO / "nlp/results/events.jsonl"
        if ev.exists():
            events = [json.loads(l) for l in ev.read_text().splitlines() if l.strip()]
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

with tab_pred:
    md_or_missing("predict/results/twin_floors.md", "make data && python predict/baselines_twin.py")
    md_or_missing("predict/results/benchmark.md", "notebooks/Predict_BasicTS_Colab.ipynb")

with tab_route:
    files = sorted(glob.glob(str(REPO / "route/results/arms_h*.json")))
    if not files:
        st.info("no `route/results/arms_h*.json` yet — run `make route`")
    else:
        arms = json.loads(Path(files[-1]).read_text())
        rows = [{"arm": a, "seed": s, **m.get("metrics", m)} for a, seeds in arms.items() for s, m in seeds.items()]
        df = pd.DataFrame(rows)
        cols = [c for c in ["mean_travel_time_s", "p95_travel_time_s", "total_waiting_s", "mean_time_loss_s", "arrived", "teleports"] if c in df]
        st.dataframe(df.groupby("arm")[cols].mean().round(1), use_container_width=True)
        st.bar_chart(df.groupby("arm")["mean_travel_time_s"].mean())
        md_or_missing("route/results/stats.md", "python route/stats.py")

with tab_net:
    md_or_missing("network/results/penetration.md", "make network")
    md_or_missing("network/results/latency.md", "python network/latency_injection.py")

with tab_nlp:
    md_or_missing("nlp/results/classifier.md", "make nlp")
    ev = REPO / "nlp/results/events.jsonl"
    if ev.exists():
        st.dataframe(pd.DataFrame([json.loads(l) for l in ev.read_text().splitlines() if l.strip()]), use_container_width=True)
    txt = st.text_input("Try a traffic post", "Heavy jam at Karwan Bazar after a bus breakdown")
    if txt and (REPO / "nlp/event_feed.py").exists():
        import subprocess, sys
        r = subprocess.run([sys.executable, str(REPO / "nlp/event_feed.py"), "--text", txt], capture_output=True, text=True)
        st.code(r.stdout or r.stderr)
