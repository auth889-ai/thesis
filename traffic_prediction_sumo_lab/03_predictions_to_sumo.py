from __future__ import annotations

from pathlib import Path
import math

import pandas as pd


ROOT = Path(__file__).resolve().parent
PRED = ROOT / "outputs" / "predictions.csv"
SUMO_DIR = ROOT / "sumo"
SUMO_DIR.mkdir(exist_ok=True)


def main() -> None:
    if not PRED.exists():
        raise SystemExit(
            "outputs/predictions.csv not found. "
            "Run: python 01_train_predict.py"
        )

    df = pd.read_csv(PRED)

    # Use the first 24 predicted hours for one simulated day.
    day = df.head(24).copy()

    lines = [
        "<routes>",
        '    <vType id="car" accel="2.6" decel="4.5" '
        'sigma="0.5" length="5" minGap="2.5" maxSpeed="13.89"/>',
        '    <route id="main" edges="e0 e1"/>',
    ]

    for i, row in day.reset_index(drop=True).iterrows():
        begin = int(i * 3600)
        end = int((i + 1) * 3600)
        count = max(1, int(round(row["predicted_flow"])))
        lines.append(
            f'    <flow id="hour_{i:02d}" type="car" '
            f'route="main" begin="{begin}" end="{end}" '
            f'number="{count}" departLane="best" '
            f'departSpeed="max"/>'
        )

    lines.append("</routes>")
    route_file = SUMO_DIR / "predicted_flows.rou.xml"
    route_file.write_text("\n".join(lines) + "\n")

    additional = """<additional>
    <edgeData id="hourly_edges"
              file="../outputs/edge_output.xml"
              period="3600"
              excludeEmpty="false"/>
</additional>
"""
    (SUMO_DIR / "edge_output.add.xml").write_text(additional)

    config = """<configuration>
    <input>
        <net-file value="simple.net.xml"/>
        <route-files value="predicted_flows.rou.xml"/>
        <additional-files value="edge_output.add.xml"/>
    </input>
    <time>
        <begin value="0"/>
        <end value="86400"/>
        <step-length value="1"/>
    </time>
    <processing>
        <time-to-teleport value="-1"/>
    </processing>
    <report>
        <verbose value="true"/>
        <no-step-log value="true"/>
    </report>
    <output>
        <tripinfo-output value="../outputs/tripinfo.xml"/>
    </output>
</configuration>
"""
    cfg = SUMO_DIR / "experiment.sumocfg"
    cfg.write_text(config)

    mapping = day[
        ["time_index", "hour", "flow_veh_per_hour", "predicted_flow"]
    ].copy()
    mapping["sumo_begin_sec"] = range(0, 24 * 3600, 3600)
    mapping["sumo_end_sec"] = range(3600, 25 * 3600, 3600)
    mapping.to_csv(ROOT / "outputs" / "sumo_input_mapping.csv", index=False)

    print("=== PREDICTIONS CONVERTED TO SUMO DEMAND ===")
    print("Input:", PRED)
    print("Output route file:", route_file)
    print("SUMO config:", cfg)
    print("\nFirst 5 hourly flows:")
    print(mapping.head().to_string(index=False))


if __name__ == "__main__":
    main()
