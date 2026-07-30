from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .utils import run, sumo_env, sumo_tool, write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--route-files", nargs="+", required=True)
    parser.add_argument("--counts", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--optimize", default="full")
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--write-flows", choices=["number", "probability", "poisson"])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--begin", type=int, default=0)
    parser.add_argument("--end", type=int, default=86400)
    parser.add_argument("--interval", type=int, default=3600)
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    output = out / "calibrated.rou.xml"
    mismatch = out / "route_sampler_mismatch.xml"
    route_sampler = sumo_tool("routeSampler.py")
    cmd = [
        sys.executable, str(route_sampler),
        "--route-files", ",".join(args.route_files),
        "--edgedata-files", args.counts,
        "--edgedata-attribute", "entered",
        "--output-file", str(output),
        "--mismatch-output", str(mismatch),
        "--begin", str(args.begin), "--end", str(args.end),
        "--interval", str(args.interval),
        "--optimize", str(args.optimize),
        "--threads", str(args.threads), "--seed", str(args.seed),
        "--geh-ok", "5", "--min-count", "1", "--verbose",
        "--attributes", 'departLane="best" departSpeed="max"',
    ]
    if args.write_flows:
        cmd += ["--write-flows", args.write_flows]

    # routeSampler parallelises with multiprocessing, and sumolib builds its
    # edgedata records from a class defined inside a function. That class cannot
    # be pickled, so --threads > 1 dies with
    #   AttributeError: Can't get local object 'compound_object.<locals>.CompoundObject'
    # Fall back to a single thread rather than losing the whole calibration.
    result = run(cmd, log=out / "route_sampler.log", env=sumo_env(), check=False)
    threads_used = args.threads
    if result.returncode != 0 and args.threads > 1:
        print("routeSampler failed with --threads "
              f"{args.threads}; retrying single-threaded.")
        single = [("1" if part == str(args.threads) and cmd[i - 1] == "--threads" else part)
                  for i, part in enumerate(cmd)]
        result = run(single, log=out / "route_sampler.log", env=sumo_env())
        threads_used = 1
    elif result.returncode != 0:
        raise RuntimeError(f"routeSampler failed ({result.returncode}); see route_sampler.log")

    write_json(out / "calibration_manifest.json", {
        "route_files": args.route_files, "counts": args.counts,
        "calibrated_routes": str(output), "mismatch_output": str(mismatch),
        "optimize": args.optimize, "threads_requested": args.threads,
        "threads_used": threads_used,
        "returncode": result.returncode,
        "paper_alignment": "routeSampler receives random/TAZ candidate routes and ML-predicted edge counts; optimize=full.",
    })


if __name__ == "__main__":
    main()
