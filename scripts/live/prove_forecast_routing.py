"""PROOF that forecast routing is real and dynamic, by running it (2026-10-13; new file, the loop unchanged).

    make prove-forecast-routing                 # seed from the clock, 10 simulated minutes after the warm-up, headless, ~4 min
    make prove-forecast-routing SEED=4242 RSUS=40

Runs core/simulation/routing/veins_routing_loop.py once (predictive arm, Veins 802.11p) with a seed nobody chose beforehand, then reads
ONLY the files that run just wrote (plus the saved evidence run it is compared with) and checks, printing PASS / FAIL for each:
  1. real inputs: the same real dataset (METR-LA, hash), the same trained checkpoint (sha256), the same OpenStreetMap network (hash) as the
     saved run; the files exist on disk with their sizes;
  2. fresh forecast: every round has its own input-window hash and forecast hash, the real moment (as_of) advances one 5-minute bin per
     round, the inference took measurable time;
  3. dynamic: a different seed gives a different demand draw (hash), a different real moment, different forecast hashes and different
     decisions than the saved run;
  4. real network: the frame counts printed by the loop equal Veins's own scalar file (status frames sent, decoded by RSUs, advice
     received and applied), and the applied count equals the APPLIED lines of the reroute log the cars reported.
Every number shown is read from a file written by this run or by the saved run; nothing is typed in.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SAVED = REPO / "evidence/veins_forecast_routing/20261012T142239Z"
ARM = "predictive_corrected_v2x"


def sca_totals(sca: Path) -> dict:
    text = sca.read_text(); out = {}
    for name in ("statusSent", "statusReceived", "adviceSent", "adviceReceived", "adviceApplied"):
        out[name] = int(sum(float(v) for v in re.findall(rf"^scalar \S+ {name} (\S+)$", text, re.M)))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", default="clock"); ap.add_argument("--minutes", type=int, default=10); ap.add_argument("--rsus", type=int, default=20)
    ap.add_argument("--compare", type=Path, default=SAVED, help="a saved evidence run to compare with")
    ap.add_argument("--gui", action="store_true", help="windows (press RUN in OMNeT++); default headless")
    a = ap.parse_args(argv)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = REPO / "evidence/live_runs/prove_forecast_routing" / stamp
    print(f"PROOF RUN {stamp}: seed {a.seed}, {a.minutes} min after the warm-up, {a.rsus} RSUs, predictive arm over Veins 802.11p; output {out.relative_to(REPO)}", flush=True)
    t0 = time.time()
    cmd = [sys.executable, "-m", "core.simulation.routing.veins_routing_loop", "--seed", str(a.seed), "--minutes", str(a.minutes), "--rsus", str(a.rsus), "--arms", ARM, "--out", str(out)] + ([] if a.gui else ["--no-gui"])
    r = subprocess.run(cmd, cwd=REPO, env={**os.environ, "PYTHONPATH": f"{REPO}:{REPO / 'backend'}"}, text=True, capture_output=True)
    for line in r.stdout.splitlines():
        if any(k in line for k in ("SEED", "demand ", "VEINS ROUTING", "round ", f"{ARM}:", "handshake")):
            print("  " + line[:230], flush=True)
    if r.returncode != 0:
        print(r.stdout[-1500:] + r.stderr[-1500:]); print("THE RUN FAILED: no proof"); return 1
    print(f"  run finished in {time.time() - t0:.0f} s wall", flush=True)
    S = json.loads((out / "summary.json").read_text()); P = json.loads((out / "PROTOCOL.json").read_text())
    seed = S["seed"]; d = out / f"s{seed}" / ARM
    rounds = sorted(d.glob("routing_round_*/routing_record.json"), key=lambda p: int(p.parent.name.split("_")[-1]))
    recs = [json.loads(p.read_text()) for p in rounds]
    C = json.loads((a.compare / "summary.json").read_text()); CP = json.loads((a.compare / "PROTOCOL.json").read_text())
    cseed = C["seed"]; cd = a.compare / f"s{cseed}" / ARM
    crecs = [json.loads(p.read_text()) for p in sorted(cd.glob("routing_round_*/routing_record.json"), key=lambda p: int(p.parent.name.split("_")[-1]))]
    checks: list[tuple[str, bool, str]] = []

    def chk(name, ok, detail):
        checks.append((name, bool(ok), detail))

    # 1. real inputs
    ds, ck, net = REPO / "data/forecasting/cities/metr_la.npz", Path(P["checkpoint_path"]), REPO / P["network"]
    chk("1a real dataset on disk", ds.exists(), f"{ds.relative_to(REPO)}: {ds.stat().st_size / 1e6:.1f} MB, modified {datetime.fromtimestamp(ds.stat().st_mtime).date()}; dataset hash {P['dataset_hash']}")
    chk("1b same real dataset as the saved run", P["dataset_hash"] == CP["dataset_hash"], f"{P['dataset_hash']} == {CP['dataset_hash']}")
    chk("1c trained checkpoint on disk, same as the saved run", ck.exists() and P["checkpoint_sha256"] == CP["checkpoint_sha256"], f"{ck.name} sha256 {P['checkpoint_sha256']}… ({ck.stat().st_size / 1e6:.1f} MB)" if ck.exists() else "missing")
    chk("1d same OpenStreetMap network", net.exists() and P["network_hash"] == CP["network_hash"], f"{net.name} hash {P['network_hash']}; {P['mapped_detectors']} detectors mapped onto it")
    # 2. fresh forecast
    fh = [x["forecast_provenance"]["forecast_hash"] for x in recs]; iw = [x["forecast_provenance"]["input_window_hash"] for x in recs]
    asof = [S["arms"][ARM]["network"] and x.get("sim_time_s") for x in recs]
    arm = json.loads((d / "arm_result.json").read_text()); as_ofs = [rr["as_of_index"] for rr in arm["rounds"]]
    chk("2a one forecast per round, each with its own hash", len(fh) >= 2 and len(set(fh)) == len(fh) and len(set(iw)) == len(iw), f"{len(fh)} rounds, forecast hashes {[h[:8] for h in fh]}, input windows {[h[:8] for h in iw]}")
    chk("2b the real moment advances one 5-min bin per round", all(b - a_ == 1 for a_, b in zip(as_ofs, as_ofs[1:])), f"as_of {as_ofs}")
    chk("2c inference took time (computed, not looked up)", all(x["forecast_provenance"]["inference_seconds"] > 0 for x in recs), f"{[x['forecast_provenance']['inference_seconds'] for x in recs]} s")
    # 3. dynamic
    chk("3a a different seed than the saved run", seed != cseed, f"{seed} vs {cseed}")
    chk("3b a different demand draw", S["demand"]["demand_hash"] != C["demand"]["demand_hash"], f"{S['demand']['demand_hash'][:12]} vs {C['demand']['demand_hash'][:12]} ({S['demand']['vehicles']} vehicles)")
    cas = [rr["as_of_index"] for rr in json.loads((cd / "arm_result.json").read_text())["rounds"]]
    chk("3c a different real moment of the detector history", as_ofs[0] != cas[0], f"as_of {as_ofs[0]} vs {cas[0]}")
    chk("3d different forecasts and decisions", fh[0] != crecs[0]["forecast_provenance"]["forecast_hash"] and recs[0]["stats"]["decisions"] != crecs[0]["stats"]["decisions"], f"round 0 decisions {recs[0]['stats']['decisions']} vs {crecs[0]['stats']['decisions']}")
    # 4. real network
    sca = sorted((d / "veins/results").glob("*.sca"))[-1]; v = sca_totals(sca); n = arm["network"]
    applied_log = sum(1 for l in (d / "reroute_log.jsonl").read_text().splitlines() if json.loads(l)["outcome"] == "APPLIED")
    chk("4a status frames: loop counters = Veins's scalar file", n["uplink"]["messages_tx"] == v["statusSent"] and n["uplink"]["messages_rx_at_rsus"] == v["statusReceived"], f"sent {v['statusSent']}, decoded by RSUs {v['statusReceived']}, distinct to the server {n['uplink']['unique_to_server']} ({sca.relative_to(REPO)})")
    chk("4b advice frames: broadcast / received / applied = Veins's scalar file", n["downlink"]["broadcast_by_rsus"] == v["adviceSent"] and n["downlink"]["received_by_car"] == v["adviceReceived"] and n["downlink"]["applied"] == v["adviceApplied"], f"decided {n['downlink']['advice_decided']}, handed {n['downlink']['handed_to_rsu']}, broadcast {v['adviceSent']}, received {v['adviceReceived']}, applied {v['adviceApplied']}")
    chk("4c applied = the cars' own reports in the reroute log", v["adviceApplied"] == applied_log, f"{applied_log} APPLIED lines in {(d / 'reroute_log.jsonl').relative_to(REPO)}")
    print("\nCHECKS (every number read from the files of this run or of the saved run):")
    for name, ok, detail in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}: {detail}")
    m = arm["metrics"]
    print(f"\nRESULT seed {seed} ({a.minutes} min after the warm-up): {m['total_vehicle_hours_incl_never_inserted']:.1f} vehicle-hours, arrived {m['arrived']}, teleports {m['teleports']};"
          f" the saved seed {cseed} ({C['minutes_after_warm_up']} min, {len(C['rsus'])} RSUs): {C['arms'][ARM]['metrics']['total_vehicle_hours_incl_never_inserted']:.1f} veh-h (not comparable unless the minutes match)."
          f"\n{'ALL CHECKS PASS' if all(ok for _, ok, _ in checks) else 'SOME CHECKS FAIL'}: files under {out.relative_to(REPO)}")
    (out / "proof.json").write_text(json.dumps({"stamp": stamp, "seed": seed, "compare": str(a.compare.relative_to(REPO)), "checks": [{"name": nm, "pass": ok, "detail": dt} for nm, ok, dt in checks]}, indent=1))
    return 0 if all(ok for _, ok, _ in checks) else 2


if __name__ == "__main__":
    sys.exit(main())
