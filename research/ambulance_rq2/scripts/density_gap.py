"""RQ2 threat to validity: why the simulation's INT section stays near 4.5 vehicles/km while DhaTraX recorded 58 (07:00-08:00).
Checks, in order, before any cause is claimed:
  1. definitions: DhaTraX density = mean tracked vehicles in its camera zone / zone length (per road approach, all lanes, all ten
     classes; 89.2 m at INT). Ours, the same: vehicles on the INT edge (3 lanes, 91.8 m) / its length, every second.
  2. vehicle space: each vType's length, minGap, width and minGapLat as SUMO uses them, and the lane-based jam density they allow.
  3. lane discipline: the same demand with the sublane model and smaller lateral gaps for two-wheelers and CNGs (variant "tight").
  4. supply: how many vehicles enter the INT edge per hour (DhaTraX recorded 1,184 an hour there 07:00-08:00), its peak density, and
     the densest edges elsewhere, i.e. whether the section is ever loaded or the network jams before traffic reaches it.
One run per variant at demand x4 (the gridlock level), seed 11. Writes evidence/ambulance_rq2/density_gap.json (+ .sha256)."""
import hashlib
import json
import re
import statistics
import sys
import tempfile
from pathlib import Path

import pandas as pd
import traci

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))
from core.simulation.ambulance import service  # noqa: E402

SECTION, SCALE, SEED, HORIZON = "691209729#5", 4.0, 11, 3600
TIGHT = {"Motor_Cycle": {"minGapLat": "0.1", "latAlignment": "arbitrary", "minGap": "1.0"}, "Bicycle": {"minGapLat": "0.1", "latAlignment": "arbitrary"},
         "Rickshaw": {"minGapLat": "0.15", "latAlignment": "arbitrary"}, "CNG": {"minGapLat": "0.2", "latAlignment": "arbitrary", "minGap": "1.5"}}


def routes(variant: str, src: Path, work: Path) -> Path:
    if variant == "default":
        return src
    text = src.read_text()
    for vid, attrs in TIGHT.items():
        extra = " ".join(f'{k}="{v}"' for k, v in attrs.items())
        text = re.sub(rf'<vType id="{vid}" ([^/]*)/>', rf'<vType id="{vid}" \1 {extra}/>', text)
    p = work / "dhaka_tight.rou.xml"
    p.write_text(text)
    return p


def run(variant: str) -> dict:
    scen = service.scenario("dhaka", "generated")
    work = Path(tempfile.mkdtemp())
    r = routes(variant, Path(scen["routes"]), work)
    cmd = ["sumo", "--net-file", str(scen["net"]), "--route-files", str(r), "--seed", str(SEED), "--scale", str(SCALE), "--end", str(HORIZON),
           "--lateral-resolution", "0.8", "--time-to-teleport", "300", "--no-step-log", "--no-warnings", "--ignore-route-errors"]
    traci.start(cmd, label=variant)
    c = traci.getConnection(variant)
    length = c.lane.getLength(f"{SECTION}_0") / 1000
    dens, entered, seen, edges_peak = [], 0, set(), {}
    edges = [e for e in c.edge.getIDList() if not e.startswith(":")]
    t = 0
    while t < HORIZON:
        c.simulationStep()
        t = c.simulation.getTime()
        ids = set(c.edge.getLastStepVehicleIDs(SECTION))
        entered += len(ids - seen)
        seen |= ids
        dens.append(len(ids) / length)
        if int(t) % 60 == 0:
            for e in edges:
                n = c.edge.getLastStepVehicleNumber(e)
                if n:
                    L = c.lane.getLength(f"{e}_0") / 1000
                    if L > 0.05:
                        edges_peak[e] = max(edges_peak.get(e, 0), n / L)
    vtypes = {v: {"vClass": c.vehicletype.getVehicleClass(v), "length_m": c.vehicletype.getLength(v), "minGap_m": c.vehicletype.getMinGap(v),
                  "width_m": c.vehicletype.getWidth(v), "minGapLat_m": c.vehicletype.getMinGapLat(v)} for v in c.vehicletype.getIDList() if not v.startswith("DEFAULT")}
    c.close()
    top = sorted(edges_peak.items(), key=lambda kv: -kv[1])[:5]
    return {"variant": variant, "section_density_mean_veh_km": round(statistics.fmean(dens[300:]), 2), "section_density_peak_veh_km": round(max(dens), 2),
            "section_entered_per_hour": entered, "densest_edges_peak_veh_km": [{"edge": e, "veh_km": round(v, 1)} for e, v in top], "vtypes": vtypes}


def main():
    d = pd.read_csv(ROOT / "data/recorded/dhatrax/Traffic_Analysis/combined_traffic_5min.csv")
    x = d[d.site == "INT"]
    h7 = x[x.interval_start.str[11:13] == "07"]
    cols = [k for k in d.columns if k.startswith("count_")]
    tot = x[cols].sum()
    rec = {"definition": "mean tracked vehicles in the camera zone / zone length (checked: mean_active_vehicle_count / active_length_m x 1000 reproduces density_veh_per_km)",
           "per": "road approach, all lanes", "classes": "all ten tracked classes (motorcycles, rickshaws, bicycles, CNGs included); no pedestrian class",
           "zone_length_m": round(float(h7.active_length_m.median()), 1), "density_07_veh_km": round(float(h7.density_veh_per_km.median()), 1),
           "active_vehicles_07": round(float(h7.mean_active_vehicle_count.median()), 2), "flow_07_veh_h": round(float(h7.flow_rate_veh_per_hour.median())),
           "class_share_pct": {k.replace("count_", ""): round(float(100 * v / tot.sum()), 1) for k, v in tot.items()},
           "check_formula_max_abs_diff": round(float((d.mean_active_vehicle_count / d.active_length_m * 1000 - d.density_veh_per_km).abs().max()), 6)}
    runs = [run("default"), run("tight")]
    v = runs[0]["vtypes"]
    mix = {"Car_Micro": 298, "CNG": 202, "Motor_Cycle": 269, "Rickshaw": 40, "Bus_Minibus": 37, "Pickup_Truck": 32, "Van": 8, "Ambulance": 7, "Special_Purpose": 4, "Bicycle": 3}
    space = sum(mix[k] * (v[k]["length_m"] + v[k]["minGap_m"]) for k in mix) / sum(mix.values())
    out = {"dhatrax_int": rec, "sumo_section": {"edge": SECTION, "lanes": 3, "length_m": 91.8},
           "lane_based_jam_density": {"mean_space_per_vehicle_m": round(space, 2), "jam_density_veh_km_3_lanes": round(3 * 1000 / space, 1),
                                      "note": "the generated demand's mix (900 trips) with each type's length + minGap as SUMO uses them; side by side packing not counted"},
           "runs": runs, "scale": SCALE, "seed": SEED}
    p = ROOT / "evidence/ambulance_rq2/density_gap.json"
    p.write_text(json.dumps(out, indent=1))
    p.with_suffix(".sha256").write_text(hashlib.sha256(p.read_bytes()).hexdigest() + "  density_gap.json\n")
    print(json.dumps({k: out[k] for k in ("lane_based_jam_density",)}, indent=1))
    for r in runs:
        print(r["variant"], {k: r[k] for k in ("section_density_mean_veh_km", "section_density_peak_veh_km", "section_entered_per_hour", "densest_edges_peak_veh_km")})


if __name__ == "__main__":
    main()
