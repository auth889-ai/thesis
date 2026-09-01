#!/usr/bin/env python3
"""DHAKAFLOW RUN — the one causal chain, per examiner input.

    python scripts/dhakaflow_run.py --source <video> --camera <id> \
        [--minutes 1.0] [--seeds 11,12,13] [--name <case>]

  VIDEO -> RT-DETR -> ByteTrack -> physical TrafficState        (Gate 1)
        -> SUMO twin synchronized to the observed state          (Gate 2)
        -> GWNet forecast +5/+10/+15 from preloaded history      (Gate 3)
        -> save exact t0 -> candidate futures, paired seeds      (Gates 4+8)
        -> network guards; reject congestion-movers              (Gate 5)
        -> decision (may honestly be NO ACTION) -> four-pane report

Everything is computed fresh from THIS input; the only offline ingredients
are declared (background demand profile, calibration scale, trained models).
Unregistered camera -> PERCEPTION_AVAILABLE + LOCATION_REQUIRED, no invention.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--camera", default=None)
    ap.add_argument("--minutes", type=float, default=1.0)
    ap.add_argument("--seeds", default="11,12,13")
    ap.add_argument("--name", default=None)
    a = ap.parse_args()
    name = a.name or f"run_{int(time.time())}"
    out = REPO / "artifacts" / f"run_{name}"
    out.mkdir(parents=True, exist_ok=True)
    wall = time.time()

    print(f"[1/4] perception on the given video ({a.minutes} min) …")
    from research.perception.pipeline import perceive
    state = perceive(str(a.source), a.camera, a.minutes, render_dir=out)
    (out / "traffic_state.json").write_text(json.dumps(state, indent=1))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                    "-i", str(out / "annotated.mp4"),
                    "-vf", "fps=6,scale=440:-1:flags=lanczos",
                    str(out / "annotated.gif")], check=False)
    print(f"    congested={state['congestion_detected']} "
          f"road_control={state['road_control']}")
    generic = not state["registered"]
    if generic:
        print("    UNMAPPED SITE — generic mode: decision demo runs on a "
              "DECLARED reference corridor; road-level routing for the true "
              "road still needs registration (nothing invented).")

    print("[2/4] twin synchronization (Gate-2 protocol, ~1 min) …")
    from research.twin.scenario_sync import synchronize
    registry = json.loads((REPO / "configs/cameras/registry.json").read_text())
    camera = (registry["cameras"][a.camera] if not generic else {
        "label": "UNMAPPED SITE — generic reference corridor (declared)",
        "approach_lane_count": 2,
        "sumo_site_transfer": {
            "declared": "GENERIC SITE_TRANSFER: observed state drives the "
                        "reference corridor twin; the true road is unmapped.",
            "edge_hint_camera": "karwanbazar"}})
    sync = synchronize(state, camera, seed=11, out_dir=out)
    sync["gate"] = "TWIN_SYNC(case)"
    sync["verdict"] = "PASS" if all(sync["checks"].values()) else "FAIL"
    (out / "twin_sync.json").write_text(json.dumps(sync, indent=1))
    print(f"    sync {sync['verdict']}: queue obs {sync['observed']['queue_median']} "
          f"sim {sync['sim_queue_at_t0']} · GEH {sync['geh_flow']}")
    if sync["verdict"] != "FAIL":
        pass
    else:
        print("TWIN SYNC FAILED — no reduction claim will be made.")

    print("[3/4] candidate futures from the SAME t0 (paired seeds) …")
    r = subprocess.run([sys.executable, "scripts/predictive_planner.py",
                        "--sync", str(out / "twin_sync.json"),
                        "--name", f"run_{name}", "--seeds", a.seeds],
                       cwd=REPO)
    plan = json.loads((REPO / "artifacts/planner" / f"run_{name}"
                       / "result.json").read_text())

    print("[4/4] four-pane report …")
    import numpy as np
    fcz = np.load(out / "forecast_context.npz", allow_pickle=True)
    cur = fcz["hist"][-1]
    forecast = {}
    for k in ("pred5", "pred10", "pred15"):
        if fcz[k] is not None and fcz[k].shape:
            forecast[k] = {"mean_speed_m_s": round(float(fcz[k].mean()), 2)}
    forecast["current_mean_speed_m_s"] = round(float(cur.mean()), 2)
    drop15 = None
    if "pred15" in forecast:
        drop15 = round(100 * (1 - forecast["pred15"]["mean_speed_m_s"]
                              / max(forecast["current_mean_speed_m_s"], .1)))

    verdict = {
        "case": name, "input": str(a.source), "camera": a.camera,
        "traceability": {
            "project_commit": subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                capture_output=True, text=True).stdout.strip(),
            "seeds": [int(x) for x in a.seeds.split(",")],
            "state_file": sync["state_file"],
            "planner_run": f"artifacts/planner/run_{name}/result.json"},
        "perception": {"congested": state["congestion_detected"],
                       "quality_flags": state["quality_flags"]},
        "site_mode": ("GENERIC_UNMAPPED (declared reference corridor; "
                      "register the camera for true-road routing)"
                      if generic else "REGISTERED"),
        "twin_sync": {"verdict": sync["verdict"], "geh": sync["geh_flow"]},
        "forecast": forecast, "network_speed_drop_15min_pct": drop15,
        "decision": plan["decision"],
        "branches": {c: {"stopped_veh_s": plan["branches"][c]["network"]
                         ["stopped_veh_s"],
                         "arrived": plan["branches"][c]["network"]["arrived"],
                         "label": plan["verdicts"].get(c, {}).get(
                             "label", "BASELINE")}
                     for c in plan["branches"]},
    }
    (out / "verdict.json").write_text(json.dumps(verdict, indent=1))
    subprocess.run([sys.executable, "scripts/four_pane_v2.py",
                    "--run", name], cwd=REPO, check=False)
    print(json.dumps({k: verdict[k] for k in
                      ("decision", "twin_sync", "forecast")}, indent=1))
    print(f"TOTAL WALL {time.time()-wall:.0f}s")
    print(f"-> {out}")


if __name__ == "__main__":
    main()
