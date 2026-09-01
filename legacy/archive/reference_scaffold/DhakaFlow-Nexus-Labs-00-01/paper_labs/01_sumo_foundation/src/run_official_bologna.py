from __future__ import annotations
from pathlib import Path
import argparse, subprocess, json, shutil
from .metrics import parse_tripinfo


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--scenario', required=True)
    ap.add_argument('--out', required=True)
    args=ap.parse_args()
    scenario=Path(args.scenario); out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    configs=sorted(scenario.glob('*.sumocfg'))
    if not configs:
        configs=sorted(scenario.rglob('*.sumocfg'))
    if not configs:
        raise FileNotFoundError(f'No .sumocfg under {scenario}')
    # Prefer the canonical run config when present, otherwise require Claude to inspect choice.
    config=next((p for p in configs if p.name=='run.sumocfg'), configs[0])
    tripinfo=out/'tripinfo.xml'; summary=out/'summary.xml'; log=out/'sumo.log'
    cmd=['sumo','-c',str(config),'--tripinfo-output',str(tripinfo),'--summary-output',str(summary),
         '--log',str(log),'--no-step-log','true']
    print('RUNNING', ' '.join(map(str,cmd)))
    subprocess.run(cmd,cwd=config.parent,check=True)
    metrics=parse_tripinfo(tripinfo)
    (out/'metrics.json').write_text(json.dumps({'config':str(config),'metrics':metrics},indent=2))
    print(json.dumps(metrics,indent=2))

if __name__=='__main__': main()
