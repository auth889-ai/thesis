from pathlib import Path
import csv, json, os, sys, time
from .controllers import CONTROLLERS
from .controllers.base import ControllerConfig

INBOUND_LANES=("N2C_0","S2C_0","E2C_0","W2C_0")


def _import_traci():
    try:
        import traci
        return traci
    except ImportError:
        sumo_home=os.environ.get("SUMO_HOME")
        if sumo_home:
            sys.path.append(str(Path(sumo_home)/"tools"))
            import traci
            return traci
        raise


def run_one(sumo_binary, sumocfg, route_file, output_dir, controller_name, seed, sim_end, controller_cfg):
    traci=_import_traci()
    output_dir=Path(output_dir); output_dir.mkdir(parents=True,exist_ok=True)
    tripinfo=output_dir/'tripinfo.xml'
    summary=output_dir/'summary.xml'
    log=output_dir/'sumo.log'
    step_csv=output_dir/'step_metrics.csv'
    action_jsonl=output_dir/'controller_actions.jsonl'
    cmd=[str(sumo_binary),'-c',str(sumocfg),'--route-files',str(route_file),'--end',str(sim_end),
         '--seed',str(seed),'--tripinfo-output',str(tripinfo),'--summary-output',str(summary),
         '--log',str(log),'--no-step-log','true']
    traci.start(cmd)
    cfg=ControllerConfig(**controller_cfg)
    controller=CONTROLLERS[controller_name](cfg)
    controller.reset(traci)
    started=time.time()
    with open(step_csv,'w',newline='',encoding='utf-8') as fcsv, open(action_jsonl,'w',encoding='utf-8') as fact:
        writer=csv.DictWriter(fcsv,fieldnames=['time','total_halting','max_halting','max_queue_ratio','running','arrived'])
        writer.writeheader()
        while traci.simulation.getTime() < sim_end:
            traci.simulationStep()
            t=float(traci.simulation.getTime())
            action=controller.step(traci,t)
            if action and action.get('action') not in ('observe','hold_between_decisions','transition'):
                fact.write(json.dumps({'time':t,'controller':controller_name,**action})+'\n')
            qs=[]; ratios=[]
            for lane in INBOUND_LANES:
                q=float(traci.lane.getLastStepHaltingNumber(lane)); qs.append(q)
                length=max(float(traci.lane.getLength(lane)),1.0)
                ratios.append(min(1.5, q*7.5/length))
            writer.writerow({
                'time':t,'total_halting':sum(qs),'max_halting':max(qs) if qs else 0,
                'max_queue_ratio':max(ratios) if ratios else 0,
                'running':traci.vehicle.getIDCount(),'arrived':traci.simulation.getArrivedNumber(),
            })
    traci.close()
    manifest={'command':cmd,'controller':controller_name,'seed':seed,'runtime_seconds':time.time()-started,
              'tripinfo':str(tripinfo),'step_metrics':str(step_csv)}
    (output_dir/'run_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return manifest
