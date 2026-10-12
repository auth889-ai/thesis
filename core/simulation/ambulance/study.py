"""RQ2 end to end (docs/PAPER_MAP.md, RQ2). Every run is service.run_one (or rl_signals.run) with RQ2's measures; finished runs are
kept on disk and never run twice, so a stage can be stopped and started again.

    python -m core.simulation.ambulance.study ladder     # no-alert ambulance at each density: gridlock and Dhaka's recorded level
    python -m core.simulation.ambulance.study sweep      # alert and alert+preemption x equipped share x paired seeds, every level up to gridlock
    python -m core.simulation.ambulance.study rl         # sumo-rl Q-learning signals: train per level, then rl_signals and rl_signals_alert (in the NumPy 1 venv)
    python -m core.simulation.ambulance.study rerun_v2   # RQ2c: every alerting arm again with make-way v2, into runs_v2/ (4 at a time)
    python -m core.simulation.ambulance.study summary    # summary.json / .md, figures, evidence hashes
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from core.common.paths import REPO
from core.simulation.ambulance import service

RQ2 = REPO / "results/emergency/dhaka/rq2"
RUNS = RQ2 / "runs"                                   # RQ2 and RQ2b: every siren-only and Q-learning run; the alerting arms here used make-way v1 (a record)
RUNS_V2 = RQ2 / "runs_v2"                             # RQ2c: the alerting arms re-run with make-way v2 (configs/ambulance.yaml), paired with the siren-only runs in RUNS
CITY, DEMAND, TECH = "dhaka", "generated", "its_g5"
LEVELS = (0.5, 1, 2, 3, 4, 5, 6, 8)
SHARES = (0.25, 0.5, 0.75, 1.0)
SEEDS_WANTED = 5                                      # siren-only seeds per level for the gridlock verdict
PAIRS_WANTED = 10                                     # finished (config, siren-only) pairs per sweep cell; a crashed seed is replaced
FIRST_SEED, MAX_SEED = 11, 60
GRIDLOCK_FAILS = 3                                    # of 5 seeds: the no-alert ambulance does not arrive before the horizon
GRIDLOCK_TELEPORT_SHARE = 0.05
NP1 = Path.home() / ".dhakaflow/venvs/sumo-rl-np1/bin/python"
SUMO_HOME = "/Users/jannatulferdouseva/miniconda3/lib/python3.13/site-packages/sumo"


def _metrics(arm: str, tech, share: float, seed: int, scale: float, demand: str = DEMAND, root: Path = RUNS) -> Path:
    return root / CITY / demand / (service.run_name(arm, tech, share, seed) + (f"_x{scale:g}" if scale != 1.0 else "")) / "metrics.json"


def one(arm: str, tech, share: float, seed: int, scale: float, demand: str = DEMAND, root: Path = RUNS) -> dict:
    f = _metrics(arm, tech, share, seed, scale, demand, root)
    if f.exists():
        return json.loads(f.read_text())
    m = service.run_one(CITY, arm, tech, share, seed, demand, root=root, scale=scale, observe=True)
    print(f"x{scale:g} {f.parent.name}: {m['state']}, ambulance {m['ambulance'].get('travel_time_s')} s, wall {m['wall_s']} s", flush=True)
    return m


def ok(m: dict) -> bool:
    return m.get("state") != "sumo_crashed"


def baseline_seeds(scale: float) -> list[int]:
    """The first SEEDS_WANTED seeds whose no-alert run finished (SUMO's bluelight crash skips a seed, as in service.sweep)."""
    seeds = []
    for s in range(FIRST_SEED, MAX_SEED):
        if ok(one("no_alert", None, 0.0, s, scale)):
            seeds.append(s)
        if len(seeds) == SEEDS_WANTED:
            break
    return seeds


def gridlocked(rows: list[dict], vehicles_by_run: list[int]) -> dict:
    """Pure: the level's gridlock verdict from its no-alert runs. Tested."""
    fails = sum(not r["ambulance"].get("arrived") for r in rows)
    tele = [r["teleports"] / max(1, v) for r, v in zip(rows, vehicles_by_run) if r.get("teleports") is not None]
    share = statistics.fmean(tele) if tele else 0.0
    return {"ambulance_not_arrived": fails, "teleport_share": round(share, 4),
            "gridlock": fails >= GRIDLOCK_FAILS or share > GRIDLOCK_TELEPORT_SHARE}


def ladder() -> Path:
    out = []
    for scale in LEVELS:
        seeds = baseline_seeds(scale)
        rows = [one("no_alert", None, 0.0, s, scale) for s in seeds]
        g = gridlocked(rows, [(r.get("others") or {}).get("vehicles", 0) + 1 for r in rows])
        dens = [r["why"]["section_density_veh_km"] for r in rows if r.get("why", {}).get("section_density_veh_km") is not None]
        tt = [r["ambulance"]["travel_time_s"] for r in rows if r["ambulance"].get("arrived")]
        out.append({"scale": scale, "seeds": seeds, **g, "section_density_veh_km": round(statistics.fmean(dens), 2) if dens else None,
                    "no_alert_travel_s": round(statistics.fmean(tt), 1) if tt else None, "vehicles": round(statistics.fmean([(r.get("others") or {}).get("vehicles", 0) for r in rows]))})
        print(f"ladder x{scale:g}: {out[-1]}", flush=True)
        if g["gridlock"]:
            break
    p = RQ2 / "ladder.json"
    p.write_text(json.dumps({"generated_utc": datetime.now(timezone.utc).isoformat(), "levels": out,
                             "gridlock_rule": f"no-alert ambulance not arrived on >= {GRIDLOCK_FAILS} of {SEEDS_WANTED} seeds, or teleports > {GRIDLOCK_TELEPORT_SHARE:.0%} of vehicles"}, indent=1))
    return p


def _levels() -> list[dict]:
    return json.loads((RQ2 / "ladder.json").read_text())["levels"]


def pairs(arm: str, tech, share: float, scale: float, wanted: int = PAIRS_WANTED, demand: str = DEMAND) -> list[int]:
    """Seeds on which both the siren-only run and this configuration finished, taking further seeds until `wanted` (as service.sweep)."""
    got = []
    for s in range(FIRST_SEED, MAX_SEED + 1):
        if ok(one("no_alert", None, 0.0, s, scale, demand)) and ok(one(arm, tech, share, s, scale, demand)):
            got.append(s)
        if len(got) == wanted:
            break
    return got


def sweep() -> None:
    for lv in _levels():
        for arm in ("alert", "alert_preemption"):
            for share in SHARES:
                print(f"x{lv['scale']:g} {arm} {share:g}: pairs {pairs(arm, TECH, share, lv['scale'])}", flush=True)


def dhaka(episodes: int = 30) -> None:
    """RQ2b: every arm at the corridor's "Dhaka density" level (evidence/ambulance_rq2/dhaka_density/match.json), 10 pairs each."""
    m = json.loads((REPO / "evidence/ambulance_rq2/dhaka_density/match.json").read_text())
    sc, dem = m["chosen_scale"], "dhaka_density"
    if sc is None:
        raise SystemExit("no scale reached the recorded density range; nothing to run at Dhaka density")
    for arm in ("alert", "alert_preemption"):
        for share in SHARES:
            print(f"dhaka x{sc:g} {arm} {share:g}: pairs {pairs(arm, TECH, share, sc, demand=dem)}", flush=True)
    env = {**os.environ, "SUMO_HOME": SUMO_HOME, "DHAKAFLOW_NO_OBSERVATORY": "1", "PYTHONPATH": f"{REPO}:{REPO / 'backend'}"}
    if not (RQ2 / "rl" / f"train_{dem}_x{sc:g}.json").exists():
        subprocess.run([str(NP1), "-m", "core.simulation.ambulance.rl_signals", "train", "--scale", str(sc), "--episodes", str(episodes), "--demand", dem], cwd=REPO, env=env, check=True)
    done = 0
    for s in range(FIRST_SEED, MAX_SEED + 1):
        if done >= PAIRS_WANTED:
            break
        if not ok(one("no_alert", None, 0.0, s, sc, dem)):
            continue
        for arm in ("rl_signals", "rl_signals_alert"):
            name = f"{arm}{'_' + TECH + '_p100' if arm == 'rl_signals_alert' else ''}_s{s}_x{sc:g}"
            if not (RUNS / CITY / dem / name / "metrics.json").exists():
                subprocess.run([str(NP1), "-m", "core.simulation.ambulance.rl_signals", "run", "--scale", str(sc), "--seed", str(s), "--arm", arm, "--share", "1.0", "--demand", dem],
                               cwd=REPO, env=env, check=True, stdout=subprocess.DEVNULL)
        f = RUNS / CITY / dem / f"rl_signals_s{s}_x{sc:g}" / "metrics.json"
        done += f.exists() and ok(json.loads(f.read_text()))


def _v2_job(job: tuple) -> str:
    """One RQ2c run (a process-pool worker): an alerting arm with make-way v2, into RUNS_V2."""
    kind, arm, share, seed, scale, dem = job
    if kind == "sumo":
        m = one(arm, TECH, share, seed, scale, dem, root=RUNS_V2)
        return f"{dem} x{scale:g} {arm} {share:g} s{seed}: {m.get('state')}"
    env = {**os.environ, "SUMO_HOME": SUMO_HOME, "DHAKAFLOW_NO_OBSERVATORY": "1", "PYTHONPATH": f"{REPO}:{REPO / 'backend'}"}
    subprocess.run([str(NP1), "-m", "core.simulation.ambulance.rl_signals", "run", "--scale", str(scale), "--seed", str(seed), "--arm", "rl_signals_alert", "--share", "1.0",
                    "--demand", dem, "--root", str(RUNS_V2)], cwd=REPO, env=env, check=True, stdout=subprocess.DEVNULL)
    return f"{dem} x{scale:g} rl_signals_alert s{seed}: done"


def _v2_path(kind: str, arm: str, share: float, seed: int, scale: float, dem: str) -> Path:
    if kind == "sumo":
        return _metrics(arm, TECH, share, seed, scale, dem, RUNS_V2)
    return RUNS_V2 / CITY / dem / f"rl_signals_alert_{TECH}_p100_s{seed}_x{scale:g}" / "metrics.json"


def rerun_v2(jobs: int = 4) -> None:
    """RQ2c: every alerting arm (alert and alert + preemption at every share, Q-learning + alert at 100 %) at every density level and at
    the Dhaka-density level, with make-way v2, until each cell has PAIRS_WANTED finished pairs with the existing siren-only runs.
    A crashed seed is replaced by the next seed whose siren-only run finished, as in the sweep. Runs go `jobs` at a time."""
    from concurrent.futures import ProcessPoolExecutor
    dk = json.loads((REPO / "evidence/ambulance_rq2/dhaka_density/match.json").read_text())["chosen_scale"]
    levels = [(lv["scale"], DEMAND) for lv in _levels()] + ([(dk, "dhaka_density")] if dk else [])
    cells = [("sumo", arm, share, sc, dem) for sc, dem in levels for arm in ("alert", "alert_preemption") for share in SHARES] + \
            [("rl", "rl_signals_alert", 1.0, sc, dem) for sc, dem in levels]
    siren = {(sc, dem): [s for s in range(FIRST_SEED, MAX_SEED + 1) if _metrics("no_alert", None, 0.0, s, sc, dem).exists()
                         and ok(json.loads(_metrics("no_alert", None, 0.0, s, sc, dem).read_text()))] for sc, dem in levels}
    with ProcessPoolExecutor(jobs) as ex:
        while True:
            todo = []
            for kind, arm, share, sc, dem in cells:
                done = [s for s in siren[(sc, dem)] if _v2_path(kind, arm, share, s, sc, dem).exists()]
                good = [s for s in done if ok(json.loads(_v2_path(kind, arm, share, s, sc, dem).read_text()))]
                need = PAIRS_WANTED - len(good)
                fresh = [s for s in siren[(sc, dem)] if s not in done][:max(0, need)]
                todo += [(kind, arm, share, s, sc, dem) for s in fresh]
            if not todo:
                short = {(sc, dem) for kind, arm, share, sc, dem in cells
                         if sum(1 for s in siren[(sc, dem)] if _v2_path(kind, arm, share, s, sc, dem).exists()
                                and ok(json.loads(_v2_path(kind, arm, share, s, sc, dem).read_text()))) < PAIRS_WANTED}
                if not short:
                    break
                for sc, dem in short:                          # the siren-only seeds ran out (crashes): add the next one; siren-only runs never use make-way
                    nxt = max([FIRST_SEED - 1, *siren[(sc, dem)], *[s for s in range(FIRST_SEED, MAX_SEED + 1) if _metrics("no_alert", None, 0.0, s, sc, dem).exists()]]) + 1
                    if nxt > MAX_SEED:
                        raise SystemExit(f"no seeds left for x{sc:g} {dem}")
                    if ok(one("no_alert", None, 0.0, nxt, sc, dem)):
                        siren[(sc, dem)].append(nxt)
                continue
            for line in ex.map(_v2_job, todo):
                print(line, flush=True)


def rl(episodes: int = 30) -> None:
    env = {**os.environ, "SUMO_HOME": SUMO_HOME, "DHAKAFLOW_NO_OBSERVATORY": "1", "PYTHONPATH": f"{REPO}:{REPO / 'backend'}"}
    for lv in _levels():
        sc = lv["scale"]
        if not (RQ2 / "rl" / f"train_x{sc:g}.json").exists() or len(json.loads((RQ2 / "rl" / f"train_x{sc:g}.json").read_text())["episodes"]) < episodes:
            subprocess.run([str(NP1), "-m", "core.simulation.ambulance.rl_signals", "train", "--scale", str(sc), "--episodes", str(episodes)], cwd=REPO, env=env, check=True)
        for s in range(FIRST_SEED, MAX_SEED + 1):
            have = sum(1 for a in ("rl_signals",) for x in [s2 for s2 in range(FIRST_SEED, s)
                       if (RUNS / CITY / DEMAND / f"rl_signals_s{s2}_x{sc:g}" / "metrics.json").exists()
                       and ok(json.loads((RUNS / CITY / DEMAND / f"rl_signals_s{s2}_x{sc:g}" / "metrics.json").read_text()))
                       and ok(one("no_alert", None, 0.0, s2, sc))])
            if have >= PAIRS_WANTED:
                break
            if not ok(one("no_alert", None, 0.0, s, sc)):
                continue
            for arm in ("rl_signals", "rl_signals_alert"):
                name = f"{arm}{'_' + TECH + '_p100' if arm == 'rl_signals_alert' else ''}_s{s}_x{sc:g}"
                if (RUNS / CITY / DEMAND / name / "metrics.json").exists():
                    continue
                subprocess.run([str(NP1), "-m", "core.simulation.ambulance.rl_signals", "run", "--scale", str(sc), "--seed", str(s), "--arm", arm, "--share", "1.0"],
                               cwd=REPO, env=env, check=True, stdout=subprocess.DEVNULL)
                print(f"x{sc:g} {name}: done", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=["ladder", "sweep", "rl", "dhaka", "rerun_v2", "summary"])
    a = ap.parse_args()
    if a.stage == "summary":
        from core.simulation.ambulance.summary import build
        print(build())
    else:
        print({"ladder": ladder, "sweep": sweep, "rl": rl, "dhaka": dhaka, "rerun_v2": rerun_v2}[a.stage]())
