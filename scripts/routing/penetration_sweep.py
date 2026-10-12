"""Penetration sweep of the forecast-routing loop (2026-10-12, owner's addition A): the share of connected (rerouting-capable) vehicles
swept 0.1 / 0.3 / 0.5 / 0.7 / 1.0 on one seed, the loop unchanged.

    PYTHONPATH=.:backend python scripts/routing/penetration_sweep.py [--seed 201] [--profile 4g] [--shares 0.1 0.3 0.5 0.7 1.0] [--minutes 60]

Design followed: Chan, Kuncheria, Macfarlane, "Simulating the Impact of Dynamic Rerouting on Metropolitan-Scale Traffic Systems", arXiv:2207.12580
(2022), who swept the rerouting penetration rate from 0 to 100 % in the Mobiliti simulator; no code copied (theirs is Mobiliti, ours is SUMO
through core.simulation.closed_loop). Per share: the predictive arm (Graph WaveNet + correction + decision rules) over the chosen radio profile,
plus the baseline once (it does not depend on the share). Every run is simulated now (reuse off), one at a time; never alongside the test suite.
Output: evidence/routing_penetration/<profile>_s<seed>/ (summary.json, per-share report rows, two PNGs) and SHA256SUMS.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / "backend")]
OUT = REPO / "evidence/routing_penetration"
ARM = "predictive_corrected_v2x"
CHAN = "Chan, Kuncheria, Macfarlane, arXiv:2207.12580 (2022): penetration rate of dynamic rerouting swept 0-100 % (design followed; their simulator is Mobiliti, no code copied)"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=201)
    ap.add_argument("--profile", default="4g", choices=["ideal", "its-g5", "c-v2x", "4g"])
    ap.add_argument("--shares", type=float, nargs="+", default=[0.1, 0.3, 0.5, 0.7, 1.0])
    ap.add_argument("--minutes", type=int, default=60, help="simulated minutes after the fork (the saved protocol: 60)")
    a = ap.parse_args(argv)
    spec = importlib.util.spec_from_file_location("run_profile", REPO / "scripts/routing/run_profile.py"); rp = importlib.util.module_from_spec(spec); spec.loader.exec_module(rp)
    reg = rp.register_profiles(); S = rp.settings(); S["profile"] = a.profile; S["duration_s"] = int(S["fork_t0"] + a.minutes * 60)
    from core.simulation.closed_loop.control import closed_loop as cl
    d = OUT / f"{a.profile}_s{a.seed}"; d.mkdir(parents=True, exist_ok=True)
    log = open(d / "run.log", "a")

    def say(s):
        print(s, flush=True); log.write(s + "\n"); log.flush()

    say(f"PENETRATION SWEEP {datetime.now(timezone.utc).isoformat()}: seed {a.seed}, profile {a.profile} {reg.get(a.profile, 'ideal link')}, shares {a.shares}, {a.minutes} min after the fork; {CHAN}")
    rows = []
    t0 = time.time()
    rep = cl.run_point(seeds=[a.seed], arms=("baseline",), tag=f"pen{int(t0)}", reuse=False, **{**S, "penetration": a.shares[0]})
    base = json.loads((REPO / rep["run_dir"] / f"s{a.seed}" / "baseline" / "arm_result.json").read_text())
    base_vh = base["metrics"]["total_vehicle_hours_incl_never_inserted"]
    say(f"  baseline: {base_vh:.1f} vehicle-hours, arrived {base['metrics']['arrived']} ({base['metrics']['wall_s']} s)")
    for share in a.shares:
        t1 = time.time()
        rep = cl.run_point(seeds=[a.seed], arms=(ARM,), tag=f"pen{int(t1)}", reuse=False, **{**S, "penetration": share})
        r = json.loads((REPO / rep["run_dir"] / f"s{a.seed}" / ARM / "arm_result.json").read_text())
        n, m = r["network"], r["metrics"]
        row = {"share": share, "vehicle_hours": m["total_vehicle_hours_incl_never_inserted"], "vs_baseline": round(m["total_vehicle_hours_incl_never_inserted"] - base_vh, 3), "arrived": m["arrived"], "teleports": m["teleports"],
               "connected": n["connected_vehicles"], "seen": n["vehicles_seen"], "reroutes_applied": r["reroutes_applied"],
               "uplink": {"tx": n["uplink"]["messages_tx"], "rx": n["uplink"]["messages_rx"], "lost": n["uplink"]["messages_tx"] - n["uplink"]["messages_rx"]},
               "downlink": {"tx": n["downlink"]["messages_tx"], "rx": n["downlink"]["messages_rx"], "lost": n["downlink"]["messages_tx"] - n["downlink"]["messages_rx"]},
               "run_dir": rep["run_dir"], "wall_s": m["wall_s"]}
        rows.append(row)
        say(f"  share {share:.1f}: {row['vehicle_hours']:.1f} veh-h ({row['vs_baseline']:+.1f} vs baseline), connected {row['connected']}/{row['seen']}, reroutes {row['reroutes_applied']}, "
            f"uplink {row['uplink']['rx']}/{row['uplink']['tx']} (lost {row['uplink']['lost']}), downlink {row['downlink']['rx']}/{row['downlink']['tx']} (lost {row['downlink']['lost']}) [{row['wall_s']} s]")
    summary = {"generated_utc": datetime.now(timezone.utc).isoformat(), "label": "SIMULATION, LA twin, synthetic 8x peak demand on the real network; METR-LA speeds replayed as caps", "design": CHAN,
               "seed": a.seed, "profile": a.profile, "profile_params": reg.get(a.profile), "minutes_after_fork": a.minutes, "baseline_vehicle_hours": base_vh, "baseline_run_dir": rep["run_dir"], "rows": rows}
    (d / "summary.json").write_text(json.dumps(summary, indent=1))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    xs = [r["share"] * 100 for r in rows]
    fig, ax = plt.subplots(1, 2, figsize=(10, 4))
    ax[0].plot(xs, [base_vh - r["vehicle_hours"] for r in rows], marker="o", color="#1f77b4"); ax[0].axhline(0, color="grey", lw=0.8)
    ax[0].set_xlabel("connected share (%)"); ax[0].set_ylabel("vehicle-hours saved vs baseline"); ax[0].set_title(f"seed {a.seed}, {a.profile}: saving vs share", fontsize=10)
    ax[1].plot(xs, [r["reroutes_applied"] for r in rows], marker="o", color="#d62728"); ax[1].set_xlabel("connected share (%)"); ax[1].set_ylabel("reroutes applied"); ax[1].set_title("reroutes vs share", fontsize=10)
    fig.suptitle("Forecast routing, penetration sweep (design: Chan et al. 2022, arXiv:2207.12580); SIMULATION", fontsize=9); fig.tight_layout(); fig.savefig(d / "penetration_sweep.png", dpi=140)
    files = sorted(p for p in OUT.rglob("*") if p.is_file() and p.name != "SHA256SUMS")
    (OUT / "SHA256SUMS").write_text("".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(OUT)}\n" for p in files))
    say(f"done in {time.time() - t0:.0f} s -> {d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
