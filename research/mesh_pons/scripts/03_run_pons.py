"""PONS (unchanged, pons-dtn from pip) on the exported city movement: one run per router and seed.

Adapter note. pons.Ns2Movement.from_file cannot read a SUMO trace: it divides by the setdest
speed, and a stopped vehicle has speed 0 (ZeroDivisionError, evidence/ns2_reader_failure.log).
SUMO's traceExporter writes one line per vehicle per second, `$ns_ at <t> "$node_(i) setdest <x> <y> <v>"`,
where (x, y) is the vehicle's position at <t>. This script translates those lines one-to-one into
the move tuples PONS's engine consumes, (t, node, x, y, 0). No position, time or PONS code is changed.

Second adapter note. pons.routing.SprayAndWaitRouter.add writes msg.metadata["copies"], but
pons.message_event_generator creates messages with metadata=None, so Spray and Wait raises
TypeError on the first message (evidence/spray_and_wait_failure.log; same code at tag 0.2.1 and at
master 90a6a35). For Spray and Wait only, messages come from `generator_with_metadata` below: the
same statements and the same random draws in the same order as PONS's generator for our fixed
settings, with metadata={} added. Epidemic and PRoPHET use PONS's own generator; both are also run
through the adapter generator and must give identical statistics (evidence/generator_equivalence.json).
"""
import argparse, hashlib, io, json, logging, random, re, sys, time
from pathlib import Path

import yaml
import pons
import pons.routing

HERE = Path(__file__).resolve().parents[1]
SETDEST = re.compile(r'^\$ns_ at ([\d.eE+-]+) "\$node_\((\d+)\) setdest ([\d.eE+-]+) ([\d.eE+-]+) ([\d.eE+-]+)"')


def read_ns2(path: Path):
    moves, nodes = [], set()
    for line in open(path):
        m = SETDEST.match(line)
        if m:
            moves.append((float(m[1]), int(m[2]), float(m[3]), float(m[4]), 0))
            nodes.add(int(m[2]))
        elif not line.startswith("$node_("):
            raise SystemExit(f"unexpected ns2 line: {line!r}")
    assert nodes == set(range(len(nodes))), "node ids are not 0..n-1"
    return sorted(moves, key=lambda m: m[0]), len(nodes)


def generator_with_metadata(netsim, cfg):
    """pons.message_event_generator for fixed interval/size/ttl and tuple src/dst, plus metadata={}."""
    env, counter = netsim.env, 0
    while True:
        if env.now >= netsim.duration:
            break
        yield env.timeout(cfg["interval"])
        netsim.routing_stats["created"] += 1
        counter += 1
        src = random.randint(cfg["src"][0], cfg["src"][1] - 1)
        dst = random.randint(cfg["dst"][0], cfg["dst"][1] - 1)
        msg = pons.Message("%s%d" % (cfg["id"], counter), src, dst, cfg["size"], env.now, ttl=cfg["ttl"],
                           src_service=0, dst_service=0, metadata={})
        netsim.nodes[src].router.add(msg)


def make_router(name: str):
    if name == "epidemic":
        return pons.routing.EpidemicRouter()
    if name == "spray_and_wait":
        return pons.routing.SprayAndWaitRouter()
    if name == "prophet":
        return pons.routing.PRoPHETRouter()
    raise SystemExit(f"unknown router {name}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(HERE / "configs/dhaka.yaml"))
    a = ap.parse_args()
    exp = yaml.safe_load(open(a.config))
    city = exp["city_id"]
    movement = json.loads((HERE / "evidence/movement.json").read_text())
    if movement["city"] != city:
        raise SystemExit(f"no data for this city: evidence/movement.json is for {movement['city']}, not {city}")
    trace = HERE / movement["ns2_trace"]
    if hashlib.sha256(trace.read_bytes()).hexdigest() != movement["ns2_trace_sha256"]:
        raise SystemExit("ns2 trace does not match the hash recorded at export")
    moves, n = read_ns2(trace)
    duration = exp["window"]["end_s"] - exp["window"]["begin_s"]
    world = (max(m[2] for m in moves) + 50, max(m[3] for m in moves) + 50)
    out = HERE / "evidence/runs"
    out.mkdir(parents=True, exist_ok=True)

    def run_one(rname, seed, adapter_generator):
        buf = io.StringIO()
        handler = logging.StreamHandler(buf)
        logging.getLogger().addHandler(handler)
        random.seed(seed)
        router = make_router(rname)
        net = pons.NetworkSettings(exp["radio"]["name"], range=exp["radio"]["range_m"])
        nodes = pons.generate_nodes(n, net=[net], router=router)
        msggen = {"type": "single", "interval": exp["messages"]["interval_s"], "src": (0, n), "dst": (0, n),
                  "size": exp["messages"]["size_bytes"], "id": "M", "ttl": exp["messages"]["ttl_s"]}
        netsim = pons.NetSim(duration, nodes, world_size=world, movements=list(moves),
                             config={"movement_logger": False, "peers_logger": False, "event_logging": False},
                             msggens=[] if adapter_generator else [msggen])
        netsim.setup()
        if adapter_generator:
            netsim.env.process(generator_with_metadata(netsim, msggen))
        t0 = time.time()
        stdout, sys.stdout = sys.stdout, io.StringIO()      # PONS prints a progress bar
        try:
            netsim.run()
        finally:
            sys.stdout = stdout
            logging.getLogger().removeHandler(handler)
        rec = {"label": "SIMULATED", "city": city, "router": rname, "router_str": str(router), "seed": seed,
               "message_generator": "adapter generator_with_metadata (metadata={})" if adapter_generator else "pons.message_event_generator",
               "nodes": n, "duration_s": duration, "radio": exp["radio"], "messages": exp["messages"],
               "ns2_trace_sha256": movement["ns2_trace_sha256"], "pons_version": "pons-dtn 0.2.1",
               "routing_stats": netsim.routing_stats, "net_stats": netsim.net_stats}
        return rec, buf.getvalue(), round(time.time() - t0, 2)

    equivalence = []
    for rname in exp["routers"]:
        for seed in exp["seeds"]:
            needs_adapter = rname == "spray_and_wait"
            rec, log, wall = run_one(rname, seed, needs_adapter)
            (out / f"{rname}_seed{seed}.json").write_text(json.dumps(rec, indent=1))
            (out / f"{rname}_seed{seed}.log").write_text(log)
            if not needs_adapter:
                other, _, _ = run_one(rname, seed, True)
                same = other["routing_stats"] == rec["routing_stats"] and other["net_stats"] == rec["net_stats"]
                equivalence.append({"router": rname, "seed": seed, "identical_stats": same})
            s = rec["routing_stats"]
            print(f"{rname} seed {seed}: created {s['created']} delivered {s['delivered']} relayed {s['relayed']} ({wall} s)")
    (HERE / "evidence/generator_equivalence.json").write_text(json.dumps(equivalence, indent=1))
    if not all(e["identical_stats"] for e in equivalence):
        raise SystemExit("adapter generator does NOT reproduce PONS's generator; Spray and Wait results are not usable")
    print("adapter generator reproduces PONS's generator on", len(equivalence), "runs")


if __name__ == "__main__":
    main()
