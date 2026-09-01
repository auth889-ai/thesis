from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.preprocess_berlin import parse_locations, parse_measurements  # noqa: E402


def run(args):
    subprocess.run([sys.executable, *args], cwd=ROOT, check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def main():
    temp = Path(tempfile.mkdtemp(prefix="utd19_e2e_smoke_"))
    try:
        raw = temp / "raw"
        run(["-m", "src.create_demo_data", "--output-dir", str(raw), "--seed", "42"])
        actual, _ = parse_measurements(raw / "berlin", 2021, 2, [1, "1", 1.0])
        locations = parse_locations(raw / "berlin/teu_standorte.json")

        predictions = []
        for detid, edge in [("B_DET_1", "e_n10_n11"), ("B_DET_2", "e_n11_n12")]:
            for hour in range(2):
                predictions.append({"detid": detid, "edge_id": edge,
                                    "hour": hour, "predicted_flow": 100 + 20 * hour})
        pred_path = temp / "predictions.csv"
        pd.DataFrame(predictions).to_csv(pred_path, index=False)
        counts = temp / "counts"
        run(["-m", "src.counts_to_edgedata", "--predictions", str(pred_path),
             "--mapping", "demo/demo_mapping.csv", "--output-dir", str(counts),
             "--scale-counts", "0.1", "--begin", "0", "--end", "7200"])
        edge_predictions = pd.read_csv(counts / "edge_predictions.csv")

        route_file = temp / "routes.xml"
        route_file.write_text('''<routes>\n'
<route id="r1" edges="e_n10_n11 e_n11_n12"/>\n'
<vehicle id="v1" route="r1" depart="0"/>\n'
<vehicle id="v2" depart="1"><route edges="e_n01_n11 e_n11_n21"/></vehicle>\n'
</routes>'''.replace("'\n", "\n"), encoding="utf-8")
        coverage = temp / "coverage"
        run(["-m", "src.coverage_audit", "--mapping", "demo/demo_mapping.csv",
             "--route-files", str(route_file), "--output-dir", str(coverage),
             "--require-complete"])
        coverage_summary = json.loads((coverage / "candidate_coverage_summary.json").read_text())

        report = {
            "synthetic_measurement_rows": len(actual),
            "synthetic_measurement_detectors": int(actual["detid"].nunique()),
            "synthetic_location_alias_rows": len(locations),
            "measurement_location_ids_match": sorted(set(actual["detid"]) & set(locations["detid"])),
            "edge_prediction_rows": len(edge_predictions),
            "edge_prediction_counts": edge_predictions["predicted_count"].tolist(),
            "candidate_coverage_percent": coverage_summary["coverage_percent"],
            "scope": "Offline pure-Python/format smoke test; no DuckDB or SUMO binaries in build environment.",
        }
        (ROOT / "tests/offline_smoke_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
    finally:
        shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    main()
