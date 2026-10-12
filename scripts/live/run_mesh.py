"""make run-mesh: phone-to-phone alerts with no network (RQ4), computed live by PONS, drawn as it runs.

    research/mesh_pons/.venv/bin/python scripts/live/run_mesh.py [--protocol epidemic|spray_and_wait|prophet] [--phones 17]
                                                                 [--range 10] [--seed 1] [--speed 30] [--no-gui]

The movement is the RQ4 study's Dhaka trace (17 vehicles present for the whole 5 minutes, sha256-checked); --phones below 17 takes a
subset fixed by the seed. PONS's own NetSim.run() simulates; a watcher process added to the same simpy clock only reads the phones'
positions once a simulated second and draws them (links when within range, the number of alerts delivered). Then the other study seeds
run without a window. The result is PONS's own statistics, summarised with the study's formulas (core/networking/mesh/results.py), and
with the study's settings (17 phones, 10 m) it is checked against the saved runs.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import logging
import math
import random
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HERE = REPO / "research/mesh_pons"
OUT = REPO / "evidence/live_runs/mesh"
NAMES = {"epidemic": "Epidemic (Vahdat & Becker 2000)", "spray_and_wait": "Spray and Wait (Spyropoulos et al. 2005)",
         "prophet": "PRoPHET (Lindgren et al. 2003)"}

spec = importlib.util.spec_from_file_location("run_pons", HERE / "scripts/03_run_pons.py")
rp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rp)
dspec = importlib.util.spec_from_file_location("demo_mesh", REPO / "scripts/demo/mesh.py")
dm = importlib.util.module_from_spec(dspec)
dspec.loader.exec_module(dm)


def simulate(exp: dict, moves: list, k: int, rname: str, seed: int, range_m: float, draw=None) -> dict:
    """One PONS run as the study sets it up (03_run_pons.run_one); `draw(netsim, t)` is called once a simulated second if given."""
    import pons
    duration = exp["window"]["end_s"] - exp["window"]["begin_s"]
    world = (max(m[2] for m in moves) + 50, max(m[3] for m in moves) + 50)
    random.seed(seed)
    net = pons.NetworkSettings(exp["radio"]["name"], range=range_m)
    nodes = pons.generate_nodes(k, net=[net], router=rp.make_router(rname))
    msggen = {"type": "single", "interval": exp["messages"]["interval_s"], "src": (0, k), "dst": (0, k),
              "size": exp["messages"]["size_bytes"], "id": "M", "ttl": exp["messages"]["ttl_s"]}
    sim = pons.NetSim(duration, nodes, world_size=world, movements=list(moves),
                      config={"movement_logger": False, "peers_logger": False, "event_logging": False}, msggens=[])
    sim.setup()
    sim.env.process(rp.generator_with_metadata(sim, msggen))
    if draw:
        def watch():
            while True:
                draw(sim, sim.env.now)
                yield sim.env.timeout(1.0)
        sim.env.process(watch())
    with contextlib.redirect_stdout(io.StringIO()):
        sim.run()
    return dict(sim.routing_stats)


class View:
    """The live window: trails of the trace, phones, links within range, delivered count."""

    def __init__(self, moves: list, range_m: float, rname: str, k: int, seed: int, speed: float, frame: Path | None = None):
        import matplotlib.pyplot as plt
        self.frame = frame
        self.plt, self.range_m, self.speed = plt, range_m, speed
        plt.ion()
        self.fig, self.ax = plt.subplots(figsize=(10, 8))
        trails: dict[int, list] = {}
        for t, i, x, y, _ in moves:
            trails.setdefault(i, []).append((x, y))
        for pts in trails.values():
            self.ax.plot([p[0] for p in pts], [p[1] for p in pts], color="#dddddd", lw=1, zorder=1)
        self.dots = self.ax.scatter([], [], s=60, color="#1f5fa8", zorder=3)
        self.links = []
        self.text = self.ax.text(0.01, 0.99, "", transform=self.ax.transAxes, va="top", fontsize=11, family="monospace",
                                 bbox={"facecolor": "white", "alpha": 0.9, "edgecolor": "#999"})
        self.ax.set_aspect("equal"); self.ax.set_xticks([]); self.ax.set_yticks([])
        self.ax.set_title(f"Dhaka, SIMULATED: {k} phones, {NAMES[rname]}, radio {range_m:g} m, seed {seed}  (PONS)", fontsize=11)
        self.fig.tight_layout()

    def __call__(self, sim, t: float) -> None:
        pos = [(n.x, n.y) for n in sim.nodes.values()]
        for ln in self.links:
            ln.remove()
        self.links = []
        near, linked = 0, set()
        for a in range(len(pos)):
            for b in range(a + 1, len(pos)):
                if math.dist(pos[a], pos[b]) <= self.range_m:
                    near += 1
                    linked |= {a, b}
                    self.links += self.ax.plot([pos[a][0], pos[b][0]], [pos[a][1], pos[b][1]], color="#e8590c", lw=3, zorder=2)
        self.dots.set_offsets(pos)
        self.dots.set_color(["#e8590c" if i in linked else "#1f5fa8" for i in range(len(pos))])   # in range of another phone: orange, larger
        self.dots.set_sizes([220 if i in linked else 60 for i in range(len(pos))])
        s = sim.routing_stats
        self.text.set_text(f"t = {int(t):3d} s of 300\nphone pairs in range now: {near}\nalerts created: {s['created']}\n"
                           f"delivered: {s['delivered']}\nrelayed copies: {s['relayed']}")
        self.fig.canvas.draw_idle()
        if self.frame and int(t) == 150:
            self.fig.savefig(self.frame, dpi=100)
        self.plt.pause(1.0 / self.speed)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--one" in argv:                                            # the second view: The ONE's GUI on the same movement (scripts/live/run_mesh_one.py)
        sys.path.insert(0, str(REPO / "scripts/live"))
        import run_mesh_one
        rest, skip = [], False
        for x in argv:                                             # The ONE takes protocol, range, seed and --no-gui; all 17 phones
            if skip:
                skip = False
            elif x in ("--phones", "--speed"):
                skip = True
            elif x != "--one":
                rest.append(x)
        return run_mesh_one.main(rest)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--protocol", default="prophet", choices=list(NAMES))
    ap.add_argument("--phones", type=int, default=17)
    ap.add_argument("--range", type=float, default=10.0, help="radio range in metres (the study: 10, The ONE's Bluetooth setting)")
    ap.add_argument("--seed", type=int, default=1, help="the seed watched in the window; the study's other seeds then run without one")
    ap.add_argument("--speed", type=float, default=30.0, help="simulated seconds per real second in the window")
    ap.add_argument("--no-gui", action="store_true")
    ap.add_argument("--frame", type=Path, help=argparse.SUPPRESS)          # save the window at t = 150 s (for the docs)
    a = ap.parse_args(argv)
    logging.disable(logging.INFO)
    import yaml
    exp = yaml.safe_load((HERE / "configs/dhaka.yaml").read_text())
    mv = json.loads((HERE / "evidence/movement.json").read_text())
    trace = HERE / mv["ns2_trace"]
    if hashlib.sha256(trace.read_bytes()).hexdigest() != mv["ns2_trace_sha256"]:
        print("STOP: the movement trace does not match its recorded sha256."); return 1
    moves, n = rp.read_ns2(trace)
    if not 2 <= a.phones <= n:
        print(f"STOP: --phones must be 2..{n} (the vehicles present for the whole 5 minutes of the study's trace)."); return 1
    print(f"LIVE RUN (RQ4 offline mesh, Dhaka, SIMULATION): {a.phones} phones carry alerts hop by hop, {NAMES[a.protocol]}, radio {a.range:g} m.",
          "SOFTWARE: PONS (pons-dtn 0.2.1, Python DTN simulator); movement from Eclipse SUMO 1.27.1 via traceExporter; radio range default",
          "  from The ONE's Bluetooth setting (Keranen et al., SIMUTools 2009). Traffic: generated, uncalibrated.", "", sep="\n")
    seeds = list(dict.fromkeys([a.seed] + list(exp["seeds"])))
    rows = []
    for s in seeds:
        mv_s = dm.subset(moves, n, a.phones, s)
        draw = View(mv_s, a.range, a.protocol, a.phones, s, a.speed, a.frame) if (s == a.seed and not a.no_gui) else None
        st = simulate(exp, mv_s, a.phones, a.protocol, s, a.range, draw)
        if draw:
            draw.plt.ioff(); draw.plt.close(draw.fig)
        rows.append({"seed": s, **{k: st[k] for k in ("created", "delivered", "relayed", "latency_avg", "delivery_prob", "hops_avg")}})
        print(f"  seed {s}: created {st['created']}, delivered {st['delivered']} ({100 * st['delivery_prob']:.1f} %), "
              f"delay {st['latency_avg']:.1f} s, relayed {st['relayed']}" + ("   <- watched" if draw else ""), flush=True)
    study = [r for r in rows if r["seed"] in exp["seeds"]]
    ratio = statistics.fmean(r["delivery_prob"] for r in study)
    delivered = [r for r in study if r["delivered"]]
    delay = statistics.fmean(r["latency_avg"] for r in delivered) if delivered else None
    copies = statistics.fmean(r["relayed"] / r["created"] for r in study)
    print("", f"RESULT of this run ({a.phones} phones, {a.protocol}, {a.range:g} m, study seeds {exp['seeds']}):",
          f"  delivered {100 * ratio:.1f} % of alerts within 5 minutes; delay {'%.1f s' % delay if delay else '— (none delivered)'}; {copies:.2f} copies per alert", sep="\n")
    check = None
    if a.phones == n and a.range == exp["radio"]["range_m"]:
        saved = {r["router"]: r for r in json.loads((REPO / "results/networking/mesh/dhaka/summary.json").read_text())["rows"]}[a.protocol]
        want = {p["seed"]: (p["created"], p["delivered"]) for p in saved["per_seed"]}
        got = {r["seed"]: (r["created"], r["delivered"]) for r in study}
        check = want == got
        print(f"  THESIS CHECK: the study's {a.protocol} runs (results/networking/mesh/dhaka/summary.json): delivery {saved['delivery_ratio']['mean']} -> "
              + ("REPRODUCED seed by seed." if check else f"DIFFERENT: saved {want}, now {got}"))
    else:
        print("  THESIS CHECK: the study ran 17 phones at 10 m; these settings are new, so there is no thesis number to compare.")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "last_run.json").write_text(json.dumps({"args": vars(a), "rows": rows, "delivery_ratio": ratio, "delay_s": delay, "copies": copies,
                                                   "thesis_check": check}, indent=1) + "\n")
    return 0 if check is not False else 2


if __name__ == "__main__":
    sys.exit(main())
