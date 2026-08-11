#!/usr/bin/env python3
import argparse,csv,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from dhakaflow_lab01.config import load_config
from dhakaflow_lab01.demand import DemandPeriod, generate_route_file
from dhakaflow_lab01.runner import run_one
from dhakaflow_lab01.metrics import aggregate_metrics

p=argparse.ArgumentParser(); p.add_argument('--config',default=str(ROOT/'configs/full.yaml')); p.add_argument('--output-root',default=None)
a=p.parse_args(); cfg=load_config(a.config)
sc=ROOT/'scenarios/unit_validation'
if not (sc/'network.net.xml').exists(): subprocess.run(['bash',str(ROOT/'scripts/build_unit_network.sh')],check=True)
outroot=Path(a.output_root) if a.output_root else ROOT/'outputs'/'unit_validation'/cfg['experiment_name']
outroot.mkdir(parents=True,exist_ok=True)
periods=[DemandPeriod(**x) for x in cfg['demand']['periods']]
rows=[]
for seed in cfg['seeds']:
    route_file=outroot/'demand'/f'routes_seed_{seed}.rou.xml'
    demand_meta=generate_route_file(route_file,seed,periods)
    for controller in cfg['controllers']:
        rd=outroot/controller/f'seed_{seed}'
        run_one(cfg['sumo_binary'],sc/'unit.sumocfg',route_file,rd,controller,seed,cfg['sim_end'],cfg['controller'])
        m=aggregate_metrics(rd/'tripinfo.xml',rd/'step_metrics.csv')
        rows.append({'controller':controller,'seed':seed,'generated_vehicles':demand_meta['vehicle_count'],**m})
fields=list(rows[0].keys())
with open(outroot/'per_seed_metrics.csv','w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
# aggregate mean/std without pandas
import statistics, math
numeric=[k for k in fields if k not in ('controller','seed')]
agg=[]
for c in cfg['controllers']:
    rs=[r for r in rows if r['controller']==c]
    row={'controller':c,'n_seeds':len(rs)}
    for k in numeric:
        vals=[float(r[k]) for r in rs if not math.isnan(float(r[k]))]
        row[k+'_mean']=statistics.mean(vals) if vals else float('nan')
        row[k+'_std']=statistics.stdev(vals) if len(vals)>1 else 0.0
    agg.append(row)
with open(outroot/'aggregate_metrics.csv','w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(agg[0].keys())); w.writeheader(); w.writerows(agg)
(outroot/'experiment_manifest.json').write_text(json.dumps({'config':cfg,'config_path':str(Path(a.config).resolve())},indent=2),encoding='utf-8')
print(outroot)
