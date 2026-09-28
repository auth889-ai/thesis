#!/usr/bin/env python3
"""V2X advisory for OUR event (NLP report or forecast), not the stock ice stub.

    python -m traffictwin.networking.mosaic.event_sweep --source nlp_event --p 0.25 --seed 11 --duration 900
    python -m traffictwin.networking.mosaic.event_sweep --source predicted --p 1.0
    python -m traffictwin.networking.mosaic.event_sweep --aggregate

Reuses src/pipeline/networking/penetration_sweep.py unchanged (build_scenario / run_mosaic / parse_point) and
only rewrites two scenario inputs:
  environment_config.json  the hazard rectangle = bounding box (+30 m) of the event edges, active
                           from --t-inc; the type stays TRACTION_HAZARD/ICE because that is the event
                           the OFFICIAL WeatherWarningApp senses -> DENM -> NavigationModule reroute.
                           Changing the type would mean editing the official app; we change WHERE
                           and WHEN the hazard is, which is what the NLP/forecast layer knows.
  sumo (additional file)   the event is physically real: a variableSpeedSign cuts the event edges'
                           lanes to --v-inc m/s from --t-inc to the end (identical for every p).
Event sources:
  nlp_event   edges from results/nlp/events_karwan_bazar.jsonl (text -> classifier -> gazetteer -> R1 edges)
  predicted   the --top-k edges with the highest traveltime / free-flow ratio in a weight table
              (results/routing/static_s11_h7200/edgedata.xml interval containing --t-inc) = "predicted congestion"
Outputs results/networking/event_{source}_p{P}_s{SEED}.json and event_sweep.csv/.md.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from traffictwin.paths import REPO
sys.path.insert(0, str(REPO))
from traffictwin.networking.mosaic import penetration_sweep as ps  # noqa: E402

NET = REPO / "data/cities/dhaka_r1/dhaka_r1.net.xml.gz"
EVENT = REPO / "results/nlp/events_karwan_bazar.jsonl"
RESULTS = ps.RESULTS


def event_edges(source: str, t_inc: int, top_k: int) -> tuple[list[str], str]:
    if source == "nlp_event":
        ev = next(json.loads(l) for l in EVENT.read_text().splitlines() if l.strip() and '"edges"' in l)
        return ev["edges"], f'NLP: "{ev["text"]}" -> {ev["label"]} @ {ev.get("place")}'
    import sumolib
    net = sumolib.net.readNet(str(NET))
    cands = sorted(REPO.glob("results/routing/static_s11_h*/edgedata.xml"), key=lambda p: int(p.parent.name.split("_h")[1]))
    wf = cands[-1]
    ratios = {}
    for iv in ET.parse(wf).getroot().iter("interval"):
        if float(iv.get("begin")) <= t_inc < float(iv.get("end")):
            for ed in iv.iter("edge"):
                tt = ed.get("traveltime")
                if tt and net.hasEdge(ed.get("id")):
                    e = net.getEdge(ed.get("id"))
                    ratios[e.getID()] = float(tt) / (e.getLength() / max(e.getSpeed(), 0.1))
    top = sorted(ratios, key=ratios.get, reverse=True)[:top_k]
    return top, f"predicted: top-{top_k} traveltime/free-flow edges of {wf.relative_to(REPO)} at t={t_inc}s"


def rectangle(edges: list[str], pad_m: float = 30.0) -> dict:
    import sumolib
    net = sumolib.net.readNet(str(NET))
    lats, lons = [], []
    for e in edges:
        if net.hasEdge(e):
            for x, y in net.getEdge(e).getShape():
                lon, lat = net.convertXY2LonLat(x, y)
                lats.append(lat); lons.append(lon)
    dlat = pad_m / 111_320.0
    dlon = pad_m / (111_320.0 * 0.916)
    return {"lat_min": min(lats) - dlat, "lat_max": max(lats) + dlat, "lon_min": min(lons) - dlon, "lon_max": max(lons) + dlon}


def lanes_of(edges: list[str]) -> list[str]:
    import sumolib
    net = sumolib.net.readNet(str(NET))
    return [l.getID() for e in edges if net.hasEdge(e) for l in net.getEdge(e).getLanes()]


def build(source: str, p: float, seed: int, duration: int, t_inc: int, v_inc: float, top_k: int) -> tuple[Path, dict, list[str], str]:
    edges, desc = event_edges(source, t_inc, top_k)
    rect = rectangle(edges)
    scen = ps.build_scenario(p, seed, duration)
    dst = ps.SCEN_ROOT / f"event_{source}_{ps.point_name(p, seed)}"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.move(str(scen), str(dst))
    scfg = dst / "sumo/sumo_config.json"                      # absolute output paths were written for the old dir
    scfg.write_text(scfg.read_text().replace(str(scen.resolve()), str(dst.resolve())).replace(str(scen), str(dst)))
    env = {"events": [{"location": {"area": {"type": "Rectangle",
                                             "a": {"latitude": rect["lat_max"], "longitude": rect["lon_min"]},
                                             "b": {"latitude": rect["lat_min"], "longitude": rect["lon_max"]}}},
                       "time": {"start": f"{t_inc} s", "end": f"{duration} s"}, "type": "TRACTION_HAZARD", "value": "ICE"}]}
    (dst / "environment/environment_config.json").write_text(json.dumps(env, indent=4))
    add = dst / "sumo/event.add.xml"
    lanes = lanes_of(edges)
    add.write_text('<additional>\n  <variableSpeedSign id="event" lanes="%s">\n    <step time="%d" speed="%.2f"/>\n  </variableSpeedSign>\n</additional>\n'
                   % (" ".join(lanes), t_inc, v_inc))
    sc = json.loads((dst / "sumo/sumo_config.json").read_text())
    sc["additionalSumoParameters"] += f" --additional-files {add.resolve()}"
    (dst / "sumo/sumo_config.json").write_text(json.dumps(sc, indent=1))
    return dst, rect, edges, desc


def flatten(d: dict, prefix: str = "") -> dict:
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out.update(flatten(v, f"{prefix}{k}."))
        elif isinstance(v, (int, float)) or v is None:
            out[f"{prefix}{k}"] = v
    return out


PREF = ["vehicles.registered", "vehicles.equipped", "v2x.senders", "v2x.receivers", "v2x.delivery_ratio_veh", "v2x.latency_mean_ms",
        "v2x.latency_p95_ms", "routing.route_switches", "routing.switch_fraction_of_equipped",
        "sumo.tripinfo.finished.n", "sumo.tripinfo.finished.duration_mean_s", "sumo.tripinfo.finished.duration_p95_s",
        "sumo.tripinfo.finished.timeLoss_mean_s", "sumo.tripinfo.finished_equipped.duration_mean_s",
        "sumo.tripinfo.finished_unequipped.duration_mean_s"]


def aggregate():
    rows = []
    for f in sorted(RESULTS.glob("event_*_p*_s*.json")):
        d = json.loads(f.read_text())
        fl = flatten({k: d[k] for k in ("vehicles", "v2x", "routing", "sumo") if k in d})
        rows.append({"source": d["event"]["source"], "p": d["point"]["p"] if isinstance(d.get("point"), dict) else d["event"]["p"],
                     "seed": d["event"]["seed"], "wall_s": round(d.get("wall_s") or 0), **{k: fl.get(k) for k in PREF if k in fl}})
    if not rows:
        return
    cols = list(dict.fromkeys(k for r in rows for k in r))          # union: p=0 rows lack the equipped split
    rows = [{c: r.get(c) for c in cols} for r in rows]
    with open(RESULTS / "event_sweep.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols); w.writeheader(); w.writerows(rows)
    md = ["# V2X advisory from OUR event (NLP report / forecast) — Eclipse MOSAIC 25.2, Dhaka R1\n",
          "Hazard rectangle = bounding box of the event edges; the event is physically real in SUMO (variableSpeedSign). "
          "Same official WeatherWarningApp/NavigationModule chain as the penetration sweep; only WHERE/WHEN the hazard is comes from us.\n",
          "| " + " | ".join(".".join(c.split(".")[-2:]).replace("tripinfo.", "") if c.startswith("sumo.") else c.split(".")[-1] for c in cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        md.append("| " + " | ".join("" if r[c] is None else (f"{r[c]:.3g}" if isinstance(r[c], float) else str(r[c])) for c in cols) + " |")
    descs = {json.loads(f.read_text())["event"]["desc"] for f in RESULTS.glob("event_*_p*_s*.json")}
    md += ["", *[f"* {d}" for d in sorted(descs)], "", "Regenerate: `python -m traffictwin.networking.mosaic.event_sweep --source nlp_event --p <P> --seed <S>`; `--aggregate` rebuilds this table."]
    (RESULTS / "event_sweep.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", choices=["nlp_event", "predicted"], default="nlp_event")
    ap.add_argument("--p", type=float, default=0.25)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--duration", type=int, default=900)
    ap.add_argument("--t-inc", type=int, default=200)
    ap.add_argument("--v-inc", type=float, default=1.5)
    ap.add_argument("--top-k", type=int, default=8)
    ap.add_argument("--aggregate", action="store_true")
    a = ap.parse_args()
    if a.aggregate:
        aggregate(); return 0
    scen, rect, edges, desc = build(a.source, a.p, a.seed, a.duration, a.t_inc, a.v_inc, a.top_k)
    ps.HAZARD.update(rect)                      # parse_point's time-to-hazard uses this rectangle
    stdout_dir = RESULTS / "logs"; stdout_dir.mkdir(parents=True, exist_ok=True)
    log_dir, wall = ps.run_mosaic(scen, stdout_dir / f"mosaic_{scen.name}.out")
    res = ps.parse_point(log_dir, scen, a.p, a.seed, a.duration, wall_s=wall)
    res["event"] = {"source": a.source, "desc": desc, "edges": edges, "rectangle": rect, "t_inc": a.t_inc, "v_inc": a.v_inc,
                    "p": a.p, "seed": a.seed, "n_lanes_slowed": len(lanes_of(edges))}
    out = RESULTS / f"event_{a.source}_p{a.p:g}_s{a.seed}.json"
    out.write_text(json.dumps(res, indent=1, default=str))
    ps.keep_small_logs(log_dir, a.p, a.seed)
    shutil.rmtree(log_dir, ignore_errors=True)
    print(f"[event] wrote {out}")
    aggregate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
