from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

from .utils import write_json

LINE = re.compile(
    r"(?:(?P<begin>\d+):\s*)?Wrote\s+(?P<routes>\d+)\s+routes\s+\((?P<distinct>\d+)\s+distinct\).*?"
    r"total count\s+(?P<total>\d+).*?at\s+(?P<locations>\d+)\s+locations\.\s+GEH<(?P<threshold>[\d.]+)\s+for\s+(?P<geh>[\d.]+)%"
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    text = Path(args.log).read_text(encoding="utf-8", errors="replace")
    rows = []
    for match in LINE.finditer(text):
        row = {key: float(value) if key in {"threshold", "geh"} else int(value)
               for key, value in match.groupdict().items() if value is not None}
        row["begin"] = row.get("begin", 0)
        row["hour"] = int(row["begin"] // 3600)
        rows.append(row)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(out / "route_sampler_interval_summary.csv", index=False)
    summary = {
        "intervals_parsed": len(frame),
        "routes_written": int(frame["routes"].sum()) if not frame.empty else None,
        "weighted_GEH_lt_threshold_percent": (
            float((frame["geh"] * frame["locations"]).sum() / frame["locations"].sum())
            if not frame.empty and frame["locations"].sum() else None
        ),
        "note": "Parsed from the official routeSampler log; simulation GEH is calculated separately from edgeData output.",
    }
    write_json(out / "route_sampler_summary.json", summary)
    print(summary)


if __name__ == "__main__":
    main()
