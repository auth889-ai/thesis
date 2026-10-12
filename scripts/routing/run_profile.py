"""RQ2's closed loop under a RADIO profile of the thesis's V2X model instead of the 'ideal' link (2026-10-12, owner's background task).

    PYTHONPATH=.:backend python scripts/routing/run_profile.py --profile its-g5 --seeds 201 [--arms baseline,predictive_corrected_v2x]

The closed loop's channel (core/networking/v2x/channel.py) knows latency, jitter, loss and lifetime per profile; its 'ideal' profile has none.
This script registers two more profiles AT RUN TIME from core/networking/v2x/configs/network_model.yaml (each value sourced there):
its-g5 = (delay_s x hops, no jitter, 1 - delivery_ratio_in_range, lifetime_s), c-v2x likewise, and 4g = cellular_4g (latency 37.5 ms x 2 legs = 75 ms, tinyLTE; loss 1 - 0.96, Xu et al. 2017): the V2N profile. Range is not part of that channel
(the closed loop's uplink and downlink are server-to-car over infrastructure), so only latency, loss and lifetime apply; stated in the record.
Everything else is the saved RQ2 protocol (scripts/live/run_routing_quick.SETTINGS), every arm simulated now (reuse off).
Output: evidence/routing_profiles/<profile>/s<seed>/{report.json, summary.txt} and SHA256SUMS. Nothing in results/ is touched.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / "backend")]

from core.networking.v2x import channel, model  # noqa: E402

OUT = REPO / "evidence/routing_profiles"
RADIO = {"its-g5": "its_g5", "c-v2x": "c_v2x", "4g": "cellular_4g"}   # 4g (added 2026-10-12 07:00): the server <-> car (V2N) technology, two radio legs


def register_profiles() -> dict:
    """The two radio profiles, computed from the sourced parameters; returns what was registered."""
    reg = {}
    for name, tech in RADIO.items():
        p = model.parameters(tech)
        prof = (float(p["delay_s"] * p["hops"] * 1000.0), 0.0, float(round(1.0 - p["delivery_ratio_in_range"], 6)), float(p["lifetime_s"]))
        channel.PROFILES.setdefault(name, prof)
        reg[name] = {"latency_ms": prof[0], "jitter_ms": prof[1], "loss": prof[2], "ttl_s": prof[3], "from": f"network_model.yaml technologies.{tech} (delay_s x hops, delivery_ratio_in_range, lifetime_s)"}
    return reg


def settings() -> dict:
    spec = importlib.util.spec_from_file_location("rrq", REPO / "scripts/live/run_routing_quick.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return dict(m.SETTINGS)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profile", default="its-g5", choices=list(RADIO) + ["ideal"])
    ap.add_argument("--seeds", type=int, nargs="+", default=[201])
    ap.add_argument("--arms", default="baseline,predictive_corrected_v2x")
    ap.add_argument("--from-run-dir", type=Path, default=None, help="no new runs: summarise a finished run folder (results/v2x/closed_loop/<name>)")
    a = ap.parse_args(argv)
    reg = register_profiles()
    from core.simulation.closed_loop.control import closed_loop as cl
    S = settings(); S["profile"] = a.profile
    arms = tuple(a.arms.split(","))
    for seed in a.seeds:
        t0 = time.time()
        if a.from_run_dir:
            rep = {"run_dir": str(a.from_run_dir.resolve().relative_to(REPO))}
        else:
            print(f"ROUTING PROFILE RUN: {a.profile} {reg.get(a.profile, 'ideal link')} seed {seed} arms {list(arms)} (reuse off)", flush=True)
            rep = cl.run_point(seeds=[seed], arms=arms, tag=f"profile{int(t0)}", reuse=False, **S)
        d = OUT / a.profile / f"s{seed}"; d.mkdir(parents=True, exist_ok=True)
        rows = {}
        for arm in arms:
            r = json.loads((REPO / rep["run_dir"] / f"s{seed}" / arm / "arm_result.json").read_text())
            n = r.get("network") or {}
            rows[arm] = {"vehicle_hours": r["metrics"]["total_vehicle_hours_incl_never_inserted"], "arrived": r["metrics"]["arrived"], "teleports": r["metrics"]["teleports"],
                         "reroutes_applied": r.get("reroutes_applied"), "uplink": n.get("uplink"), "downlink": n.get("downlink"), "connected": n.get("connected_vehicles"), "seen": n.get("vehicles_seen"), "wall_s": r["metrics"].get("wall_s")}
        base = rows.get("baseline", {}).get("vehicle_hours")
        out = {"profile": a.profile, "profile_params": reg.get(a.profile), "seed": seed, "settings": S, "run_dir": rep["run_dir"], "arms": rows,
               "vehicle_hours_vs_baseline": {arm: (rows[arm]["vehicle_hours"] - base) if base is not None else None for arm in rows}, "real_s": round(time.time() - t0)}
        (d / "report.json").write_text(json.dumps(out, indent=1, default=str))
        lines = [f"profile {a.profile} seed {seed}: " + "; ".join(f"{arm}: veh-h {v['vehicle_hours']:.1f} ({(v['vehicle_hours'] - base):+.1f} vs baseline), reroutes {v['reroutes_applied']}, "
                 f"uplink rx/tx {(v['uplink'] or {}).get('messages_rx')}/{(v['uplink'] or {}).get('messages_tx')}, downlink rx/tx {(v['downlink'] or {}).get('messages_rx')}/{(v['downlink'] or {}).get('messages_tx')}"
                 for arm, v in rows.items() if base is not None)]
        (d / "summary.txt").write_text("\n".join(lines) + "\n")
        print("\n".join(lines), flush=True)
        files = sorted(p for p in OUT.rglob("*") if p.is_file() and p.name != "SHA256SUMS")
        (OUT / "SHA256SUMS").write_text("".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(OUT)}\n" for p in files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
