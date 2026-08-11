from pathlib import Path
import csv, math, statistics
import xml.etree.ElementTree as ET


def percentile(xs, p):
    xs=sorted(float(x) for x in xs)
    if not xs: return float('nan')
    if len(xs)==1: return xs[0]
    k=(len(xs)-1)*(p/100.0)
    f=math.floor(k); c=math.ceil(k)
    if f==c: return xs[int(k)]
    return xs[f]*(c-k)+xs[c]*(k-f)


def parse_tripinfo(path):
    root=ET.parse(path).getroot()
    trips=[]
    for t in root.findall('tripinfo'):
        def g(name, default=0.0):
            try: return float(t.attrib.get(name, default))
            except (TypeError,ValueError): return float(default)
        trips.append({
            "duration":g("duration"),
            "waitingTime":g("waitingTime"),
            "timeLoss":g("timeLoss"),
            "departDelay":g("departDelay"),
            "waitingCount":g("waitingCount"),
        })
    return trips


def parse_step_metrics(path):
    with open(path,newline='',encoding='utf-8') as f:
        return list(csv.DictReader(f))


def aggregate_metrics(tripinfo_path, step_metrics_path):
    trips=parse_tripinfo(tripinfo_path)
    steps=parse_step_metrics(step_metrics_path)
    durations=[x['duration'] for x in trips]
    waits=[x['waitingTime'] for x in trips]
    losses=[x['timeLoss'] for x in trips]
    stops=[x['waitingCount'] for x in trips]
    queues=[float(r['total_halting']) for r in steps] if steps else []
    spill=[float(r['max_queue_ratio'])>=0.8 for r in steps] if steps else []
    return {
        "throughput":len(trips),
        "avg_travel_time":statistics.mean(durations) if durations else float('nan'),
        "p95_travel_time":percentile(durations,95),
        "avg_waiting_time":statistics.mean(waits) if waits else float('nan'),
        "avg_time_loss":statistics.mean(losses) if losses else float('nan'),
        "avg_stops_proxy":statistics.mean(stops) if stops else float('nan'),
        "mean_queue":statistics.mean(queues) if queues else float('nan'),
        "p95_queue":percentile(queues,95),
        "max_queue":max(queues) if queues else float('nan'),
        "spillback_proxy_fraction":sum(spill)/len(spill) if spill else float('nan'),
    }
