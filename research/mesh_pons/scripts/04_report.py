"""RESULTS.md from the run JSONs in evidence/runs only. Every number is SIMULATED."""
import json, statistics, subprocess
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parents[1]
NAMES = {"epidemic": "Epidemic", "spray_and_wait": "Spray and Wait (7 copies, non-binary)", "prophet": "PRoPHET (PONS defaults)"}


def stats_line(vals, fmt):
    if not vals:
        return "no deliveries in any seed"
    m = statistics.mean(vals)
    sd = statistics.stdev(vals) if len(vals) > 1 else 0.0
    return f"{fmt(m)} ± {fmt(sd)} (min {fmt(min(vals))}, max {fmt(max(vals))}, n={len(vals)})"


def upstream_block(path, title):
    txt = path.read_text().replace("\r", "\n")
    j = txt[txt.rindex("{\n    \"created\""):]
    j = j[: j.index("}") + 1]
    return f"{title}\n```json\n{j}\n```\n"


def main():
    exp = yaml.safe_load(open(HERE / "configs/dhaka.yaml"))
    mov = json.loads((HERE / "evidence/movement.json").read_text())
    eq = json.loads((HERE / "evidence/generator_equivalence.json").read_text())
    runs = {}
    for p in sorted((HERE / "evidence/runs").glob("*.json")):
        r = json.loads(p.read_text())
        assert r["ns2_trace_sha256"] == mov["ns2_trace_sha256"], p
        runs.setdefault(r["router"], []).append(r)
    rows, per_seed = [], []
    for rname in exp["routers"]:
        rs = sorted(runs[rname], key=lambda r: r["seed"])
        assert [r["seed"] for r in rs] == exp["seeds"], rname
        dr = [r["routing_stats"]["delivery_prob"] for r in rs]
        delay = [r["routing_stats"]["latency_avg"] for r in rs if r["routing_stats"]["delivered"] > 0]
        copies = [r["routing_stats"]["relayed"] / r["routing_stats"]["created"] for r in rs]
        ovh = [r["routing_stats"]["overhead_ratio"] for r in rs if r["routing_stats"]["delivered"] > 0]
        no_deliv = len(rs) - len(delay)
        rows.append(f"| {NAMES[rname]} | {stats_line(dr, lambda v: f'{v:.3f}')} | {stats_line(delay, lambda v: f'{v:.1f}')}"
                    f"{' ; ' + str(no_deliv) + ' seed(s) with no deliveries' if no_deliv else ''} | "
                    f"{stats_line(copies, lambda v: f'{v:.2f}')} | {stats_line(ovh, lambda v: f'{v:.1f}')} |")
        for r in rs:
            s = r["routing_stats"]
            delay_s = f"{s['latency_avg']:.1f}" if s["delivered"] else "no deliveries"
            per_seed.append(f"| {NAMES[rname]} | {r['seed']} | {s['created']} | {s['delivered']} | {s['delivery_prob']:.3f} | {delay_s} | "
                            f"{s['relayed']} | {s['relayed']/s['created']:.2f} | {s['started']} | {s['dups']} | {s['hops_avg']:.2f} |")
    pip = (HERE / "evidence/pip_freeze.txt").read_text().strip().replace("\n", ", ")
    commit = (HERE / "evidence/upstream_commit.txt").read_text().strip()
    src = exp["radio"]["source"]
    text = f"""# Mesh prototype: PONS on Dhaka SUMO movement — SIMULATED results

**Every number on this page is SIMULATED.** Nothing here is a measurement of Dhaka. The demand is
synthetic and uncalibrated, the radio is an ideal disc, and only {mov['vehicles_kept_present_whole_window']} vehicles take part (see
Scope). The app reads these files through `core/networking/mesh/results.py` (Offline alerts page and Lab → Evidence; 2026-10-06).

## Scope and provenance

| item | value |
|---|---|
| city / dataset | Dhaka, frozen SUMO network `{mov['network']}` (OpenStreetMap -> netconvert, uncompressed sha256 `{mov['network_sha256_uncompressed_in_city_config']}` per `config/cities/dhaka.yaml`); read only, never changed |
| demand | SYNTHETIC, UNCALIBRATED: SUMO `randomTrips.py`, seed {mov['demand']['seed']}, one departure every {mov['demand']['period_s']} s, {mov['demand']['horizon_s']} s, the `sumo.build` values of the city config, same options as `core/simulation/twin/scenario_builder.py`; routes sha256 `{mov['routes_sha256']}` |
| SUMO | {mov['sumo_version']}, default passenger-car model, seed {mov['demand']['seed']} |
| movement window | SUMO seconds {mov['window_s'][0]}-{mov['window_s'][1]} ({mov['window_steps']} steps), fixed before any result was seen; exported with SUMO's `traceExporter.py --ns2mobility-output`; ns2 trace sha256 `{mov['ns2_trace_sha256']}` |
| vehicles | {mov['vehicles_seen_in_window']} vehicles appear in the window; **{mov['vehicles_kept_present_whole_window']} are present at every step and only those are simulated** (why: below) |
| simulator | PONS `pons-dtn` {pip.split('pons-dtn==')[1].split(',')[0]} from PyPI (identical to git tag 0.2.1 = `{commit}`), MIT licence; run on Python 3.11 |
| radio | one interface per vehicle, `range = {exp['radio']['range_m']} m`, ideal disc, no loss model beyond PONS's own. Source of the value: {src} |
| messages | PONS's own generator: one message per {exp['messages']['interval_s']} s, random source and destination among the simulated vehicles, {exp['messages']['size_bytes']} bytes, TTL {exp['messages']['ttl_s']} s; so {exp['messages']['ttl_s'] // exp['messages']['interval_s']} messages per run |
| routers | PONS defaults: `EpidemicRouter()`, `SprayAndWaitRouter()` (7 copies, non-binary), `PRoPHETRouter()` (`PRoPHETConfig()` defaults); scan interval 2 s, unlimited buffer |
| seeds | {exp['seeds']} per router = {len(exp['seeds']) * len(exp['routers'])} runs. The seed changes which vehicles send to which and when; **the movement trace is the same in every run**, so the spread is over message draws, not over traffic |
| evidence | `evidence/runs/<router>_seed<k>.json` (PONS statistics verbatim) + `.log`, `evidence/movement.json`, `evidence/SHA256SUMS` |

## Results (SIMULATED), mean ± sample standard deviation over {len(exp['seeds'])} seeds

| router | delivery ratio (SIMULATED) | delay of delivered messages, s (SIMULATED) | copies: relayed transfers per created message (SIMULATED) | PONS overhead ratio (SIMULATED) |
|---|---|---|---|---|
""" + "\n".join(rows) + f"""

Definitions, all taken verbatim from PONS's `routing_stats`: delivery ratio = `delivery_prob` =
delivered / created; delay = `latency_avg`, the mean of (delivery time - creation time) over
delivered messages only, so seeds without deliveries carry no delay; copies = `relayed` / `created`,
where `relayed` counts every successful message transfer between two vehicles (including the final
hop); overhead ratio = PONS's (`relayed` - `delivered`) / `delivered`.

### Per seed (SIMULATED)

| router | seed | created | delivered | delivery ratio | delay s | relayed | relayed/created | started | dups | hops avg |
|---|---|---|---|---|---|---|---|---|---|---|
""" + "\n".join(per_seed) + f"""

### Reading these numbers

- With {mov['vehicles_kept_present_whole_window']} vehicles spread over a 5.8 x 5.5 km network and a 10 m radio, contacts are rare; most
  messages never meet their destination within the 300 s TTL. Delivery ratios of a few percent are
  the consequence of this setup, not a property of Dhaka traffic.
- PONS's PRoPHET (default `PRoPHETConfig`) forwards to a peer only if that peer's delivery
  predictability for the destination exceeds the sender's own. In this sparse window it never did:
  `relayed` equals `delivered` in every seed, i.e. all PRoPHET deliveries are direct source-to-
  destination contacts, and PRoPHET's delivery ratio is then the direct-contact rate.
- Spray and Wait (7 copies) and Epidemic reach the same destinations through more transfers;
  Epidemic spends the most copies.

### Why only {mov['vehicles_kept_present_whole_window']} of {mov['vehicles_seen_in_window']} vehicles

PONS's ns2 model (`pons.Ns2Movement`) parks a node at its first position before its first entry
and at its last position after its last entry. A vehicle that departs or arrives inside the window
would therefore sit as a stationary relay that does not exist in the SUMO run. Keeping only vehicles
present at every step of the window avoids that artefact at the cost of a small, long-trip-biased
sample. A follow-up that models vehicles entering and leaving (PONS has no node on/off switch in
its ns2 path) is noted in README.md; it is not done here.

### Our adapter code, and why (please read)

1. **ns2 -> PONS movement adapter is our code** (`scripts/03_run_pons.py`, `read_ns2`). PONS's own
   ns2 reader, `pons.Ns2Movement.from_file`, divides by the `setdest` speed and a stopped vehicle has
   speed 0, so it raises `ZeroDivisionError` on this trace (`evidence/ns2_reader_failure.log`).
   The adapter reads the same ns2 file written by SUMO's traceExporter and turns each
   `$ns_ at t "$node_(i) setdest x y v"` line into PONS's native move tuple `(t, i, x, y, 0)`,
   which is what PONS's own movement manager consumes. No position or time is changed, and PONS
   itself is not modified.
2. **Message generator with `metadata={{}}`, for Spray and Wait only.** PONS 0.2.1's
   `SprayAndWaitRouter.add` writes `msg.metadata["copies"]`, but PONS's own message generator
   creates messages with `metadata=None`, so Spray and Wait crashes on its first message
   (`evidence/spray_and_wait_failure.log`; the code is the same at master `90a6a35`). Our
   `generator_with_metadata` repeats PONS's generator statements and random draws for our fixed
   settings and adds `metadata={{}}`. Check: Epidemic and PRoPHET were each run twice per seed, with
   PONS's generator and with ours; all {len(eq)} pairs gave identical statistics
   (`evidence/generator_equivalence.json`, identical = {all(e['identical_stats'] for e in eq)}).
3. **Upstream examples ran on Python 3.11.** Run unchanged on Python 3.13 they crash
   (`random.randint` with a float `max_pause`, `evidence/upstream_sim_python313_failure.log`), so the
   venv uses Python 3.11.

## Upstream examples, unchanged (step 2 of the task)

PONS publishes no reference numbers for its examples, so there is nothing to compare against; the
outputs below are ours, saved for the record (`evidence/upstream_sim.log`, `evidence/upstream_ext_ns2.log`).

""" + upstream_block(HERE / "evidence/upstream_sim.log", "`sim.py` (README example: 10 random-waypoint nodes, Epidemic, 24 h, seed 42) — SIMULATED:") + "\n" + upstream_block(HERE / "evidence/upstream_ext_ns2.log", "`examples/ext_ns2.py` (PONS's own ns2 test trace, Epidemic) — SIMULATED:") + """
Environment: `evidence/pip_freeze.txt`. All evidence hashes: `evidence/SHA256SUMS`.
"""
    (HERE / "RESULTS.md").write_text(text)
    files = sorted(str(f.relative_to(HERE)) for pat in ("evidence/*.log", "evidence/*.json", "evidence/*.txt", "evidence/runs/*",
                   "configs/*", "scripts/*.py", "scripts/*.sh", "work/*.ns2.tcl", "work/*.rou.xml", "work/*.window.fcd.xml")
                   for f in HERE.glob(pat) if f.is_file())
    out = subprocess.run(["shasum", "-a", "256"] + files, cwd=HERE, check=True, capture_output=True, text=True).stdout
    (HERE / "evidence/SHA256SUMS").write_text(out)
    print("\n".join(rows))


if __name__ == "__main__":
    main()
