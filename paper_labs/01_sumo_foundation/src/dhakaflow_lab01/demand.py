from dataclasses import dataclass
from pathlib import Path
import random
import xml.etree.ElementTree as ET

@dataclass(frozen=True)
class DemandPeriod:
    begin: float
    end: float
    ns_vph_each: float
    ew_vph_each: float

ROUTES = {
    "ns": ("N2C C2S", "car_ns"),
    "sn": ("S2C C2N", "car_sn"),
    "ew": ("E2C C2W", "car_ew"),
    "we": ("W2C C2E", "car_we"),
}

def _arrivals(rng, begin, end, vph):
    if vph <= 0:
        return []
    rate = vph / 3600.0
    t = float(begin)
    out=[]
    while True:
        t += rng.expovariate(rate)
        if t >= end:
            break
        out.append(t)
    return out

def generate_route_file(path, seed, periods, sigma=0.3):
    rng=random.Random(int(seed))
    root=ET.Element("routes")
    ET.SubElement(root,"vType", id="car", accel="2.6", decel="4.5", sigma=str(sigma), length="5", minGap="2.5", maxSpeed="13.89")
    for rid,(edges,_) in ROUTES.items():
        ET.SubElement(root,"route", id=rid, edges=edges)
    vehicles=[]
    seq=0
    for period in periods:
        for rid, vph in [("ns",period.ns_vph_each),("sn",period.ns_vph_each),("ew",period.ew_vph_each),("we",period.ew_vph_each)]:
            for t in _arrivals(rng, period.begin, period.end, vph):
                vehicles.append((t,seq,rid)); seq+=1
    vehicles.sort()
    for t,seq,rid in vehicles:
        ET.SubElement(root,"vehicle", id=f"v{seq:06d}", type="car", route=rid, depart=f"{t:.2f}", departLane="best", departSpeed="max")
    tree=ET.ElementTree(root)
    ET.indent(tree, space="  ")
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    tree.write(path,encoding="utf-8",xml_declaration=True)
    return {"seed":int(seed),"vehicle_count":len(vehicles),"path":str(path)}
