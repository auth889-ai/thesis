"""penetration.csv and penetration.md from every point JSON: per point, and means over seeds per P."""
from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict

from core.networking.mosaic.sweep.scenario import RESULTS

HEADER = ("Knob: `mapping_config.json` -> `typeDistributions.DEFAULT_VEHTYPE` = [{AdHoc: WeatherWarningApp+SlowDownApp, weight p}, "
          "{Unequipped: SlowDownApp, weight 1-p}], `config.fixedOrder=false` (stochastic, seed-driven). "
          "Hazard: TRACTION_HAZARD/ICE rectangle at Karwan Bazar (environment_config.json); equipped vehicles that sense it "
          "broadcast DENMs over SNS ad-hoc (ITS-G5, multi-hop TTL 20); receivers with the hazard on their route reroute "
          "through the official NavigationModule.")
DEFINITIONS = ("Definitions: equipped = registered with WeatherWarningApp; delivery_ratio_veh = distinct receivers / equipped; "
               "latency = t_rx - t_tx per MessageId; route switches = CentralNavigationComponent 'Change to route' lines; "
               "travel time = SUMO tripinfo of finished trips (equipped vs unequipped split).")


def _r(v, nd):
    return round(v, nd) if v is not None else ""


def _row(r: dict) -> dict:
    v, x, rt, lat = r["vehicles"], r["v2x"], r["routing"], r["v2x"]["latency"]
    ti = r["sumo"]["tripinfo"]
    fin = ti.get("finished", {}) if ti.get("available") else {}
    fe = ti.get("finished_equipped", {}) if ti.get("available") else {}
    fu = ti.get("finished_unequipped", {}) if ti.get("available") else {}
    return {
        "p": r["point"]["p"], "seed": r["point"]["seed"], "duration_s": r["point"]["duration_s"], "wall_s": round(r["wall_s"] or 0),
        "registered": v["registered"], "equipped": v["equipped"], "equipped_frac": round(v["equipped_fraction"] or 0, 3),
        "denm_sent": x["denm_sent"], "senders": x["senders"], "receptions": x["receptions"], "receivers": x["receivers"],
        "delivery_ratio_veh": _r(x["delivery_ratio_veh"], 3), "receptions_per_denm": _r(x["receptions_per_denm"], 1),
        "lat_mean_ms": _r(lat["mean_ms"], 2), "lat_p50_ms": _r(lat["p50_ms"], 2), "lat_p95_ms": _r(lat["p95_ms"], 2), "lat_p99_ms": _r(lat["p99_ms"], 2),
        "route_switches": rt["route_switches"], "vehicles_switched": rt["vehicles_switched"],
        "trips_finished": fin.get("n", ""), "trips_unfinished": ti.get("unfinished", ""),
        "tt_mean_s": round(fin["duration_mean_s"], 1) if fin.get("n") else "", "tt_p95_s": round(fin["duration_p95_s"], 1) if fin.get("n") else "",
        "timeLoss_mean_s": round(fin["timeLoss_mean_s"], 1) if fin.get("n") else "",
        "tt_mean_equipped_s": round(fe["duration_mean_s"], 1) if fe.get("n") else "", "tt_mean_unequipped_s": round(fu["duration_mean_s"], 1) if fu.get("n") else "",
        "tth_p50_s": r["time_to_hazard"]["tth_s_p50"] if r["time_to_hazard"]["n"] else "",
    }


def aggregate():
    rows = sorted((_row(json.loads(f.read_text())) for f in sorted(RESULTS.glob("penetration_p*_s*.json"))), key=lambda r: (r["p"], r["seed"]))
    if not rows:
        print("[aggregate] no point JSONs yet")
        return
    csv_path = RESULTS / "penetration.csv"
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    byp = defaultdict(list)
    for r in rows:
        byp[r["p"]].append(r)

    def m(key, rs, nd=2):
        vals = [r[key] for r in rs if r[key] != ""]
        return round(statistics.fmean(vals), nd) if vals else "-"

    md = ["# V2X penetration sweep - Eclipse MOSAIC 25.2, Dhaka R1 (registered scenario)", "", HEADER, "", DEFINITIONS, "",
          "## Per point", "",
          "| p | seed | wall s | registered | equipped | DENM sent | senders | receptions | receivers | deliv. ratio | lat mean ms | lat p95 ms | route switches | veh switched | trips fin. | TT mean s | TT p95 s | timeLoss mean s | TT eq. s | TT uneq. s |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['p']} | {r['seed']} | {r['wall_s']} | {r['registered']} | {r['equipped']} | {r['denm_sent']} | {r['senders']} | "
                  f"{r['receptions']} | {r['receivers']} | {r['delivery_ratio_veh']} | {r['lat_mean_ms']} | {r['lat_p95_ms']} | "
                  f"{r['route_switches']} | {r['vehicles_switched']} | {r['trips_finished']} | {r['tt_mean_s']} | {r['tt_p95_s']} | "
                  f"{r['timeLoss_mean_s']} | {r['tt_mean_equipped_s']} | {r['tt_mean_unequipped_s']} |")
    md += ["", "## Mean over seeds", "",
           "| p | n seeds | equipped frac | receivers | deliv. ratio | lat mean ms | lat p95 ms | route switches | TT mean s | TT p95 s | timeLoss mean s |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for p_, rs in sorted(byp.items()):
        md.append(f"| {p_} | {len(rs)} | {m('equipped_frac', rs, 3)} | {m('receivers', rs, 0)} | {m('delivery_ratio_veh', rs, 3)} | "
                  f"{m('lat_mean_ms', rs)} | {m('lat_p95_ms', rs)} | {m('route_switches', rs, 0)} | {m('tt_mean_s', rs, 1)} | "
                  f"{m('tt_p95_s', rs, 1)} | {m('timeLoss_mean_s', rs, 1)} |")
    md += ["", "Source JSONs: `results/networking/penetration_p{P}_s{SEED}.json`; regenerate with "
               "`python -m core.networking.mosaic.penetration_sweep --aggregate`."]
    (RESULTS / "penetration.md").write_text("\n".join(md) + "\n")
    print(f"[aggregate] {len(rows)} points -> {csv_path}, {RESULTS / 'penetration.md'}")
