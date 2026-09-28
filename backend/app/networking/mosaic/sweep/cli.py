"""The command line of the sweep: one point, the full grid, parse an existing log directory, or
rebuild the report."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from .metrics import keep_small_logs, parse_point, refresh_tripinfo
from .report import aggregate
from .scenario import P_GRID, RESULTS, SCEN_ROOT, build_scenario, point_name, ptag, run_mosaic


def run_point(p: float, seed: int, duration: int, keep_logs: bool, stdout_dir: Path):
    scenario = build_scenario(p, seed, duration)
    stdout_dir.mkdir(parents=True, exist_ok=True)
    log_dir, wall = run_mosaic(scenario, stdout_dir / f"mosaic_{point_name(p, seed)}.out")
    res = parse_point(log_dir, scenario, p, seed, duration, wall_s=wall)
    kept = keep_small_logs(log_dir, p, seed)
    if not keep_logs:
        shutil.rmtree(log_dir, ignore_errors=True)   # visualizer.csv can be GBs; parsed JSON is the record
        print(f"[clean] removed {log_dir} (small logs kept in {kept})", flush=True)
    aggregate()
    return res


def main(doc: str = ""):
    ap = argparse.ArgumentParser(description=doc, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--p", type=float, help="penetration rate in [0,1]")
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--seeds", type=int, nargs="*", default=[11, 22, 33], help="seeds for --all")
    ap.add_argument("--duration", type=int, default=600, help="simulation duration in s")
    ap.add_argument("--all", action="store_true", help="run the full grid P x seeds sequentially")
    ap.add_argument("--skip-done", action="store_true", help="with --all: skip points whose JSON exists")
    ap.add_argument("--parse-only", type=Path, help="parse an existing MOSAIC log dir for --p/--seed")
    ap.add_argument("--aggregate", action="store_true", help="only rebuild penetration.csv/.md")
    ap.add_argument("--refresh-tripinfo", action="store_true", help="recompute equipped/unequipped travel-time split of existing JSONs from kept logs")
    ap.add_argument("--keep-logs", action="store_true", help="do not delete the MOSAIC log dir after parsing")
    ap.add_argument("--stdout-dir", type=Path, default=RESULTS / "logs", help="where mosaic stdout goes")
    a = ap.parse_args()
    RESULTS.mkdir(parents=True, exist_ok=True)
    if a.aggregate:
        return aggregate()
    if a.refresh_tripinfo:
        return refresh_tripinfo()
    if a.parse_only:
        if a.p is None:
            sys.exit("--parse-only needs --p")
        parse_point(a.parse_only, SCEN_ROOT / point_name(a.p, a.seed), a.p, a.seed, a.duration)
        return aggregate()
    if a.all:
        for seed in a.seeds:
            for p in P_GRID:
                out = RESULTS / f"penetration_p{ptag(p)}_s{seed}.json"
                if a.skip_done and out.exists():
                    print(f"[all] skip {out.name} (exists)")
                    continue
                run_point(p, seed, a.duration, a.keep_logs, a.stdout_dir)
        return
    if a.p is None:
        sys.exit("give --p (and --seed) or --all")
    run_point(a.p, a.seed, a.duration, a.keep_logs, a.stdout_dir)
