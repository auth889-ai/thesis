"""make sweep-sos (step Q1, 2026-10-11): the car-to-car crash SOS run (scripts/live/run_sos_v2v.py, simulate()) over seeds, app shares and
crash times, each warning run paired with the same seed's run without any warning, computed now on the Dhaka corridor.

    PYTHONPATH=.:backend python scripts/live/sweep_sos.py [--seeds 11 12 13 14 15] [--shares 0.25 0.5 0.75 1.0] [--crash-at 600 900]
                                                          [--tech its_g5] [--quick] [--workers 4]

Per cell (seed, share, crash time): cars warned, cars rerouted, the cars that were heading for the crash and how many of them arrived
within 600 s with and without the warning, their mean time from the crash to arrival with and without (headline: over all of them, a car
not arrived counted at 600 s; also over arrived cars only), and the in-range delivery ratio.
`--quick` = seeds 11 and 12, crash at 600 s only (8 warning runs + 2 twins). Outputs: evidence/sos/sweep/sweep[_quick].{csv,json,png}
(sha256 printed). There is no thesis number for car-to-car SOS: the only check is that the cell of the saved live run
(evidence/live_runs/sos_v2v/last_run.json, seed 11, 50 %, crash at 600 s) comes out the same. The SOS rule itself is re-run on the thesis
traces first and must reproduce evidence/sos/results.json. Saved results are never touched: the runs go to evidence/sos/sweep/runs/.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / "backend"), str(REPO / "scripts/live")]

SHARES = (0.25, 0.5, 0.75, 1.0)
CRASH_AT = (600.0, 900.0)
AFTER = 600.0
OUT = REPO / "evidence/sos/sweep"
SAVED = REPO / "evidence/live_runs/sos_v2v/last_run.json"
PAIR_KEYS = ("affected", "affected_arrived", "affected_mean_s_to_arrive", "warned", "rerouted")


def one(seed: int, share: float, crash_at: float, tech: str, warn: bool) -> dict:
    import run_sos_v2v as rs
    rs.OUT = OUT / "runs" / f"crash{int(crash_at)}"                      # simulate() names its folder by warn/tech/share/seed/level only
    a = SimpleNamespace(tech=tech, share=share, seed=seed, level="dhaka", crash_at=crash_at, after=AFTER, speed=8.0, no_gui=True, gui_colours=False, collide=False)
    t0 = time.time()
    r = rs.simulate(a, warn=warn, gui=False)
    m = r["messages"]
    inr = m["delivered"] + m["lost"]
    cens = censored_mean(r["affected"], r["affected_arrived"], r["affected_mean_s_to_arrive"])
    return {"seed": seed, "share": share if warn else 0.0, "crash_at": crash_at, "tech": tech if warn else "", "warn": warn, "crashed": r["crashed"],
            "affected": r["affected"], "affected_arrived": r["affected_arrived"], "affected_mean_s_to_arrive": r["affected_mean_s_to_arrive"], "censored_mean_s": cens,
            "warned": r["warned"], "rerouted": r["rerouted"], "no_alternative": r["no_alternative"], "half_warned_by_s": r["half_warned_by_s"],
            "teleports": r["teleports"], "broadcasts": m["broadcasts"], "sent": m["sent"], "delivered": m["delivered"], "lost": m["lost"],
            "delivery_in_range": round(m["delivered"] / inr, 3) if inr else None, "real_s": round(time.time() - t0, 1)}


def censored_mean(affected: int, arrived: int, mean_arrived: float | None) -> float | None:
    """Mean time from the crash over ALL the cars that were heading for it, a car that had not arrived counted at the horizon (AFTER s):
    the mean over arrived cars alone falls when fewer cars get through, so it would reward a warning that strands cars."""
    if not affected:
        return None
    return round(((arrived * (mean_arrived or 0.0)) + (affected - arrived) * AFTER) / affected, 1)


def pair(rows: list[dict]) -> list[dict]:
    """Attach each warning row's twin (same seed and crash time, no warning): arrivals gained and mean seconds saved."""
    twin = {(r["seed"], r["crash_at"]): r for r in rows if not r["warn"]}
    out = []
    for r in rows:
        if not r["warn"]:
            continue
        n = twin.get((r["seed"], r["crash_at"]))
        r = dict(r)
        r["arrived_without"] = n["affected_arrived"] if n else None
        r["mean_s_without"] = n["affected_mean_s_to_arrive"] if n else None
        r["arrivals_gained"] = None if n is None else r["affected_arrived"] - n["affected_arrived"]
        r["saved_s"] = None if n is None or r["affected_mean_s_to_arrive"] is None or n["affected_mean_s_to_arrive"] is None else round(n["affected_mean_s_to_arrive"] - r["affected_mean_s_to_arrive"], 1)
        r["censored_without"] = n["censored_mean_s"] if n else None
        r["saved_censored_s"] = None if n is None or r["censored_mean_s"] is None or n["censored_mean_s"] is None else round(n["censored_mean_s"] - r["censored_mean_s"], 1)
        r["same_crash"] = None if n is None else r["crashed"] == n["crashed"]
        out.append(r)
    return out


def summary(paired: list[dict]) -> list[dict]:
    out = []
    for sh in sorted({r["share"] for r in paired}):
        for ca in sorted({r["crash_at"] for r in paired}):
            rs_ = [r for r in paired if r["share"] == sh and r["crash_at"] == ca]
            sv = [r["saved_s"] for r in rs_ if r["saved_s"] is not None]
            sc = [r["saved_censored_s"] for r in rs_ if r["saved_censored_s"] is not None]
            out.append({"share": sh, "crash_at": ca, "runs": len(rs_), "saved_censored_s_median": round(statistics.median(sc), 1) if sc else None,
                        "saved_censored_s_mean": round(statistics.fmean(sc), 1) if sc else None, "censored_slower_runs": sum(x < 0 for x in sc), "warned_mean": round(statistics.fmean(r["warned"] for r in rs_), 1) if rs_ else None,
                        "rerouted_mean": round(statistics.fmean(r["rerouted"] for r in rs_), 1) if rs_ else None,
                        "arrivals_gained_mean": round(statistics.fmean(r["arrivals_gained"] for r in rs_ if r["arrivals_gained"] is not None), 2) if rs_ else None,
                        "saved_s_median": round(statistics.median(sv), 1) if sv else None, "saved_s_mean": round(statistics.fmean(sv), 1) if sv else None,
                        "saved_s_min": min(sv) if sv else None, "saved_s_max": max(sv) if sv else None, "slower_runs": sum(x < 0 for x in sv),
                        "delivery_in_range_mean": round(statistics.fmean(r["delivery_in_range"] for r in rs_ if r["delivery_in_range"] is not None), 3) if any(r["delivery_in_range"] is not None for r in rs_) else None})
    return out


def saved_check(paired: list[dict]) -> str:
    """The one cell that was run before (the saved live run) must come out the same; everything else is new."""
    if not SAVED.exists():
        return "no saved live run to compare with"
    s = json.loads(SAVED.read_text())
    a, w, n = s["args"], s["with_warning"], s["without_warning"]
    if a.get("collide") or a.get("level") != "dhaka":
        return f"saved live run has other settings ({a}); not comparable"
    cell = [r for r in paired if r["seed"] == a["seed"] and r["share"] == a["share"] and r["crash_at"] == a["crash_at"] and r["tech"] == a["tech"]]
    if not cell:
        return f"saved live run's cell (seed {a['seed']}, {int(a['share'] * 100)} %, crash at {a['crash_at']:g} s, {a['tech']}) not in this sweep"
    r = cell[0]
    diffs = {k: (r[k], w[k]) for k in PAIR_KEYS if r[k] != w[k]}
    diffs.update({f"{k}_without": (r["arrived_without" if k == "affected_arrived" else "mean_s_without"], n[k]) for k in ("affected_arrived", "affected_mean_s_to_arrive")
                  if r["arrived_without" if k == "affected_arrived" else "mean_s_without"] != n[k]})
    return "REPRODUCED the saved live run (seed %d, %d %%, crash at %g s)" % (a["seed"], a["share"] * 100, a["crash_at"]) if not diffs else f"DIFFERENT from the saved live run: {diffs}"


def plot(paired: list[dict], summ: list[dict], path: Path, seeds: list[int]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    for ca in sorted({r["crash_at"] for r in paired}):
        for ax, key, lab in ((axes[0], "saved_censored_s", "seconds saved (all cars heading for the crash;\nnot arrived = 600 s)"), (axes[1], "arrivals_gained", "extra cars arrived within 600 s")):
            for sd in seeds:
                pts = [(r["share"] * 100, r[key]) for r in paired if r["seed"] == sd and r["crash_at"] == ca and r[key] is not None]
                if pts:
                    ax.plot(*zip(*pts), "o", alpha=0.3, color="C0" if ca == 600 else "C1")
            med = [(s["share"] * 100, s["saved_censored_s_median" if key == "saved_censored_s" else "arrivals_gained_mean"]) for s in summ if s["crash_at"] == ca and s["saved_censored_s_median" if key == "saved_censored_s" else "arrivals_gained_mean"] is not None]
            if med:
                ax.plot(*zip(*med), "-", lw=2.5, color="C0" if ca == 600 else "C1", label=f"crash at {int(ca)} s ({'median' if key == 'saved_censored_s' else 'mean'})")
            ax.axhline(0, color="grey", lw=0.8); ax.set_xlabel("cars with the app, %"); ax.set_ylabel(lab); ax.legend(fontsize=8)
    fig.suptitle(f"SIMULATION, no thesis number: crash SOS car to car, Dhaka density, seeds {seeds}, computed {datetime.now().strftime('%Y-%m-%d %H:%M')}", fontsize=9)
    fig.tight_layout(); fig.savefig(path, dpi=130)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", type=int, nargs="+", default=[11, 12, 13, 14, 15])
    ap.add_argument("--shares", type=float, nargs="+", default=list(SHARES))
    ap.add_argument("--crash-at", type=float, nargs="+", default=list(CRASH_AT))
    ap.add_argument("--tech", default="its_g5", choices=["its_g5", "c_v2x", "cellular_4g"])
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    seeds, crash = (a.seeds[:2], [a.crash_at[0]]) if a.quick else (a.seeds, a.crash_at)
    import run_sos_v2v as rs
    ok, lines = rs.rule_check()
    jobs = [(sd, sh, ca, a.tech, True) for sd in seeds for ca in crash for sh in a.shares] + [(sd, 0.0, ca, a.tech, False) for sd in seeds for ca in crash]
    print(f"SWEEP (crash SOS car to car, Dhaka density, SIMULATION, no thesis number): {a.tech}, shares {[int(s * 100) for s in a.shares]} %, crash at {[int(c) for c in crash]} s,"
          f" seeds {seeds}: {len(jobs)} runs computed now ({len(seeds) * len(crash)} of them without any warning), {a.workers} at a time", flush=True)
    print("  SOS rule on the thesis traces: " + ("REPRODUCED (evidence/sos/results.json)" if ok else "DIFFERENT"), flush=True)
    t0 = time.time()
    with ProcessPoolExecutor(a.workers) as ex:
        rows = list(ex.map(one, *zip(*jobs)))
    paired = pair(rows)
    summ = summary(paired)
    check = saved_check(paired)
    OUT.mkdir(parents=True, exist_ok=True)
    tag = "_quick" if a.quick else ""
    cols = ["seed", "share", "crash_at", "tech", "crashed", "same_crash", "affected", "affected_arrived", "arrived_without", "arrivals_gained", "affected_mean_s_to_arrive", "mean_s_without", "saved_s", "censored_mean_s", "censored_without", "saved_censored_s",
            "warned", "rerouted", "no_alternative", "half_warned_by_s", "teleports", "broadcasts", "sent", "delivered", "lost", "delivery_in_range", "real_s"]
    with (OUT / f"sweep{tag}.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows({k: r.get(k) for k in cols} for r in paired)
    plot(paired, summ, OUT / f"sweep{tag}.png", seeds)
    body = {"what": "crash SOS car to car over app share, crash time and seed; each warning run paired with the same seed's run without any warning", "label": "SIMULATION",
            "thesis_number": None, "note": "no thesis number exists for car-to-car SOS; these figures are new", "rule_reproduced": ok, "saved_live_run_check": check,
            "tech": a.tech, "seeds": seeds, "shares": a.shares, "crash_at": crash, "after_s": AFTER, "runs": len(rows), "summary": summ, "rows": paired,
            "twins": [r for r in rows if not r["warn"]], "real_s": round(time.time() - t0), "csv": f"evidence/sos/sweep/sweep{tag}.csv", "png": f"evidence/sos/sweep/sweep{tag}.png",
            "when": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    p = OUT / f"sweep{tag}.json"
    p.write_text(json.dumps(body, indent=1))
    for s in summ:
        print(f"  share {int(s['share'] * 100):3d} %, crash at {int(s['crash_at'])} s: warned {s['warned_mean']}, rerouted {s['rerouted_mean']}, extra arrivals {s['arrivals_gained_mean']},"
              f" saved (all cars, not arrived = 600 s) median {s['saved_censored_s_median']} s, mean {s['saved_censored_s_mean']}, slower {s['censored_slower_runs']} of {s['runs']};"
              f" over arrived cars only: median {s['saved_s_median']} s (min {s['saved_s_min']}, max {s['saved_s_max']}); delivery in range {s['delivery_in_range_mean']}")
    print(f"  CHECK: {check}; {body['real_s']} s in all. THESIS CHECK: the SOS rule {'REPRODUCED' if ok else 'DIFFERENT'}; the car-to-car figures have no thesis number.")
    print(f"  {body['csv']}, {body['png']}, sha256 {hashlib.sha256(p.read_bytes()).hexdigest()} {p.relative_to(REPO)}")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
