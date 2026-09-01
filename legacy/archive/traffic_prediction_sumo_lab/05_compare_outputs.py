from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parent
MAPPING = ROOT / "outputs" / "sumo_input_mapping.csv"
EDGE_XML = ROOT / "outputs" / "edge_output.xml"
OUT = ROOT / "outputs"


def main() -> None:
    if not MAPPING.exists():
        raise SystemExit(
            "sumo_input_mapping.csv not found. "
            "Run 03_predictions_to_sumo.py."
        )
    if not EDGE_XML.exists():
        raise SystemExit(
            "edge_output.xml not found. Run 04_run_sumo.py first."
        )

    mapping = pd.read_csv(MAPPING)
    root = ET.parse(EDGE_XML).getroot()

    intervals = []
    for interval in root.findall("interval"):
        begin = float(interval.attrib["begin"])
        edge = None
        for candidate in interval.findall("edge"):
            if candidate.attrib.get("id") == "e0":
                edge = candidate
                break

        entered = 0.0
        speed = 0.0
        density = 0.0
        waiting_time = 0.0
        if edge is not None:
            entered = float(
                edge.attrib.get(
                    "entered",
                    edge.attrib.get("departed", 0),
                )
            )
            speed = float(edge.attrib.get("speed", 0))
            density = float(edge.attrib.get("density", 0))
            waiting_time = float(edge.attrib.get("waitingTime", 0))

        intervals.append(
            {
                "sumo_begin_sec": int(begin),
                "sumo_entered_vehicles": entered,
                "mean_speed_mps": speed,
                "density_veh_per_km": density,
                "waiting_time_sec": waiting_time,
            }
        )

    simulated = pd.DataFrame(intervals)
    result = mapping.merge(
        simulated,
        on="sumo_begin_sec",
        how="left",
    )
    result["sumo_entered_vehicles"] = (
        result["sumo_entered_vehicles"].fillna(0)
    )
    result["prediction_to_sumo_abs_error"] = (
        result["predicted_flow"]
        - result["sumo_entered_vehicles"]
    ).abs()

    mae = float(result["prediction_to_sumo_abs_error"].mean())
    summary = {
        "hours_compared": int(len(result)),
        "mean_absolute_count_mismatch": round(mae, 4),
        "note": (
            "This measures how closely SUMO inserted the predicted "
            "hourly vehicle counts on edge e0."
        ),
    }

    result.to_csv(OUT / "final_comparison.csv", index=False)
    (OUT / "sumo_validation_metrics.json").write_text(
        json.dumps(summary, indent=2)
    )

    plt.figure(figsize=(11, 5))
    plt.plot(result["hour"], result["flow_veh_per_hour"], label="Actual")
    plt.plot(result["hour"], result["predicted_flow"], label="ML predicted")
    plt.plot(
        result["hour"],
        result["sumo_entered_vehicles"],
        label="SUMO entered",
    )
    plt.xlabel("Hour of day")
    plt.ylabel("Vehicles")
    plt.title("Actual vs predicted vs SUMO-simulated traffic")
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUT / "actual_predicted_sumo.png", dpi=160)
    plt.close()

    print("=== FINAL COMPARISON COMPLETE ===")
    print("Summary:", summary)
    print("\nFirst 8 rows:")
    print(result.head(8).to_string(index=False))
    print("\nCreated:")
    print(" - outputs/final_comparison.csv")
    print(" - outputs/sumo_validation_metrics.json")
    print(" - outputs/actual_predicted_sumo.png")


if __name__ == "__main__":
    main()
