"""make sweep-mesh (step P, 2026-10-11): The ONE's built-in routers (Epidemic, Spray-and-Wait, PRoPHET, MaxProp) on the thesis mesh scenario,
over a sweep of the phone count (17, 50, 100, 200) and seeds: delivery ratio and mean latency per router, computed now in The ONE 1.6.0
(GPL-3.0, batch mode; `third_party/the-one`). These are The ONE's numbers; the thesis's RQ4 numbers come from PONS (make run-mesh).

    python scripts/live/sweep_mesh.py [--counts 17 50 100 200] [--seeds 1 2 3] [--routers epidemic spray_and_wait prophet maxprop] [--range 10] [--quick]

Phones: the study's SUMO run (research/mesh_pons/work/dhaka.fcd.xml), window 900-1200 s, the vehicles ranked by how many of the 300
seconds they are present (17 are present throughout: the thesis's set; 50 are present >= 236 s, 100 >= 175 s, 200 >= 77 s). A phone that is
not in the window at a second is parked on a line outside the map, 50 m apart, out of every radio's range ("switched off"): it then
neither moves nor talks. Messages are sent and received only among the 17 full-window phones at every count (the added phones relay),
so the counts compare the same traffic; the seed changes the message set (The ONE seeds its generator from the message prefix).
Radio, message rate, size and lifetime as in the study's config. Outputs: evidence/mesh/routers/sweep.{csv,json,png}.
`--range-sweep`: Epidemic, 17 and 100 phones, radio 10 / 30 / 50 / 100 m, 3 seeds -> evidence/mesh/range/ (the contacts-bottleneck check).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import statistics
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import yaml

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/live"))
import run_mesh_one as one  # noqa: E402

OUT = REPO / "evidence/mesh/routers"
ROUTER = {**one.ROUTER, "maxprop": "MaxPropRouter"}
WINDOW = (900.0, 1200.0)
PARK_GAP_M = 50.0
CORE_PHONES = 17                        # the thesis's full-window phones: the only senders and receivers at every count; added phones relay


def window_positions(fcd: Path = one.MESH / "work/dhaka.fcd.xml") -> tuple[list[float], dict[str, dict[float, tuple[float, float]]]]:
    """Every vehicle's position per second inside the study window, read from the full FCD once."""
    pos: dict[str, dict[float, tuple[float, float]]] = {}
    times: list[float] = []
    for _, el in ET.iterparse(str(fcd)):
        if el.tag == "timestep":
            t = float(el.get("time"))
            if WINDOW[0] <= t < WINDOW[1]:
                times.append(t)
                for v in el:
                    pos.setdefault(v.get("id"), {})[t] = (float(v.get("x")), float(v.get("y")))
            el.clear()
    return times, pos


def rank(pos: dict) -> list[str]:
    """Vehicles by presence (most seconds first), ties by id: the first 17 are the thesis's full-window set."""
    return sorted(pos, key=lambda v: (-len(pos[v]), int(v[3:]) if v[3:].isdigit() else 0, v))


def movement(out: Path, times: list[float], pos: dict, ids: list[str]) -> dict:
    """ExternalMovement lines for `ids`; absent phones parked outside the map, PARK_GAP_M apart. Returns the world size."""
    xs = [p[0] for v in ids for p in pos[v].values()]
    ys = [p[1] for v in ids for p in pos[v].values()]
    x0, y1 = min(xs), max(ys)
    width, height = max(xs) - x0, y1 - min(ys)
    park_y = height + 200.0
    lines = [f"{times[0]} {times[-1]} 0 {max(width, PARK_GAP_M * len(ids)):.2f} 0 {park_y:.2f} 0 0"]
    for t in times:
        for i, v in enumerate(ids):
            if t in pos[v]:
                x, y = pos[v][t]
                lines.append(f"{t} {i} {x - x0:.2f} {y1 - y:.2f}")
            else:
                lines.append(f"{t} {i} {PARK_GAP_M * i:.2f} {park_y:.2f}")
    out.write_text("\n".join(lines) + "\n")
    return {"width_m": round(max(width, PARK_GAP_M * len(ids))), "height_m": round(park_y), "present_full_window": sum(len(pos[v]) == len(times) for v in ids),
            "presence_s_min": min(len(pos[v]) for v in ids)}


def run_one(n: int, router: str, seed: int, rng: float, exp: dict, times, pos, ranked, work: Path) -> dict:
    ids = ranked[:n]
    mv = work / f"movement_n{n}.txt"
    if not mv.exists():
        info = movement(mv, times, pos, ids)
        (work / f"movement_n{n}.json").write_text(json.dumps(info))
    info = json.loads((work / f"movement_n{n}.json").read_text())
    a = SimpleNamespace(protocol=router, range=rng, seed=seed)
    st = work / f"n{n}_{router}_s{seed}.settings.txt"
    rep = work / "reports"
    rep.mkdir(exist_ok=True)
    one.ROUTER[router] = ROUTER[router]                                # the GUI runner's table, extended with MaxProp for this sweep
    one.settings(st, mv, n, a, exp, rep)
    core = min(n, CORE_PHONES)
    text = (st.read_text().replace(f"Scenario.name = dhaka_{router}_r{rng:g}_s{seed}", f"Scenario.name = dhaka_n{n}_{router}_r{rng:g}_s{seed}")
            .replace(f"Events1.hosts = 0,{n}\n", f"Events1.hosts = 0,{core}\nEvents1.tohosts = 0,{core}\n")    # the same senders/receivers at every count: extra phones only relay
            .replace("Events1.prefix = M\n", f"Events1.prefix = M{seed}\n"))                                # The ONE seeds the generator from the prefix (input/MessageEventGenerator.java:94)
    st.write_text(text)
    t0 = time.time()
    subprocess.run(["java", "-Xmx2G", "-cp", ".:lib/*", "core.DTNSim", "-b", "1", str(st)], cwd=one.ONE, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    f = rep / f"dhaka_n{n}_{router}_r{rng:g}_s{seed}_MessageStatsReport.txt"
    stats = dict(re.findall(r"^(\w+): (\S+)$", f.read_text(), re.M)) if f.exists() else {}
    num = lambda k: (None if stats.get(k) in (None, "NaN") else float(stats[k]))  # noqa: E731
    return {"phones": n, "router": router, "seed": seed, "created": num("created"), "delivered": num("delivered"), "delivery_ratio": num("delivery_prob"),
            "latency_avg_s": num("latency_avg"), "overhead_ratio": num("overhead_ratio"), "hopcount_avg": num("hopcount_avg"), "present_full_window": info["present_full_window"],
            "presence_s_min": info["presence_s_min"], "real_s": round(time.time() - t0, 1), "report": str(f.relative_to(REPO)) if f.exists() else None}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--counts", type=int, nargs="+", default=[17, 50, 100, 200])
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--routers", nargs="+", default=list(ROUTER), choices=list(ROUTER))
    ap.add_argument("--range", type=float, default=10.0)
    ap.add_argument("--quick", action="store_true", help="seed 1 only")
    ap.add_argument("--range-sweep", action="store_true", help="radio range 10/30/50/100 m x phones 17/100, Epidemic (P's upper bound), seeds 1-3 -> evidence/mesh/range/")
    a = ap.parse_args()
    if a.range_sweep:
        return range_sweep(a)
    if not (one.ONE / "core/DTNSim.class").exists():
        print("STOP: The ONE is not built here: third_party/the-one/fetch.sh"); return 1
    seeds = a.seeds[:1] if a.quick else a.seeds
    exp = yaml.safe_load((one.MESH / "configs/dhaka.yaml").read_text())
    work = OUT / "work"
    work.mkdir(parents=True, exist_ok=True)
    times, pos = window_positions()
    ranked = rank(pos)
    print(f"SWEEP (RQ4 second view, The ONE 1.6.0, SIMULATION): routers {a.routers}, phones {a.counts} of {len(ranked)} seen in the window, seeds {seeds}, radio {a.range:g} m;"
          f" {len(a.routers) * len(a.counts) * len(seeds)} runs computed now.", flush=True)
    t0 = time.time()
    rows = []
    for n in a.counts:
        for r in a.routers:
            for sd in seeds:
                row = run_one(n, r, sd, a.range, exp, times, pos, ranked, work)
                rows.append(row)
                print(f"  phones {n:3d} {r:15s} seed {sd}: delivered {row['delivered']} of {row['created']} (ratio {row['delivery_ratio']}), latency {row['latency_avg_s']} s, overhead {row['overhead_ratio']}  [{row['real_s']} s]", flush=True)
    cols = ["phones", "router", "seed", "created", "delivered", "delivery_ratio", "latency_avg_s", "overhead_ratio", "hopcount_avg", "present_full_window", "presence_s_min", "real_s", "report"]
    with (OUT / "sweep.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows({k: r[k] for k in cols} for r in rows)
    summary = {}
    for r in a.routers:
        summary[r] = {}
        for n in a.counts:
            rr = [x for x in rows if x["router"] == r and x["phones"] == n]
            dr = [x["delivery_ratio"] for x in rr if x["delivery_ratio"] is not None]
            la = [x["latency_avg_s"] for x in rr if x["latency_avg_s"] is not None]
            summary[r][n] = {"delivery_ratio_mean": round(statistics.fmean(dr), 4) if dr else None, "delivery_ratio_sd": round(statistics.stdev(dr), 4) if len(dr) > 1 else None,
                             "latency_avg_s_mean": round(statistics.fmean(la), 1) if la else None, "seeds": len(rr)}
    body = {"what": "The ONE's routers on the thesis mesh scenario over the phone count; The ONE's own numbers (second view), not the thesis's PONS result", "label": "SIMULATION",
            "simulator": "The ONE 1.6.0 (GPL-3.0), batch", "routers": {r: ROUTER[r] for r in a.routers}, "counts": a.counts, "seeds": seeds, "range_m": a.range, "window_s": list(WINDOW),
            "vehicles_in_window": len(ranked), "messages": exp["messages"], "parking": f"absent phones parked outside the map {PARK_GAP_M:g} m apart (out of range)", "senders_receivers": f"phones 0-{CORE_PHONES - 1} (the full-window set) at every count; added phones relay only",
            "summary": summary, "rows": rows, "real_s": round(time.time() - t0), "when": datetime.now(timezone.utc).isoformat(timespec="seconds"), "csv": "evidence/mesh/routers/sweep.csv", "png": "evidence/mesh/routers/sweep.png"}
    (OUT / "sweep.json").write_text(json.dumps(body, indent=1))
    plot(body, OUT / "sweep.png")
    print(f"  {'router':16}" + "".join(f"{'n=' + str(n):>18}" for n in a.counts) + "   (delivery ratio mean / latency s)")
    for r in a.routers:
        print(f"  {r:16}" + "".join(f"{str(summary[r][n]['delivery_ratio_mean']) + ' / ' + str(summary[r][n]['latency_avg_s_mean']):>18}" for n in a.counts))
    print(f"  THESIS CHECK: none applies: these are The ONE's numbers; the thesis's RQ4 result (PONS, 17 phones) stays results/networking/mesh/dhaka/summary.json. {body['real_s']} s in all")
    print(f"  sha256 {hashlib.sha256((OUT / 'sweep.json').read_bytes()).hexdigest()} evidence/mesh/routers/sweep.json; {body['png']}")
    return 0


RANGES_M = (10.0, 30.0, 50.0, 100.0)                       # Bluetooth-class to Wi-Fi Direct-class radio
RANGE_OUT = REPO / "evidence/mesh/range"


def range_sweep(a) -> int:
    """Delivery ratio against the radio range (owner's check, 2026-10-11): if delivery rises with range, contacts are the bottleneck."""
    seeds = a.seeds[:1] if a.quick else a.seeds
    counts = [n for n in (17, 100) if n in a.counts] or [17, 100]
    router = "epidemic"
    exp = yaml.safe_load((one.MESH / "configs/dhaka.yaml").read_text())
    work = RANGE_OUT / "work"
    work.mkdir(parents=True, exist_ok=True)
    times, pos = window_positions()
    ranked = rank(pos)
    print(f"RANGE SWEEP (RQ4 second view, The ONE 1.6.0, SIMULATION): {ROUTER[router]}, phones {counts}, radio {[int(r) for r in RANGES_M]} m, seeds {seeds}: {len(counts) * len(RANGES_M) * len(seeds)} runs computed now.", flush=True)
    t0 = time.time()
    rows = []
    for n in counts:
        for rng in RANGES_M:
            for sd in seeds:
                row = run_one(n, router, sd, rng, exp, times, pos, ranked, work)
                row["range_m"] = rng
                rows.append(row)
                print(f"  phones {n:3d} range {rng:5.0f} m seed {sd}: delivered {row['delivered']} of {row['created']} (ratio {row['delivery_ratio']}), latency {row['latency_avg_s']} s, hops {row['hopcount_avg']}  [{row['real_s']} s]", flush=True)
    cols = ["phones", "range_m", "router", "seed", "created", "delivered", "delivery_ratio", "latency_avg_s", "overhead_ratio", "hopcount_avg", "real_s", "report"]
    with (RANGE_OUT / "range.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows({k: r[k] for k in cols} for r in rows)
    summary = {}
    for n in counts:
        summary[n] = {}
        for rng in RANGES_M:
            rr = [x for x in rows if x["phones"] == n and x["range_m"] == rng]
            dr = [x["delivery_ratio"] for x in rr if x["delivery_ratio"] is not None]
            la = [x["latency_avg_s"] for x in rr if x["latency_avg_s"] is not None]
            hp = [x["hopcount_avg"] for x in rr if x["hopcount_avg"] is not None]
            summary[n][int(rng)] = {"delivery_ratio_mean": round(statistics.fmean(dr), 4) if dr else None, "delivery_ratio_sd": round(statistics.stdev(dr), 4) if len(dr) > 1 else None,
                                    "latency_avg_s_mean": round(statistics.fmean(la), 1) if la else None, "hopcount_avg_mean": round(statistics.fmean(hp), 2) if hp else None, "seeds": len(rr)}
    rises = all(summary[n][100]["delivery_ratio_mean"] > summary[n][10]["delivery_ratio_mean"] for n in counts if summary[n][100]["delivery_ratio_mean"] is not None and summary[n][10]["delivery_ratio_mean"] is not None)
    body = {"what": "Delivery ratio against the radio range in The ONE (Epidemic, the upper bound of make sweep-mesh), 17 and 100 phones; a check that contacts are the bottleneck", "label": "SIMULATION",
            "simulator": "The ONE 1.6.0 (GPL-3.0), batch", "router": ROUTER[router], "counts": counts, "ranges_m": list(RANGES_M), "seeds": seeds, "messages": exp["messages"],
            "senders_receivers": f"phones 0-{CORE_PHONES - 1} at every count; added phones relay only", "summary": summary, "delivery_rises_with_range": rises, "rows": rows,
            "real_s": round(time.time() - t0), "when": datetime.now(timezone.utc).isoformat(timespec="seconds"), "csv": "evidence/mesh/range/range.csv", "png": "evidence/mesh/range/range.png"}
    (RANGE_OUT / "range.json").write_text(json.dumps(body, indent=1))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    for n in counts:
        xs = [int(r) for r in RANGES_M]
        axes[0].errorbar(xs, [summary[n][x]["delivery_ratio_mean"] for x in xs], yerr=[summary[n][x]["delivery_ratio_sd"] or 0 for x in xs], fmt="o-", capsize=3, label=f"{n} phones")
        axes[1].plot(xs, [summary[n][x]["latency_avg_s_mean"] for x in xs], "o-", label=f"{n} phones")
    axes[0].set_ylim(0, 1); axes[0].set_ylabel("delivery ratio (mean over seeds, sd bars)"); axes[1].set_ylabel("mean latency of delivered messages, s")
    for ax in axes:
        ax.set_xlabel("radio range, m"); ax.set_xticks([int(r) for r in RANGES_M]); ax.grid(alpha=0.3); ax.legend(fontsize=8)
    fig.suptitle(f"SIMULATION: The ONE {ROUTER[router]} on the thesis window, seeds {seeds} (second view; the thesis = PONS, 17 phones, 10 m)", fontsize=8)
    fig.tight_layout(); fig.savefig(RANGE_OUT / "range.png", dpi=130)
    print(f"  {'phones':8}" + "".join(f"{str(int(r)) + ' m':>16}" for r in RANGES_M) + "   (delivery ratio mean / latency s)")
    for n in counts:
        print(f"  {n:<8}" + "".join(f"{str(summary[n][int(r)]['delivery_ratio_mean']) + ' / ' + str(summary[n][int(r)]['latency_avg_s_mean']):>16}" for r in RANGES_M))
    print(f"  Delivery rises with range: {rises}. THESIS CHECK: none applies (The ONE's numbers); the thesis's RQ4 result is untouched. {body['real_s']} s in all")
    print(f"  sha256 {hashlib.sha256((RANGE_OUT / 'range.json').read_bytes()).hexdigest()} evidence/mesh/range/range.json; {body['png']}")
    return 0


def plot(body: dict, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    for ax, key, title in zip(axes, ("delivery_ratio_mean", "latency_avg_s_mean"), ("delivery ratio (mean over seeds)", "mean latency of delivered messages, s")):
        for r in body["routers"]:
            xs = [n for n in body["counts"] if body["summary"][r][str(n) if str(n) in body["summary"][r] else n][key] is not None]
            ys = [body["summary"][r][str(n) if str(n) in body["summary"][r] else n][key] for n in xs]
            ax.plot(xs, ys, "o-", label=r)
        ax.set_xlabel("phones"); ax.set_title(title, fontsize=9); ax.grid(alpha=0.3); ax.set_xticks(body["counts"])
    axes[0].set_ylim(0, 0.1); axes[1].set_ylim(0, None)                   # a true zero: the differences are hundredths
    axes[0].legend(fontsize=8)
    fig.suptitle(f"SIMULATION: The ONE's {', '.join(body['routers'].values())} on the thesis window, radio {body['range_m']:g} m, seeds {body['seeds']} (second view; the thesis = PONS, 17 phones)", fontsize=8)
    fig.tight_layout(); fig.savefig(path, dpi=130)


if __name__ == "__main__":
    sys.exit(main())
