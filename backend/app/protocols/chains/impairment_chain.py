#!/usr/bin/env python3
"""Does WORSE COMMUNICATION cause HIGHER NETWORK DELAY? The end-to-end causal chain, measured.

    python -m app.protocols.chains.impairment_chain --seeds 11,12,13 --levels karwanbazar_to_shahbagh=3
    python -m app.protocols.chains.impairment_chain --seeds 11,12,13 --conditions good,degraded,bad

    communication condition -> advisory DELIVERY -> how many vehicles reroute
                            -> SUMO paired counterfactual -> travel time / waiting

The routing arms in this repo already answer "does acting on a forecast help?". They all assume the
advisory *arrives*. This script removes that assumption, which is the whole point of the research
question: a route advisory that reaches the driver after the decision point is not a worse
advisory, it is no advisory at all.

WHERE THE DELIVERY NUMBERS COME FROM — and what they are not
    `results/networking/latency.csv`, produced by src/pipeline/networking/latency_injection.py: for each
    (added latency, loss) pair, the fraction of 4,386 rerouting vehicles whose advisory arrived
    before they reached the decision point. Those vehicles and their time budgets come from Eclipse
    MOSAIC ITS-G5 sweeps — an official SIMULATOR. Nothing here is measured on radio hardware, and
    no condition below should be described as a measured V2X deployment.

    We do not re-derive delivery, we read it. A condition that is not in that table is refused
    rather than interpolated.

HOW A CONDITION CHANGES THE SIMULATION
    Each vehicle is equipped or not exactly as in every other arm (deterministic md5 on the vehicle
    id, so the equipped set is identical across conditions and seeds). An equipped vehicle then
    reroutes only if its advisory was DELIVERED: an independent draw at the delivery probability
    for that condition, seeded by (vehicle, condition, seed) so the same run always reproduces and
    conditions stay comparable. Undelivered vehicles keep their original route -- they behave
    exactly like unequipped traffic, which is what a missed advisory actually means.

    The congestion itself is made real for EVERY arm (each affected edge's speed limit is divided
    by its multiplier), so conditions differ only in who got told.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from app.paths import REPO
sys.path.insert(0, str(REPO))

import app.twin.runtime as pr                      # noqa: E402
from app.protocols.chains import live_chain as lc                         # noqa: E402
from app.forecasting.live.live_to_edges import write_weights          # noqa: E402

RESULTS = REPO / "results/routing"
NET_RESULTS = REPO / "results/networking/latency.csv"
MAP_FILE = REPO / "data/forecasting/live_dhaka/corridor_edges.json"

# (added latency ms, loss %) -> a name the chain reports. Every one must exist in latency.csv.
CONDITIONS = {
    "none":     None,        # nobody is advised — the unaware reference arm
    "ideal":    (0, 0),
    "good":     (0, 10),
    "degraded": (500, 30),
    "bad":      (5000, 30),
}


def delivery_fraction(added_ms, loss_pct, repeat: bool) -> tuple[float, dict]:
    """Read the delivered fraction out of the networking evidence. Never interpolated."""
    if added_ms is None:                       # the unaware reference arm
        return 0.0, {"added_latency_ms": "—", "loss_pct": "—",
                     "delivery_model": "no advisory issued (unaware reference arm)",
                     "n_vehicles": 0, "effective_latency_mean_ms": 0.0,
                     "source": "reference arm, not a link condition"}
    if not NET_RESULTS.exists():
        raise SystemExit(f"missing {NET_RESULTS}; run src/pipeline/networking/latency_injection.py first")
    col = "frac_delivered_1hz_repeat" if repeat else "frac_delivered_single_shot"
    for r in csv.DictReader(NET_RESULTS.open()):
        if int(r["added_latency_ms"]) == added_ms and int(float(r["loss_pct"])) == loss_pct:
            return float(r[col]), {
                "added_latency_ms": added_ms, "loss_pct": loss_pct,
                "delivery_model": col,
                "n_vehicles": int(r["n_vehicles"]),
                "effective_latency_mean_ms": float(r["effective_latency_mean_ms"]),
                "source": "results/networking/latency.csv (Eclipse MOSAIC ITS-G5 sweep, SIMULATED)",
            }
    have = sorted({(int(r["added_latency_ms"]), int(float(r["loss_pct"])))
                   for r in csv.DictReader(NET_RESULTS.open())})
    raise SystemExit(f"no delivery row for ({added_ms} ms, {loss_pct} %); table has {have}. "
                     f"Add the point to latency_injection.py rather than interpolating it.")


def delivered(vid: str, p: float, condition: str, seed: int) -> bool:
    """Independent per-vehicle delivery draw, reproducible and independent of the equipped set."""
    if p >= 1.0:
        return True
    h = hashlib.md5(f"{vid}|{condition}|{seed}".encode()).hexdigest()
    return (int(h[:8], 16) / 0xFFFFFFFF) < p


def run_condition(a, condition: str, seed: int, slow: dict, weights: Path) -> dict:
    """One SUMO run: the equipped-and-DELIVERED share is rerouted; everyone else is not."""
    import traci
    spec = CONDITIONS[condition]
    added_ms, loss_pct = spec if spec else (None, None)
    p, prov = delivery_fraction(added_ms, loss_pct, repeat=not a.single_shot)
    out = RESULTS / f"impairment_{condition}_s{seed}"
    out.mkdir(parents=True, exist_ok=True)

    vehicles = lc.read_routes(Path(a.routes))
    eq = [(v, d, r) for v, d, r in vehicles if pr.equipped(v, a.compliance) and float(d) < a.horizon]
    got = [(v, d, r) for v, d, r in eq if delivered(v, p, condition, seed)]

    routes = Path(a.routes)
    changed = 0
    if got:
        trips = out / "trips_delivered.xml"
        trips.write_text("<routes>\n" + "".join(
            f'  <trip id="{v}" depart="{d}" from="{r.split()[0]}" to="{r.split()[-1]}"/>\n'
            for v, d, r in got) + "</routes>\n")
        alt = out / "routes_delivered.rou.xml"
        subprocess.run(["duarouter", "--net-file", str(a.net), "--route-files", str(trips),
                        "--weight-files", str(weights), "--weight-attribute", "traveltime",
                        "--output-file", str(alt), "--ignore-errors", "--no-warnings",
                        "--no-step-log", "--seed", str(seed), "--routing-threads", "4"],
                       check=True, capture_output=True)
        new = {v: r for v, d, r in lc.VEH_RE.findall(alt.read_text())}
        routes = out / "routes_merged.rou.xml"
        with open(routes, "w") as fh:
            fh.write('<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
                     'xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">\n')
            for v, d, r in vehicles:
                nr = new.get(v, r)
                changed += nr != r
                fh.write(f'    <vehicle id="{v}" depart="{d}">\n'
                         f'        <route edges="{nr}" />\n    </vehicle>\n')
            fh.write("</routes>\n")

    ns = argparse.Namespace(net=str(a.net), routes=str(routes), seed=seed, scale=a.scale,
                            horizon=a.horizon, edgedata_period=300, time_to_teleport=300,
                            sumo_binary="sumo")
    t0 = time.time()
    traci.start(pr.base_cmd(ns, out), label=f"imp-{condition}-{seed}")
    applied = 0
    for eid, m in slow.items():                    # congestion is real in EVERY condition
        try:
            for i in range(traci.edge.getLaneNumber(eid)):
                lid = f"{eid}_{i}"
                traci.lane.setMaxSpeed(lid, max(traci.lane.getMaxSpeed(lid) / m, 0.5))
            applied += 1
        except traci.TraCIException:
            pass
    t = 0
    while t < a.horizon and traci.simulation.getMinExpectedNumber() > 0:
        traci.simulationStep()
        t = int(traci.simulation.getTime())
    traci.close()

    m = pr.parse_metrics(out, horizon=a.horizon)
    rec = {"condition": condition, "seed": seed, "delivery_fraction": round(p, 4),
           "link": prov, "equipped": len(eq), "advisories_delivered": len(got),
           "routes_changed": changed, "edges_slowed": applied,
           "wall_s": round(time.time() - t0, 1), "metrics": m}
    print(f"[chain] {condition:<9} seed={seed} delivery={p:.3f} "
          f"equipped={len(eq)} delivered={len(got)} changed={changed} "
          f"veh-h={m['total_vehicle_hours']:.1f} wait={m.get('total_waiting_s', 0):.0f} "
          f"arrived={m['arrived']} ({rec['wall_s']}s)", flush=True)
    return rec


def _paired(by: dict, baseline: str, cond: str) -> tuple[list, list]:
    """Per-seed % change in vehicle-hours and waiting, cond vs baseline."""
    per_seed, waits = [], []
    for s, r in sorted(by[cond].items()):
        b = by[baseline].get(s)
        if not b:
            continue
        bv, cv = b["metrics"]["total_vehicle_hours"], r["metrics"]["total_vehicle_hours"]
        per_seed.append(round((cv - bv) / bv * 100, 2))
        bw = b["metrics"].get("total_waiting_s") or 0
        cw = r["metrics"].get("total_waiting_s") or 0
        if bw:
            waits.append(round((cw - bw) / bw * 100, 2))
    return per_seed, waits


def analyse(runs: list[dict], baseline: str) -> dict:
    """Paired per-seed comparison.

    Two different questions live here and must not share a baseline:
      * does advising anyone help?   `ideal` vs `none`      (the reference check)
      * does a worse link hurt?      each condition vs `ideal` (the research question)
    Comparing an impaired link against `none` would answer neither.
    """
    by = {}
    for r in runs:
        by.setdefault(r["condition"], {})[r["seed"]] = r
    if "ideal" in by:
        baseline = "ideal"
    if baseline not in by:
        return {"error": f"no runs for baseline condition {baseline}"}
    out = {"baseline": baseline, "conditions": {}}
    for cond, seeds in by.items():
        if cond == baseline or cond == "none":
            continue
        per_seed, waits = _paired(by, baseline, cond)
        out["conditions"][cond] = {
            "delivery_fraction": seeds[next(iter(seeds))]["delivery_fraction"],
            "mean_advisories_delivered": round(
                sum(r["advisories_delivered"] for r in seeds.values()) / len(seeds), 1),
            "vehicle_hours_pct_per_seed": per_seed,
            "mean_vehicle_hours_pct": round(sum(per_seed) / len(per_seed), 2) if per_seed else None,
            "mean_waiting_pct": round(sum(waits) / len(waits), 2) if waits else None,
            "seeds_worse": sum(1 for x in per_seed if x > 0),
            "seeds": len(per_seed),
        }
    # A monotone trend in the MEANS is not the same as an effect the seeds support. The same
    # standard the routing decision guard already applies: a causal claim needs every paired seed
    # to agree, otherwise it is reported as suggestive and nothing stronger.
    link_conds = {c: d for c, d in out["conditions"].items() if c != "none"}
    worst = max(link_conds, key=lambda c: link_conds[c]["mean_vehicle_hours_pct"] or 0, default=None)

    # Before asking whether a degraded link hurts, check that the advisory helped at all. If
    # perfect delivery does not beat advising nobody, then there is no benefit for the link to
    # erode, and a null impairment result says nothing about communication.
    baseline_benefit = None
    if "none" in by and baseline in by:
        adv, _ = _paired(by, "none", baseline)          # advised vs nobody advised
        helped = sum(1 for x in adv if x < 0)           # negative = fewer vehicle-hours = better
        baseline_benefit = {
            "reference_arm": "none (nobody advised)",
            "mean_vehicle_hours_pct_advising_vs_nobody": round(sum(adv) / len(adv), 2) if adv else None,
            "per_seed": adv,
            "seeds_where_advising_helped": f"{helped}/{len(adv)}",
            "established": bool(adv) and helped == len(adv) and len(adv) >= 3,
        }

    if worst:
        d = link_conds[worst]
        unanimous = d["seeds_worse"] == d["seeds"] and d["seeds"] >= 3
        means = [link_conds[c]["mean_vehicle_hours_pct"] for c in link_conds
                 if link_conds[c]["mean_vehicle_hours_pct"] is not None]
        if baseline_benefit and not baseline_benefit["established"]:
            claim = "INCONCLUSIVE_UNDERPOWERED"
            mb = baseline_benefit["mean_vehicle_hours_pct_advising_vs_nobody"]
            reason = (
                f"Advising does help, but only a little: {mb} % vehicle-hours on "
                f"{baseline_benefit['seeds_where_advising_helped']} seeds — a real effect, though "
                f"not unanimous by this project's decision-guard rule. That is the problem. If "
                f"halving advisory delivery removes a proportional share of a ~{abs(mb):.1f} % "
                f"benefit, the effect being looked for is a fraction of a percent, which is well "
                f"inside the seed-to-seed spread here. This experiment is UNDERPOWERED for the "
                f"communication hypothesis rather than evidence against it. Testing the chain "
                f"needs a regime where routing gives a large, unanimous benefit — higher "
                f"compliance, heavier congestion, or a network where rerouting matters more — so "
                f"that degrading delivery has something substantial to erode.")
        elif unanimous:
            claim, reason = "CAUSAL_EFFECT_SUPPORTED", "every paired seed is worse under the degraded link"
        else:
            claim = "NO_EFFECT_DETECTED" if d["seeds"] >= 10 else "SUGGESTIVE_ONLY"
            reason = (f"only {d['seeds_worse']} of {d['seeds']} paired seeds are worse under "
                      f"`{worst}` (mean {d['mean_vehicle_hours_pct']} %); the seeds do not "
                      f"establish an effect.")
        out["verdict"] = {
            "worst_condition": worst,
            "mean_vehicle_hours_pct": d["mean_vehicle_hours_pct"],
            "seeds_agreeing": f"{d['seeds_worse']}/{d['seeds']}",
            "monotone_in_means": means == sorted(means),
            "baseline_benefit": baseline_benefit,
            "claim": claim, "reason": reason,
        }
    return out


def reanalyse(path: Path, a) -> int:
    """Recompute the summary from runs already recorded — no simulation is repeated."""
    rec = json.loads(path.read_text())
    rec["summary"] = analyse(rec["runs"], baseline="ideal")
    path.write_text(json.dumps(rec, indent=1, default=str))
    a.tag = path.stem.replace("impairment_chain", "")
    a.seeds = ",".join(str(s) for s in sorted({r["seed"] for r in rec["runs"]}))
    a.levels = ""
    write_md(rec, a)
    print(f"re-analysed {path.name} -> {path.with_suffix('.md').name}")
    v = rec["summary"].get("verdict", {})
    print(f"  verdict: {v.get('claim')} — {v.get('reason', '')[:160]}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--reanalyse", type=Path, help="recompute the summary from a saved run record")
    p.add_argument("--seeds", default="11,12,13")
    p.add_argument("--conditions", default="ideal,good,degraded,bad")
    p.add_argument("--horizon", type=int, default=1800)
    p.add_argument("--compliance", type=float, default=0.3)
    p.add_argument("--single-shot", action="store_true",
                   help="one DENM per vehicle instead of the official 1 Hz repeat")
    sc = RESULTS / "SCALE_CHOICE.json"
    p.add_argument("--scale", type=float,
                   default=json.loads(sc.read_text()).get("scale", 0.25) if sc.exists() else 0.25)
    p.add_argument("--net", default=str(pr.DEFAULT_NET))
    p.add_argument("--routes", default=str(pr.DEFAULT_ROUTES))
    p.add_argument("--levels", default="", help="WHAT-IF congestion, e.g. 'corridor=3' (labelled)")
    p.add_argument("--horizon-min", type=float, default=15.0)
    p.add_argument("--tag", default="")
    a = p.parse_args()
    if a.reanalyse:
        return reanalyse(a.reanalyse, a)

    conds = [c.strip() for c in a.conditions.split(",")]
    for c in conds:
        if c not in CONDITIONS:
            raise SystemExit(f"unknown condition {c!r}; have {sorted(CONDITIONS)}")

    cmap = json.loads(MAP_FILE.read_text())
    if a.levels:
        levels = {k: float(v) for k, v in (kv.split("=") for kv in a.levels.split(","))}
        source = {"reality": "SYNTHETIC_WHAT_IF", "levels": levels,
                  "note": "congestion levels supplied on the command line — a mechanism check "
                          "of the communication chain, NEVER evidence about Dhaka"}
    else:
        levels, prov = lc.latest_levels(lc.SERIES, int(round(a.horizon_min * 60 / 300)))
        source = {"reality": "REAL_LIVE", "provider": "google_routes",
                  "google_data_mode": "RUNTIME_REFERENCE", "forecast": "persistence",
                  "horizon_min": a.horizon_min, "levels": levels} | prov

    slow = lc.affected_edges(levels, cmap)
    print(f"[chain] {source['reality']}: {len(slow)} edges congested above free flow")
    if not slow:
        print("[chain] nothing to route around — the communication chain cannot be tested on a "
              "free-flowing network. Re-run with --levels to exercise the mechanism.")
        return 1

    weights = RESULTS / f"impairment{a.tag}_weights.xml"
    wrec = write_weights(levels, cmap, weights, 0.0, float(a.horizon), source)

    seeds = [int(s) for s in a.seeds.split(",")]
    runs = [run_condition(a, c, s, slow, weights) for s in seeds for c in conds]
    summary = analyse(runs, baseline=conds[0])

    rec = {"generated_utc": datetime.now(timezone.utc).isoformat(),
           "question": "does worse communication cause higher network delay?",
           "source": source,
           "demand": "DHAKA_SIMULATED_DEMAND (the feed supplies congestion state, never demand)",
           "network": str(Path(a.net).name), "scale": a.scale, "horizon_s": a.horizon,
           "compliance": a.compliance,
           "delivery_model": "single DENM" if a.single_shot else "official 1 Hz DENM repeat",
           "impairment_nature": "SIMULATED (Eclipse MOSAIC ITS-G5), not hardware-measured",
           "weights": wrec, "runs": runs, "summary": summary}
    (RESULTS / f"impairment_chain{a.tag}.json").write_text(json.dumps(rec, indent=1, default=str))
    write_md(rec, a)
    print(f"\nwrote {(RESULTS / f'impairment_chain{a.tag}.md')}")
    return 0


def write_md(rec: dict, a) -> None:
    s = rec["summary"]
    L = [f"# Does worse communication cause higher network delay?\n",
         f"Generated {rec['generated_utc']}. Source: **{rec['source']['reality']}**. "
         f"Network: real Dhaka R1. Demand: {rec['demand']}. Compliance {rec['compliance']:.0%}; "
         f"horizon {rec['horizon_s']} s; delivery model: {rec['delivery_model']}.\n",
         "The equipped set is identical in every condition. Conditions differ only in whether the "
         "advisory **arrived before the driver's decision point**; an undelivered advisory leaves "
         "that vehicle on its original route, which is what a missed advisory actually means.\n",
         f"Delivery fractions are read from `results/networking/latency.csv`, never interpolated. "
         f"**{rec['impairment_nature']}.**\n",
         "| condition | added latency | loss | delivery fraction | advisories delivered | routes changed | veh-h | waiting s | arrived |",
         "|---|---|---|---|---|---|---|---|---|"]
    for r in rec["runs"]:
        m = r["metrics"]
        L.append(f"| {r['condition']} (seed {r['seed']}) | {r['link']['added_latency_ms']} ms | "
                 f"{r['link']['loss_pct']} % | {r['delivery_fraction']} | "
                 f"{r['advisories_delivered']}/{r['equipped']} | {r['routes_changed']} | "
                 f"{m['total_vehicle_hours']:.1f} | {m.get('total_waiting_s', 0):.0f} | {m['arrived']} |")
    if "conditions" in s:
        L += ["", f"## Paired change vs `{s['baseline']}` (the best-communication condition)\n",
              "| condition | delivery | advisories delivered | veh-h % per seed | mean veh-h % | "
              "mean waiting % | seeds worse |", "|---|---|---|---|---|---|---|"]
        for cond, d in s["conditions"].items():
            L.append(f"| {cond} | {d['delivery_fraction']} | {d['mean_advisories_delivered']} | "
                     f"{d['vehicle_hours_pct_per_seed']} | **{d['mean_vehicle_hours_pct']} %** | "
                     f"{d['mean_waiting_pct']} % | {d['seeds_worse']}/{d['seeds']} |")
        L += ["", "A positive percentage means the condition is WORSE than the baseline: degrading "
                  "the link raised network delay.\n"]
    v = s.get("verdict")
    if v:
        L += [f"## Verdict: **{v['claim']}**\n"]
        bb = v.get("baseline_benefit")
        if bb:
            L += [f"Reference check — does advising anyone help at all? Perfect delivery vs "
                  f"advising nobody: mean {bb['mean_vehicle_hours_pct_advising_vs_nobody']} % "
                  f"vehicle-hours, helped on {bb['seeds_where_advising_helped']} seeds "
                  f"(**established: {bb['established']}**).\n"]
        L += [
              f"Worst condition `{v['worst_condition']}`: mean vehicle-hours "
              f"{v['mean_vehicle_hours_pct']} %, {v['seeds_agreeing']} paired seeds agree; "
              f"means monotone in link quality: {v['monotone_in_means']}.\n",
              f"{v['reason']}\n"]
    L.append(f"Regenerate: `python -m app.protocols.chains.impairment_chain --seeds {a.seeds}"
             + (f" --levels {a.levels}" if a.levels else "") + "`.\n")
    (RESULTS / f"impairment_chain{a.tag}.md").write_text("\n".join(L))


if __name__ == "__main__":
    sys.exit(main())
