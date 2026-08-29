from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .metrics import geh, mae, rmse, smape
from .utils import write_json


def save_actual_prediction_plots(joined: pd.DataFrame, out: Path, max_detectors: int = 6) -> None:
    if joined.empty:
        return
    detectors = joined.groupby("detid").size().sort_values(ascending=False).head(max_detectors).index
    for detid in detectors:
        frame = joined[joined["detid"] == detid].copy()
        plt.figure(figsize=(9, 5))
        if "date" in frame:
            for date, block in frame.groupby("date"):
                plt.plot(block["hour"], block["actual_flow"], label=f"actual {str(date)[:10]}")
        pred = frame.groupby("hour", as_index=False)["predicted_flow"].mean()
        plt.plot(pred["hour"], pred["predicted_flow"], linestyle="--", linewidth=2.2, label="ML predicted")
        plt.xlabel("Hour")
        plt.ylabel("Vehicles/hour")
        plt.title(f"Berlin detector {detid}: actual vs predicted")
        plt.legend(fontsize=8)
        plt.tight_layout()
        plt.savefig(out / f"detector_{detid}_actual_vs_predicted.png", dpi=170)
        plt.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--edge-predictions", required=True)
    parser.add_argument("--actual")
    parser.add_argument("--simulated-edge", required=True)
    parser.add_argument("--simulated-detector", required=True)
    parser.add_argument("--network-summary")
    parser.add_argument("--network-stats")
    parser.add_argument("--extraction-audit")
    parser.add_argument("--route-sampler-summary")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    predictions = pd.read_csv(args.predictions)
    edge_pred = pd.read_csv(args.edge_predictions)
    sim_edge = pd.read_csv(args.simulated_edge)
    sim_det = pd.read_csv(args.simulated_detector)

    edge_join = edge_pred.merge(sim_edge[["hour", "edge_id", "simulated_count"]],
                                on=["hour", "edge_id"], how="left")
    edge_join["simulated_count"] = edge_join["simulated_count"].fillna(0)
    edge_join["GEH"] = geh(edge_join["predicted_count"], edge_join["simulated_count"])
    edge_join["absolute_mismatch"] = (edge_join["predicted_count"] - edge_join["simulated_count"]).abs()
    edge_join.to_csv(out / "edge_predicted_vs_simulated.csv", index=False)
    geh_summary = {
        "edge_hour_rows": len(edge_join),
        "GEH_lt_5_percent": float(100 * (edge_join["GEH"] < 5).mean()) if len(edge_join) else 0,
        "GEH_lt_10_percent": float(100 * (edge_join["GEH"] < 10).mean()) if len(edge_join) else 0,
        "GEH_mean": float(edge_join["GEH"].mean()) if len(edge_join) else None,
        "GEH_median": float(edge_join["GEH"].median()) if len(edge_join) else None,
        "mean_absolute_mismatch": float(edge_join["absolute_mismatch"].mean()) if len(edge_join) else None,
    }
    pd.DataFrame([geh_summary]).to_csv(out / "geh_summary.csv", index=False)

    actual_metrics = None
    actual_join = pd.DataFrame()
    if args.actual and Path(args.actual).exists():
        actual = pd.read_parquet(args.actual) if str(args.actual).endswith(".parquet") else pd.read_csv(args.actual)
        actual["detid"] = actual["detid"].astype(str)
        predictions["detid"] = predictions["detid"].astype(str)
        actual_join = actual.merge(predictions[["detid", "hour", "predicted_flow"]],
                                   on=["detid", "hour"], how="inner")
        actual_join.to_csv(out / "detector_actual_vs_predicted.csv", index=False)
        if not actual_join.empty:
            actual_metrics = {
                "rows": len(actual_join),
                "detectors": int(actual_join["detid"].nunique()),
                "MAE": mae(actual_join["actual_flow"], actual_join["predicted_flow"]),
                "RMSE": rmse(actual_join["actual_flow"], actual_join["predicted_flow"]),
                "SMAPE_percent": smape(actual_join["actual_flow"], actual_join["predicted_flow"]),
            }
            pd.DataFrame([actual_metrics]).to_csv(out / "actual_prediction_summary.csv", index=False)
            save_actual_prediction_plots(actual_join, out)

    detector_join = predictions.merge(
        sim_det[["detid", "hour", "simulated_count"]], on=["detid", "hour"], how="left"
    )
    detector_join.to_csv(out / "detector_predicted_vs_simulated.csv", index=False)

    plt.figure(figsize=(10, 5))
    hourly = edge_join.groupby("hour", as_index=False)[["predicted_count", "simulated_count"]].sum()
    plt.plot(hourly["hour"], hourly["predicted_count"], linestyle="--", label="sum of monitored predicted entries")
    plt.plot(hourly["hour"], hourly["simulated_count"], label="sum of monitored simulated entries")
    if args.network_summary and Path(args.network_summary).exists():
        network = pd.read_csv(args.network_summary)
        if "running_mean" in network:
            plt.plot(network["hour"], network["running_mean"], label="mean vehicles running in network")
    plt.xlabel("Hour")
    plt.ylabel("Vehicles")
    plt.title("24-hour traffic trajectory: requested counts and simulation")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out / "network_24h_trajectory.png", dpi=180)
    plt.close()

    import json
    network_stats = json.loads(Path(args.network_stats).read_text()) if args.network_stats and Path(args.network_stats).exists() else None
    extraction_audit = json.loads(Path(args.extraction_audit).read_text()) if args.extraction_audit and Path(args.extraction_audit).exists() else None
    route_sampler_summary = json.loads(Path(args.route_sampler_summary).read_text()) if args.route_sampler_summary and Path(args.route_sampler_summary).exists() else None
    summary = {
        "GEH": geh_summary,
        "actual_vs_prediction": actual_metrics,
        "network_stats": network_stats,
        "simulation_extraction": extraction_audit,
        "route_sampler": route_sampler_summary,
        "paper_reference": {
            "Random_Forest_SMAPE_percent": 17.12,
            "Random_Forest_MAE": 71.04,
            "GEH_lt_5_percent_claim": 85,
            "reported_area_km2": 891.7,
            "reported_detectors": ">260",
            "reported_vehicles": ">1.2 million",
        },
        "claim_boundary": "Paper values are references. This report contains the independently generated reimplementation values.",
    }
    write_json(out / "final_evaluation.json", summary)
    print(summary)


if __name__ == "__main__":
    main()
