from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .utils import write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    out = Path(args.output_dir)
    utd = out / "utd19"
    berlin = out / "berlin"
    osm = out / "osm"
    for folder in [utd, berlin, osm]:
        folder.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)

    cities = ["augsburg", "hamburg", "zurich", "london", "melbourne"]
    fclasses = ["primary", "secondary", "tertiary"]
    detectors = []
    rows = []
    for ci, city in enumerate(cities):
        for di in range(6):
            detid = f"{city[:3]}_{di:02d}"
            lanes = int(rng.integers(1, 4))
            fclass = fclasses[di % len(fclasses)]
            detectors.append({
                "detid": detid,
                "length": round(float(rng.uniform(0.08, 0.8)), 6),
                "pos": round(float(rng.uniform(0.002, 0.06)), 6),
                "fclass": fclass,
                "road": f"{city.title()} Road {di}",
                "limit": [30, 50, 60][di % 3],
                "citycode": city,
                "lanes": lanes,
                "linkid": ci * 100 + di,
                "long": 8 + ci * 0.5 + di * 0.01,
                "lat": 48 + ci * 0.4 + di * 0.01,
            })
            for day in pd.date_range("2021-01-01", periods=12, freq="D"):
                for interval in range(0, 86400, 300):
                    hour = interval // 3600
                    morning = 180 * np.exp(-((hour - 8) / 2.4) ** 2)
                    evening = 140 * np.exp(-((hour - 17) / 2.8) ** 2)
                    city_effect = 25 * ci
                    road_effect = 12 * di + (25 if fclass == "primary" else 0)
                    per_lane_rate = max(5, 35 + city_effect + road_effect + morning + evening)
                    flow = max(0, rng.normal(per_lane_rate, 15))
                    error = "bad" if rng.random() < 0.002 else ""
                    rows.append({
                        "city": city, "detid": detid, "day": day.date().isoformat(),
                        "interval": interval, "flow": round(flow, 2),
                        "occ": round(float(np.clip(flow / 30, 1, 45)), 2),
                        "speed": round(float(max(10, 58 - flow / 20 + rng.normal(0, 2))), 2),
                        "error": error,
                    })
    pd.DataFrame(rows).to_csv(utd / "utd19_u.csv", index=False)
    pd.DataFrame(detectors).to_csv(utd / "detectors.csv", index=False)
    pd.DataFrame({"linkid": [d["linkid"] for d in detectors]}).to_csv(utd / "links.csv", index=False)
    (utd / "manual.pdf").write_bytes(b"Demo placeholder; official mode downloads the ETH manual.")

    detector_edges = [
        ("B_DET_1", "e_n10_n11", "Demo Avenue East", 2),
        ("B_DET_2", "e_n11_n12", "Demo Avenue East", 2),
        ("B_DET_3", "e_n01_n11", "Central North", 2),
        ("B_DET_4", "e_n11_n21", "Central South", 2),
    ]
    actual_rows = []
    for date in pd.date_range("2021-02-02", periods=5, freq="D"):
        for detector_index, (detid, edge, road, lanes) in enumerate(detector_edges):
            for hour in range(24):
                morning = 260 * np.exp(-((hour - 8) / 2.2) ** 2)
                evening = 210 * np.exp(-((hour - 17) / 2.8) ** 2)
                baseline = 45 + detector_index * 25
                count = max(0, baseline + morning + evening + rng.normal(0, 25))
                actual_rows.append({
                    "detid": detid, "date": date.strftime("%d.%m.%Y"), "hour": hour,
                    "quality": 1, "Nveh": int(round(count)), "vveh": round(max(12, 55-count/35), 1),
                    "Npassenger": int(round(count*0.82)), "vpassenger": 50,
                    "Ntruck": int(round(count*0.18)), "vtruck": 45,
                })
    pd.DataFrame(actual_rows).to_csv(berlin / "berlin_2021_02.csv", sep=";", index=False)

    # Feature coordinates are synthetic but IDs align with measurements.
    features = []
    coordinates = [(13.40, 52.50), (13.41, 52.50), (13.405, 52.505), (13.405, 52.495)]
    for (detid, edge, road, lanes), coord in zip(detector_edges, coordinates):
        features.append({
            "type": "Feature", "id": detid,
            "properties": {"detid": detid, "name": road, "direction": 90, "lanes": lanes},
            "geometry": {"type": "Point", "coordinates": list(coord)},
        })
    (berlin / "teu_standorte.json").write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, indent=2),
        encoding="utf-8",
    )
    write_json(out / "demo_manifest.json", {"detector_edges": detector_edges})
    print(f"Demo data written to {out}")


if __name__ == "__main__":
    main()
