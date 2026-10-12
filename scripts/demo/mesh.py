"""make demo-mesh: phone-to-phone alerts with no network, delivery against the number of phones, three protocols (PONS).

    research/mesh_pons/.venv/bin/python scripts/demo/mesh.py [--no-show]

The movement is the saved Dhaka trace of the mesh study (research/mesh_pons, 17 vehicles present for the whole 5-minute window,
sha256-checked). "k phones" = k of those 17 vehicles, a random subset per seed; messages go only between phones. Radio, messages,
window and routers are the study's (configs/dhaka.yaml); the simulation set-up is the one in scripts/03_run_pons.py run_one.
Output: evidence/demo/mesh/{results.json,mesh.png,run.log,SHA256SUMS}.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import logging
import random
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HERE = REPO / "research/mesh_pons"
OUT = REPO / "evidence/demo/mesh"
PHONES = (4, 8, 12, 17)
NAMES = {"epidemic": "Epidemic (Vahdat & Becker 2000)", "spray_and_wait": "Spray and Wait (Spyropoulos et al. 2005)",
         "prophet": "PRoPHET (Lindgren et al. 2003)"}

spec = importlib.util.spec_from_file_location("run_pons", HERE / "scripts/03_run_pons.py")
rp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rp)


def subset(moves: list, n: int, k: int, seed: int) -> list:
    """Moves of k of the n nodes (chosen by the seed), renumbered 0..k-1 in their original order. Pure."""
    keep = sorted(random.Random(f"phones|{k}|{seed}").sample(range(n), k))
    new = {old: i for i, old in enumerate(keep)}
    return [(t, new[i], x, y, z) for t, i, x, y, z in moves if i in new]


def run(exp: dict, moves: list, k: int, rname: str, seed: int) -> dict:
    import pons
    duration = exp["window"]["end_s"] - exp["window"]["begin_s"]
    world = (max(m[2] for m in moves) + 50, max(m[3] for m in moves) + 50)
    random.seed(seed)
    net = pons.NetworkSettings(exp["radio"]["name"], range=exp["radio"]["range_m"])
    nodes = pons.generate_nodes(k, net=[net], router=rp.make_router(rname))
    msggen = {"type": "single", "interval": exp["messages"]["interval_s"], "src": (0, k), "dst": (0, k),
              "size": exp["messages"]["size_bytes"], "id": "M", "ttl": exp["messages"]["ttl_s"]}
    sim = pons.NetSim(duration, nodes, world_size=world, movements=list(moves),
                      config={"movement_logger": False, "peers_logger": False, "event_logging": False}, msggens=[])
    sim.setup()
    sim.env.process(rp.generator_with_metadata(sim, msggen))     # identical to PONS's own generator (generator_equivalence.json)
    with contextlib.redirect_stdout(io.StringIO()):                # PONS prints a progress bar
        sim.run()
    s = sim.routing_stats
    return {"phones": k, "router": rname, "seed": seed, "created": s["created"], "delivered": s["delivered"],
            "delivery": s["delivered"] / s["created"] if s["created"] else 0.0}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-show", action="store_true")
    a = ap.parse_args()
    print("DEMO: with no mobile network, can an alert hop from phone to phone (Bluetooth, 10 m) between cars in Dhaka traffic?",
          "  Each point: how many of the alerts reach their phone within 5 minutes, for 4 to 17 phones.",
          "SOFTWARE: PONS (pons-dtn 0.2.1, Python DTN simulator); vehicle movement from Eclipse SUMO 1.27.1 via traceExporter.",
          "PAPERS: Epidemic (Vahdat & Becker 2000), Spray and Wait (Spyropoulos et al. 2005), PRoPHET (Lindgren et al. 2003);",
          "  radio range from The ONE simulator's Bluetooth setting (Keranen et al. 2009). Traffic: generated, uncalibrated.", "", sep="\n")
    logging.disable(logging.INFO)                                  # PONS logs every run
    import yaml
    exp = yaml.safe_load((HERE / "configs/dhaka.yaml").read_text())
    mv = json.loads((HERE / "evidence/movement.json").read_text())
    trace = HERE / mv["ns2_trace"]
    if hashlib.sha256(trace.read_bytes()).hexdigest() != mv["ns2_trace_sha256"]:
        print("STOP: the saved movement trace does not match its recorded sha256."); return 1
    moves, n = rp.read_ns2(trace)
    rows, log = [], []
    for k in PHONES:
        for rname in exp["routers"]:
            for seed in exp["seeds"]:
                r = run(exp, subset(moves, n, k, seed), k, rname, seed)
                rows.append(r)
                log.append(f"{k} phones {rname} seed {seed}: created {r['created']} delivered {r['delivered']}")
        line = "  ".join(f"{NAMES[r].split(' (')[0]} {100 * sum(x['delivery'] for x in rows if x['phones'] == k and x['router'] == r) / len(exp['seeds']):.1f} %"
                         for r in exp["routers"])
        print(f"{k:>2} phones: {line}", flush=True)
    saved = {r["router"]: r["delivery_ratio"]["mean"] for r in json.loads((REPO / "results/networking/mesh/dhaka/summary.json").read_text())["rows"]}
    ours = {r: sum(x["delivery"] for x in rows if x["phones"] == n and x["router"] == r) / len(exp["seeds"]) for r in exp["routers"]}
    same = all(abs(ours[r] - saved[r]) < 5e-4 for r in exp["routers"])
    print(f"Check: with all {n} phones this equals the saved mesh study (results/networking/mesh/dhaka/summary.json): "
          + ("yes." if same else f"NO: {ours} against {saved}"))
    print("In plain words: with few phones and a 10 m radio almost no alert gets through; the app sends by mobile network first.")
    OUT.mkdir(parents=True, exist_ok=True)
    res = {"label": "SIMULATED", "city": "dhaka", "trace_sha256": mv["ns2_trace_sha256"], "phones": PHONES, "seeds": exp["seeds"],
           "radio": exp["radio"], "messages": exp["messages"], "pons": "pons-dtn 0.2.1",
           "matches_saved_study_at_all_phones": same, "rows": rows}
    (OUT / "results.json").write_text(json.dumps(res, indent=1) + "\n")
    (OUT / "run.log").write_text("\n".join(log) + "\n")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 5))
    for rname, c in zip(exp["routers"], ("#d2552b", "#1f5fa8", "#3a9a5b")):
        ys = [100 * sum(x["delivery"] for x in rows if x["phones"] == k and x["router"] == rname) / len(exp["seeds"]) for k in PHONES]
        ax.plot(PHONES, ys, marker="o", lw=2, color=c, label=NAMES[rname])
    ax.set(xlabel="phones among the cars (of 17 present the whole 5 minutes)", ylabel="alerts delivered within 5 min (%)", xticks=PHONES,
           title="Dhaka, simulated: phone-to-phone alerts, Bluetooth 10 m, mean of 5 seeds (PONS)")
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "mesh.png", dpi=130)
    sums = "".join(f"{hashlib.sha256((OUT / f).read_bytes()).hexdigest()}  {f}\n" for f in ("results.json", "run.log", "mesh.png"))
    (OUT / "SHA256SUMS").write_text(sums)
    print(f"Figure: {(OUT / 'mesh.png').relative_to(REPO)}  (results.json, run.log, SHA256SUMS beside it)")
    if not a.no_show and sys.platform == "darwin":
        subprocess.run(["open", str(OUT / "mesh.png")], check=False)
    return 0 if same else 2


if __name__ == "__main__":
    sys.exit(main())
