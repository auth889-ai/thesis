#!/usr/bin/env python3
"""Generate all Lab 01 figures from REAL validated evidence + version-controlled sources.

Data sources (never invented):
  outputs/evidence/unit_full/{aggregate,per_seed}_metrics.csv   (5-seed Colab matrix)
  outputs/evidence/unit_smoke/aggregate_metrics.csv             (smoke matrix)
  outputs/evidence/verification_record.json                     (independent recompute + safety)
  outputs/evidence/bologna_unmodified/{manifest.txt,RERUN_NOTE.md}
  scenarios/unit_validation/tls.tll.xml                         (declared TLS program)
Architecture figures are drawn from code here (no manual screenshots).

Run: python3 scripts/make_figures.py
"""
from __future__ import annotations

import csv
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "outputs/evidence"
FIG = ROOT / "outputs/figures"
FIG.mkdir(parents=True, exist_ok=True)

CTRL = ["fixed_time", "actuated", "max_pressure"]
LABEL = {"fixed_time": "Fixed-Time", "actuated": "Queue-Actuated", "max_pressure": "Max-Pressure*"}
COLOR = {"fixed_time": "#6c757d", "actuated": "#1b6ca8", "max_pressure": "#c1121f"}
STAMP = "DhakaFlow Lab 01 · SUMO 1.27.1 · real Colab run · commit ca2ac81"


def _agg(path):
    rows = {r["controller"]: r for r in csv.DictReader(open(path))}
    return rows


def _per_seed(path):
    out = {c: [] for c in CTRL}
    for r in csv.DictReader(open(path)):
        out[r["controller"]].append(r)
    return out


AGG = _agg(EV / "unit_full/aggregate_metrics.csv")
SMOKE = _agg(EV / "unit_smoke/aggregate_metrics.csv")
SEEDS = _per_seed(EV / "unit_full/per_seed_metrics.csv")
VER = json.loads((EV / "verification_record.json").read_text())


def _box(ax, x, y, w, h, text, fc="#eef2f7", ec="#33475b", fs=8.5, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012",
                                facecolor=fc, edgecolor=ec, linewidth=1.2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            fontweight="bold" if bold else "normal", wrap=True)


def _arrow(ax, p1, p2, color="#33475b"):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle="-|>", mutation_scale=13,
                                 color=color, linewidth=1.3))


def _canvas(title, figsize=(12, 7.2)):
    fig, ax = plt.subplots(figsize=figsize)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    fig.text(0.99, 0.01, STAMP, ha="right", fontsize=6.5, color="#666")
    return fig, ax


def _save(fig, name):
    p = FIG / name
    fig.tight_layout()
    fig.savefig(p, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("wrote", p.name)


# ---------------------------------------------------------------- 01 architecture
def fig01():
    fig, ax = _canvas("Lab 01 architecture — modular, notebook orchestrates src/")
    _box(ax, 0.03, 0.80, 0.94, 0.13,
         "notebooks/Lab01_SUMO_Foundation_Colab.ipynb  —  ORCHESTRATION ONLY\n"
         "(install pinned SUMO · run scripts · verify · bundle evidence)", "#dbe9f6", bold=True)
    _box(ax, 0.03, 0.60, 0.30, 0.13, "scripts/\nrun_matrix.py\nverify_environment.py\nrun_bologna_unmodified.sh\nfetch_upstreams.sh", "#f7f3e8")
    _box(ax, 0.35, 0.60, 0.30, 0.13, "configs/\nsmoke.yaml (1 seed, 900 s)\nfull.yaml (5 seeds, 2100 s)", "#f7f3e8")
    _box(ax, 0.67, 0.60, 0.30, 0.13, "tests/\nunit/ (3, SUMO-free)\nintegration/ (SUMO gate)", "#f7f3e8")
    _box(ax, 0.03, 0.36, 0.44, 0.18,
         "src/dhakaflow_lab01/\nrunner.py  (TraCI lifecycle, step loop, per-step metrics)\n"
         "demand.py  (seeded Poisson arrivals → routes)\nmetrics.py  (tripinfo/step aggregation)\n"
         "colab_env.py · config.py", "#e8f2ec")
    _box(ax, 0.51, 0.36, 0.46, 0.18,
         "src/dhakaflow_lab01/controllers/\nbase.py (min/max-green guards, phase bookkeeping)\n"
         "fixed_time.py · actuated.py · max_pressure.py\nhelpers.py (getControlledLinks → queue/pressure)", "#e8f2ec")
    _box(ax, 0.03, 0.14, 0.44, 0.16,
         "scenarios/unit_validation/\nnodes · edges · connections · tls.tll.xml · unit.sumocfg\n(netconvert-built, deterministic)", "#fdecef")
    _box(ax, 0.51, 0.14, 0.46, 0.16,
         "upstream/ (pinned, never modified)\neclipse-sumo 1.27.1 · DLR-TS/sumo-scenarios @00f6eb47\nBologna/Acosta executed unmodified", "#fdecef")
    for x in (0.18, 0.50, 0.82):
        _arrow(ax, (x, 0.80), (x, 0.735))
    _arrow(ax, (0.25, 0.60), (0.25, 0.545))
    _arrow(ax, (0.74, 0.60), (0.74, 0.545))
    _arrow(ax, (0.25, 0.36), (0.25, 0.305))
    _arrow(ax, (0.74, 0.36), (0.74, 0.305))
    _save(fig, "01_lab_architecture.png")


# ------------------------------------------------- 02 paper → dhakaflow pipeline
def fig02():
    fig, ax = _canvas("Paper → Lab 01 → DhakaFlow Nexus pipeline")
    _box(ax, 0.02, 0.78, 0.29, 0.15,
         "PRIMARY PAPER\nAlvarez Lopez et al. 2018\n“Microscopic Traffic Simulation\nusing SUMO”, IEEE ITSC\nDOI 10.1109/ITSC.2018.8569938",
         "#dbe9f6", bold=True)
    _box(ax, 0.35, 0.78, 0.29, 0.15,
         "REAL-WORLD SCENARIO PAPER\nBieker et al. 2014 (SUMO conf.)\n“Traffic simulation for all:\nBologna”\nDOI 10.1007/978-3-319-15024-6_4", "#dbe9f6")
    _box(ax, 0.68, 0.78, 0.30, 0.15,
         "THEORY REFERENCE\nVaraiya 2013, Transp. Res. C 36\n“Max pressure control of a network\nof signalized intersections”\nDOI 10.1016/j.trc.2013.08.014", "#dbe9f6")
    _box(ax, 0.02, 0.53, 0.29, 0.15,
         "OFFICIAL SOFTWARE\neclipse-sumo/sumo\ntag v1_27_1\nSHA 7717f237…\n(pip eclipse-sumo==1.27.1)", "#f7f3e8")
    _box(ax, 0.35, 0.53, 0.29, 0.15,
         "OFFICIAL SCENARIO\nDLR-TS/sumo-scenarios\n@ 00f6eb479a9d…\nbologna/acosta/run.sumocfg\nEXECUTED UNMODIFIED", "#f7f3e8")
    _box(ax, 0.68, 0.53, 0.30, 0.15,
         "BASELINE_IMPLEMENTATION\nmovement max-pressure at ONE\njunction — NOT a network-scale\nreproduction of Varaiya (Lab 14)", "#fdecef")
    _box(ax, 0.13, 0.29, 0.74, 0.15,
         "LAB 01 — FOUNDATION_VALIDATION (this lab)\n"
         "TraCI lifecycle · signal action interface · deterministic 5-seed matrix · safety checks · metrics · evidence",
         "#e8f2ec", bold=True)
    _box(ax, 0.13, 0.05, 0.74, 0.16,
         "GRADUATES TO dhakaflow/  →  simulation/ · control/ · evaluation/ · safety/\n"
         "used by: Dhaka calibrated digital twin → Max-Pressure (network) → SUMO-RL/PPO →\n"
         "PressLight → FRAP → CoLight → MAPPO → Forecast-Aware MAPPO → routing & priority",
         "#dbe9f6", bold=True)
    for x in (0.165, 0.495, 0.83):
        _arrow(ax, (x, 0.78), (x, 0.685))
        _arrow(ax, (x, 0.53), (x, 0.445))
    _arrow(ax, (0.50, 0.29), (0.50, 0.215))
    _save(fig, "02_paper_to_dhakaflow_pipeline.png")


# ------------------------------------------------------ 03 SUMO/TraCI control loop
def fig03():
    fig, ax = _canvas("SUMO ↔ TraCI control loop as implemented in src/ (paper §X: simulator coupling)")
    _box(ax, 0.06, 0.72, 0.36, 0.14, "traci.start(cmd)\nrunner.run_one(): binary, sumocfg,\nroute file, seed, end, outputs", "#dbe9f6", bold=True)
    _box(ax, 0.58, 0.72, 0.36, 0.14, "SUMO microscopic core\n(Krauss car-following, step-length 1 s)", "#e8f2ec", bold=True)
    _box(ax, 0.58, 0.50, 0.36, 0.13, "traci.simulationStep()\nadvance one simulation second", "#e8f2ec")
    _box(ax, 0.06, 0.50, 0.36, 0.13, "controller.step(traci, t)\nphase/state read → decision", "#dbe9f6")
    _box(ax, 0.06, 0.28, 0.36, 0.15,
         "OBSERVE (per lane/link)\ngetControlledLinks · getLastStepHaltingNumber\n→ queue score / pressure score", "#f7f3e8")
    _box(ax, 0.58, 0.28, 0.36, 0.15,
         "ACT (safety-guarded)\nsetPhaseDuration(extend | 0)\nmin_green ≤ elapsed ≤ max_green\nyellow phase always traversed", "#fdecef")
    _box(ax, 0.20, 0.06, 0.60, 0.14,
         "RECORD  →  step_metrics.csv · controller_actions.jsonl · tripinfo.xml · summary.xml · sumo.log\n"
         "→ metrics.aggregate_metrics() → per_seed_metrics.csv / aggregate_metrics.csv", "#eef2f7", bold=True)
    _arrow(ax, (0.42, 0.79), (0.58, 0.79))
    _arrow(ax, (0.76, 0.72), (0.76, 0.635))
    _arrow(ax, (0.58, 0.565), (0.42, 0.565))
    _arrow(ax, (0.24, 0.50), (0.24, 0.435))
    _arrow(ax, (0.42, 0.355), (0.58, 0.355))
    _arrow(ax, (0.76, 0.28), (0.62, 0.20))
    _arrow(ax, (0.24, 0.28), (0.38, 0.20))
    ax.annotate("loop until sim_end", xy=(0.50, 0.66), fontsize=8, style="italic",
                ha="center", color="#33475b")
    _save(fig, "03_sumo_traci_control_loop.png")


# ------------------------------------------------------------- 04 experiment design
def fig04():
    fig, ax = _canvas("Experiment design — fair comparison (identical demand, seeds, scenario, duration)")
    _box(ax, 0.05, 0.76, 0.90, 0.14,
         "SCENARIO (identical for all controllers): 4-arm signalized junction, netconvert-built,\n"
         "static program GGrr → yyrr → rrGG → rryy   ·   step-length 1 s   ·   sim_end 2100 s (full) / 900 s (smoke)",
         "#e8f2ec", bold=True)
    _box(ax, 0.05, 0.54, 0.90, 0.16,
         "DEMAND: seeded Poisson arrivals, asymmetric peaks (NS 650 vph/arm then EW 650 vph/arm)\n"
         "SAME route file per seed reused across all three controllers  →  seeds 11, 22, 33, 44, 55",
         "#dbe9f6", bold=True)
    for i, c in enumerate(CTRL):
        x = 0.05 + i * 0.315
        n = int(float(AGG[c]["n_seeds"]))
        _box(ax, x, 0.30, 0.28, 0.16,
             f"{LABEL[c]}\n{n} seeds × 1 scenario\n"
             f"{'observation only' if c=='fixed_time' else 'min_green 10 s · max_green 45 s'}\n"
             f"{'(SUMO executes static plan)' if c=='fixed_time' else 'decision every 5 s'}",
             "#f7f3e8")
        _arrow(ax, (x + 0.14, 0.54), (x + 0.14, 0.465))
        _arrow(ax, (x + 0.14, 0.30), (x + 0.14, 0.225))
    _box(ax, 0.05, 0.06, 0.90, 0.155,
         "IDENTICAL METRIC PIPELINE → throughput · avg/p95 travel time · waiting · queue mean/p95/max ·\n"
         "stops proxy (waitingCount) · spillback proxy (queue-ratio ≥ 0.8)   +   independent recomputation",
         "#eef2f7", bold=True)
    _save(fig, "04_experiment_design.png")


# ------------------------------------------------------------ 05 controller results
def fig05():
    metrics = [("avg_travel_time", "avg travel time (s)"), ("p95_travel_time", "p95 travel time (s)"),
               ("avg_waiting_time", "avg waiting (s)"), ("mean_queue", "mean queue (veh)"),
               ("p95_queue", "p95 queue (veh)"), ("throughput", "throughput (veh)")]
    fig, axes = plt.subplots(2, 3, figsize=(13.5, 7.4))
    for ax, (key, label) in zip(axes.ravel(), metrics):
        vals = [float(AGG[c][f"{key}_mean"]) for c in CTRL]
        errs = [float(AGG[c][f"{key}_std"]) for c in CTRL]
        ax.bar([LABEL[c] for c in CTRL], vals, yerr=errs, capsize=4,
               color=[COLOR[c] for c in CTRL], alpha=0.9)
        ax.set_title(label, fontsize=10)
        ax.tick_params(axis="x", labelsize=8, rotation=12)
        for i, (v, e) in enumerate(zip(vals, errs)):
            ax.text(i, v + e, f"{v:.1f}", ha="center", va="bottom", fontsize=8)
        ax.margins(y=0.20)
    fig.suptitle("Lab 01 five-seed results (mean ± std over seeds 11/22/33/44/55) — real Colab run",
                 fontsize=13, fontweight="bold")
    fig.text(0.99, 0.005, STAMP, ha="right", fontsize=6.5, color="#666")
    _save(fig, "05_controller_results.png")


def _seed_scatter(ax, key, ylabel):
    for i, c in enumerate(CTRL):
        ys = [float(r[key]) for r in SEEDS[c]]
        xs = [i + (j - (len(ys) - 1) / 2) * 0.07 for j in range(len(ys))]
        ax.scatter(xs, ys, color=COLOR[c], s=34, zorder=3, label=LABEL[c] if False else None)
        m = float(AGG[c][f"{key}_mean"])
        ax.hlines(m, i - 0.28, i + 0.28, color="black", lw=2, zorder=4)
        ax.text(i, m, f"  mean {m:.1f}", va="bottom", fontsize=8)
    ax.set_xticks(range(len(CTRL)))
    ax.set_xticklabels([LABEL[c] for c in CTRL], fontsize=9)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.3)


def fig06():
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.4))
    _seed_scatter(axes[0], "mean_queue", "mean queue (vehicles)")
    axes[0].set_title("Mean queue — every seed shown")
    _seed_scatter(axes[1], "p95_queue", "p95 queue (vehicles)")
    axes[1].set_title("p95 queue — every seed shown")
    fig.suptitle("Queue comparison (5 seeds, identical demand) — adaptive control reduces queues",
                 fontsize=12, fontweight="bold")
    fig.text(0.99, 0.005, STAMP, ha="right", fontsize=6.5, color="#666")
    _save(fig, "06_queue_comparison.png")


def fig07():
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.4))
    _seed_scatter(axes[0], "avg_travel_time", "avg travel time (s)")
    axes[0].set_title("Average travel time")
    _seed_scatter(axes[1], "avg_waiting_time", "avg waiting time (s)")
    axes[1].set_title("Average waiting time")
    fig.suptitle("Travel/waiting time — fixed-time keeps a small travel-time edge, "
                 "adaptive controllers cut waiting", fontsize=12, fontweight="bold")
    fig.text(0.99, 0.005, STAMP, ha="right", fontsize=6.5, color="#666")
    _save(fig, "07_travel_time_comparison.png")


def fig08():
    fig, ax = plt.subplots(figsize=(9.5, 5.6))
    _seed_scatter(ax, "throughput", "arrived vehicles")
    gen = [float(AGG[c]["generated_vehicles_mean"]) for c in CTRL]
    ax.hlines(gen[0], -0.4, len(CTRL) - 0.6, color="#c1121f", ls="--", lw=1.4,
              label=f"generated demand (mean {gen[0]:.0f} veh, identical per seed)")
    ax.legend(fontsize=8, loc="lower left")
    ax.set_title("Throughput — arrived vs generated vehicles (5 seeds)", fontweight="bold")
    fig.text(0.99, 0.005, STAMP, ha="right", fontsize=6.5, color="#666")
    _save(fig, "08_throughput_comparison.png")


def fig09():
    fig, ax = plt.subplots(figsize=(9.5, 5.6))
    vals = [float(AGG[c]["spillback_proxy_fraction_mean"]) for c in CTRL]
    errs = [float(AGG[c]["spillback_proxy_fraction_std"]) for c in CTRL]
    ax.bar([LABEL[c] for c in CTRL], vals, yerr=errs, capsize=4,
           color=[COLOR[c] for c in CTRL], alpha=0.9)
    for i, v in enumerate(vals):
        ax.text(i, v, f"  {v*100:.1f}% of steps", ha="center", va="bottom", fontsize=9)
    ax.set_ylabel("fraction of simulation steps with max queue-ratio ≥ 0.8")
    ax.set_title("Spillback PROXY (not a detector-based jam-length metric)", fontweight="bold")
    ax.margins(y=0.25)
    ax.grid(axis="y", alpha=0.3)
    fig.text(0.99, 0.005, STAMP + " · proxy definition: metrics.py", ha="right", fontsize=6.5, color="#666")
    _save(fig, "09_spillback_comparison.png")


# ------------------------------------------------------------ 10 signal timeline
def fig10():
    """Declared static TLS program from the version-controlled scenario XML."""
    root = ET.parse(ROOT / "scenarios/unit_validation/tls.tll.xml").getroot()
    logic = root.find("tlLogic")
    phases = [(float(p.get("duration")), p.get("state")) for p in logic.findall("phase")]
    fig, ax = plt.subplots(figsize=(12.5, 4.6))
    link_colors = {"G": "#2a9d8f", "g": "#8ecfc6", "y": "#e9c46a", "r": "#c1121f"}
    n_links = len(phases[0][1])
    t = 0.0
    for dur, state in phases * 3:            # three cycles for readability
        for li, ch in enumerate(state):
            ax.barh(li, dur, left=t, height=0.72, color=link_colors.get(ch, "#999"),
                    edgecolor="white", linewidth=0.6)
        t += dur
    ax.set_yticks(range(n_links))
    ax.set_yticklabels([f"controlled link {i}\n({'NS' if i < 2 else 'EW'} approach)" for i in range(n_links)],
                       fontsize=8)
    ax.set_xlabel("time (s)")
    ax.set_title("Declared static TLS program (scenarios/unit_validation/tls.tll.xml) — 3 cycles\n"
                 "GGrr → yyrr → rrGG → rryy : yellow always separates conflicting greens",
                 fontweight="bold", fontsize=11)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in ["#2a9d8f", "#e9c46a", "#c1121f"]]
    ax.legend(handles, ["green", "yellow", "red"], ncol=3, fontsize=8, loc="upper right")
    fig.text(0.99, 0.005, STAMP + " · adaptive controllers shorten/extend greens within min/max-green,"
             " never removing the yellow phase", ha="right", fontsize=6.5, color="#666")
    _save(fig, "10_signal_phase_timeline.png")


# ----------------------------------------------------------- 11 bologna provenance
def fig11():
    manifest = (EV / "bologna_unmodified/manifest.txt").read_text().strip()
    fig, ax = _canvas("Official Bologna/Acosta scenario — provenance & unmodified-execution evidence",
                      figsize=(12, 7.6))
    _box(ax, 0.03, 0.70, 0.94, 0.20,
         "OFFICIAL SCENARIO (Bieker et al. 2014; iTETRIS project, data from Comune di Bologna)\n"
         "network + demand originally VISSIM → converted to SUMO · peak hour 08:00–09:00\n"
         "traffic-light telemetry + signal plans supplied by the municipality · 636 induction-loop sites\n"
         "repo: github.com/DLR-TS/sumo-scenarios  ·  bologna/acosta/run.sumocfg", "#dbe9f6", bold=True)
    _box(ax, 0.03, 0.36, 0.46, 0.28,
         "EXECUTION MANIFEST (real run)\n\n" + manifest, "#e8f2ec", fs=8)
    _box(ax, 0.51, 0.36, 0.46, 0.28,
         "UPSTREAM INTEGRITY\n\n"
         "git status --porcelain --untracked-files=no\n→ EMPTY (no tracked file modified)\n\n"
         "untracked files = outputs written by the\nunmodified config itself (recorded)\n\n"
         "we never edit upstream; our wrapper only\nruns it and captures logs", "#fdecef", fs=8.5)
    _box(ax, 0.03, 0.06, 0.94, 0.24,
         "DOCUMENTED SCENARIO LIMITATIONS (from the paper, §1.6–1.7)\n"
         "· demand covers ONE hour → ≈30 min usable after warm-up/cool-down\n"
         "· small network → limited route choice → authors advise against rerouting studies\n"
         "· multi-lane roundabouts produce unrealistic jams · pedestrians not included\n"
         "· warm-up needed ≈ 2× max travel time through the network\n"
         "→ Lab 01 uses Bologna ONLY as an official real-world execution check, not as a control benchmark",
         "#f7f3e8", fs=8.5)
    _save(fig, "11_bologna_scenario.png")


# ------------------------------------------------- 12 final dhakaflow connection
def fig12():
    fig, ax = _canvas("Lab 01 → final DhakaFlow Nexus connection (capabilities that graduate)")
    caps = [
        "SUMO simulation runner\n(deterministic, seeded)",
        "TraCI lifecycle\n(start · step · close)",
        "Signal action interface\n(phase extend / terminate)",
        "Scenario execution\n(config-driven)",
        "Traffic metrics\n(travel/wait/queue/throughput)",
        "TLS safety checks\n(min/max green · yellow kept)",
        "Artifact & evidence\ncollection",
        "Fair multi-seed\nbenchmark harness",
    ]
    for i, c in enumerate(caps):
        x = 0.02 + (i % 4) * 0.245
        y = 0.72 - (i // 4) * 0.16
        _box(ax, x, y, 0.225, 0.13, c, "#e8f2ec", fs=8)
    _box(ax, 0.15, 0.40, 0.70, 0.10,
         "dhakaflow/simulation · dhakaflow/control · dhakaflow/safety · dhakaflow/evaluation",
         "#dbe9f6", bold=True)
    for i in range(4):
        _arrow(ax, (0.13 + i * 0.245, 0.56), (0.42 + i * 0.03, 0.505))
    downstream = [
        "Lab 13\nDhaka calibrated\ndigital twin",
        "Lab 14\nnetwork-scale\nMax-Pressure",
        "Labs 15–19\nSUMO-RL · PressLight\nFRAP · CoLight · MAPPO",
        "Lab 20\nForecast-Aware\nMAPPO (contribution)",
        "Labs 21–23\nsafety shield ·\nrouting · priority",
    ]
    for i, d in enumerate(downstream):
        _box(ax, 0.015 + i * 0.198, 0.16, 0.18, 0.15, d, "#f7f3e8", fs=8)
        _arrow(ax, (0.5, 0.40), (0.105 + i * 0.198, 0.315))
    _box(ax, 0.10, 0.02, 0.80, 0.09,
         "Research question answered: DhakaFlow HAS a trusted, reproducible microscopic simulation +\n"
         "control environment in which later world-paper controllers can be trained and evaluated safely.",
         "#eef2f7", bold=True)
    _save(fig, "12_final_dhakaflow_connection.png")


if __name__ == "__main__":
    for f in (fig01, fig02, fig03, fig04, fig05, fig06, fig07, fig08, fig09, fig10, fig11, fig12):
        f()
    print(f"\n{len(list(FIG.glob('*.png')))} figures in {FIG}")
