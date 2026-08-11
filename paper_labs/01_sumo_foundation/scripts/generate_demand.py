#!/usr/bin/env python3
import argparse, json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from dhakaflow_lab01.demand import DemandPeriod, generate_route_file

p=argparse.ArgumentParser(); p.add_argument('--seed',type=int,required=True); p.add_argument('--out',required=True)
p.add_argument('--duration',type=float,default=1800)
a=p.parse_args(); h=a.duration/2
periods=[DemandPeriod(0,h,650,220), DemandPeriod(h,a.duration,220,650)]
print(json.dumps(generate_route_file(a.out,a.seed,periods),indent=2))
