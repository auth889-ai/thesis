from __future__ import annotations
from pathlib import Path
import csv
import statistics
import xml.etree.ElementTree as ET


def parse_tripinfo(path):
    root = ET.parse(path).getroot()
    trips = root.findall('tripinfo')
    if not trips:
        return {"completed_trips": 0}
    vals = lambda key: [float(t.attrib.get(key, 0.0)) for t in trips]
    duration, waiting, time_loss = vals('duration'), vals('waitingTime'), vals('timeLoss')
    duration_sorted = sorted(duration)
    p95 = duration_sorted[min(len(duration_sorted)-1, int(round(.95*(len(duration_sorted)-1))))]
    return {
        "completed_trips": len(trips),
        "mean_trip_duration_s": statistics.mean(duration),
        "p95_trip_duration_s": p95,
        "mean_waiting_time_s": statistics.mean(waiting),
        "mean_time_loss_s": statistics.mean(time_loss),
    }


def parse_queue_csv(path):
    rows = list(csv.DictReader(open(path)))
    if not rows:
        return {"mean_total_queue": 0.0, "max_total_queue": 0.0}
    totals = [float(r['ns_in_queue']) + float(r['ew_in_queue']) for r in rows]
    return {
        "mean_total_queue": statistics.mean(totals),
        "max_total_queue": max(totals),
    }


def combined_metrics(tripinfo, queue_csv):
    return {**parse_tripinfo(tripinfo), **parse_queue_csv(queue_csv)}
