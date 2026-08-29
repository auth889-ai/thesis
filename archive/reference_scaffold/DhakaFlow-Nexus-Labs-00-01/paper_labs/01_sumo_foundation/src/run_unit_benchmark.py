from __future__ import annotations
import argparse
import json
from pathlib import Path
import pandas as pd

from src.common import run_traci
from src.controllers import FixedTime, QueueActuated, MaxPressure
from src.metrics import combined_metrics


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', required=True, help='unit.sumocfg')
    ap.add_argument('--out', required=True)
    ap.add_argument('--seed', type=int, default=2018)
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    strategies = [FixedTime(), QueueActuated(), MaxPressure()]
    rows=[]
    for strategy in strategies:
        run_dir = out / strategy.name
        tripinfo, summary, queue_csv = run_traci(args.config, strategy, run_dir, seed=args.seed)
        metrics = combined_metrics(tripinfo, queue_csv)
        metrics['controller'] = strategy.name
        rows.append(metrics)
        (run_dir/'metrics.json').write_text(json.dumps(metrics, indent=2))
        print(strategy.name, metrics)
    df=pd.DataFrame(rows).sort_values('mean_trip_duration_s')
    df.to_csv(out/'benchmark.csv', index=False)
    print(df.to_string(index=False))

if __name__ == '__main__':
    main()
