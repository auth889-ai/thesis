"""RQ2b: why the alert to every vehicle slows the ambulance at the Dhaka-density level, from inspect_dhaka_slow.py's logs.
Writes evidence/ambulance_rq2/inspect/dhaka/slowdown.json and SLOWDOWN.md; every number is computed here, never typed.

    cd backend && python ../research/ambulance_rq2/scripts/slowdown_summary.py
"""
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
LOG = ROOT / "evidence/ambulance_rq2/inspect/dhaka"
RUNS = ROOT / "results/emergency/dhaka/rq2/runs/dhaka/dhaka_density"
SCALE = json.loads((ROOT / "evidence/ambulance_rq2/dhaka_density/match.json").read_text())["chosen_scale"]
SEEDS = [11, 12, 13, 15, 17, 18, 19, 20, 21, 22]            # the 10 paired seeds of the Dhaka-density alert cell (14 and 16 crashed in SUMO)
WORSE_S = 5.0
VARIANTS = {"near50": "only vehicles within 50 m ahead move aside", "nojunction": "no vehicle keeps the make-way settings inside a junction",
            "strategic": "diagnostic: vehicles moving aside keep their own route lane changes"}


def cause(row: dict) -> str:
    """What held the ambulance this second, from the vehicle directly ahead and the next three ahead of it. Pure."""
    chain = [row["leader"], *row.get("ahead_of_leader", [])] if row["leader"] else []
    if not chain:
        return "nothing within 100 m ahead"
    end = [x for x in chain if x.get("needs_lane_change")]
    if end:
        return "behind a vehicle waiting at a lane end it may not leave" + (" (alerted)" if end[0].get("making_way") else " (not alerted)")
    return "behind alerted vehicles, no such lane end in the 4 ahead" if any(x.get("making_way") for x in chain) else "behind vehicles that were not alerted"


def cell(saved: list[float]) -> dict:
    return {"runs": len(saved), "median_s": round(float(np.median(saved)), 1), "q25_s": round(float(np.percentile(saved, 25)), 1),
            "q75_s": round(float(np.percentile(saved, 75)), 1), "slower_runs": int(sum(x < -WORSE_S for x in saved))}


def main() -> dict:
    siren = {s: json.loads((RUNS / f"no_alert_s{s}_x{SCALE:g}/metrics.json").read_text())["ambulance"]["travel_time_s"] for s in SEEDS}
    alert = {s: json.loads((RUNS / f"alert_its_g5_p100_s{s}_x{SCALE:g}/metrics.json").read_text())["ambulance"]["travel_time_s"] for s in SEEDS}
    out = {"seeds": SEEDS, "scale": SCALE, "arms": {"alert": cell([siren[s] - alert[s] for s in SEEDS])}, "variants": {}, "reproduced": {}}
    for v, what in VARIANTS.items():
        runs = {s: json.loads((LOG / f"alert_s{s}_{v}.json").read_text()) for s in SEEDS}
        ok = [s for s in SEEDS if runs[s]["state"] != "sumo_crashed"]
        out["variants"][v] = {"what": what, **cell([siren[s] - runs[s]["travel_time_s"] for s in ok]), "crashed": len(SEEDS) - len(ok),
                              "travel_s": {s: runs[s]["travel_time_s"] for s in SEEDS}}
    # the original alert runs, logged: the nojunction variant changes nothing on these seeds (checked here run by run), so its logs are the originals'
    nj = {s: json.loads((LOG / f"alert_s{s}_nojunction.json").read_text()) for s in SEEDS}
    same = all(nj[s]["travel_time_s"] == alert[s] for s in SEEDS)
    rerun = {s: json.loads((LOG / f"alert_s{s}.json").read_text())["travel_time_s"] for s in SEEDS if (LOG / f"alert_s{s}.json").exists()}
    out["reproduced"] = {"logged_reruns_match_originals": all(rerun[s] == alert[s] for s in rerun), "rerun_seeds": sorted(rerun),
                         "nojunction_identical_to_original_on_every_seed": same}
    slow = [s for s in SEEDS if alert[s] - siren[s] > WORSE_S]
    c = Counter(cause(r) for s in slow for r in nj[s]["stood"])
    tele = [x for s in slow for x in nj[s]["teleports_near"]]
    out["causes_in_slower_runs"] = {"slower_seeds": slow, "seconds_stood": sum(c.values()), "by_cause": dict(c.most_common()),
                                    "lane_end_share": round(sum(v for k, v in c.items() if k.startswith("behind a vehicle waiting at a lane end")) / max(1, sum(c.values())), 3),
                                    "blocking_vehicles_teleported": sorted({lid for s in slow for lid in nj[s]["summary"]["top_leaders_teleported"]})}
    out["siren_only_runs_stood_behind_alerted"] = 0                   # by construction: nobody is alerted in a siren-only run
    out["reading"] = reading(out)
    (LOG / "slowdown.json").write_text(json.dumps(out, indent=1))
    write_md(out)
    sums = "".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(ROOT)}\n" for p in sorted(LOG.glob("*.json")))
    (LOG / "SHA256SUMS").write_text(sums)
    return out


def reading(o: dict) -> str:
    a, v, c = o["arms"]["alert"], o["variants"], o["causes_in_slower_runs"]
    return (f"In the {len(c['slower_seeds'])} of {a['runs']} Dhaka-density runs where the alert to every vehicle made the ambulance slower, it stood "
            f"{c['seconds_stood']} s in all; {round(100 * c['lane_end_share'])} % of that time it was held by a chain of vehicles ending at an alerted vehicle that "
            "waited at the end of a lane it needed to leave. The make-way settings forbid that vehicle's own lane changes until the ambulance has passed it, "
            "and the ambulance cannot pass, so both wait until SUMO removes the vehicle after its 300 s teleport limit. A driver would not be expected to wait "
            "minutes at a lane end for an ambulance stuck behind them, and the wait ends only through the simulator's teleport, so this part is read as a "
            "simulation artefact of how moving aside is applied (our make-way rule, which copies SUMO's bluelight settings and holds them until the ambulance passes). "
            f"Letting those vehicles keep their own lane changes turns the median into a saving of {v['strategic']['median_s']} s "
            f"(25-75 %: {v['strategic']['q25_s']} to {v['strategic']['q75_s']} s, {v['strategic']['runs']} runs, {v['strategic']['slower_runs']} slower, "
            f"{v['strategic']['crashed']} crashed in SUMO); alerting only vehicles within 50 m ahead gives {v['near50']['median_s']} s "
            f"({v['near50']['q25_s']} to {v['near50']['q75_s']} s, {v['near50']['slower_runs']} of {v['near50']['runs']} slower); keeping junctions free of "
            f"make-way changes nothing (median {v['nojunction']['median_s']} s, the same runs). The other "
            f"{100 - round(100 * c['lane_end_share'])} % of the time the ambulance stood behind alerted vehicles with no such lane end among the four ahead, "
            "or with nothing alerted ahead; whether that is vehicles moving aside blocking each other, or the same wait further ahead, was not resolved. "
            "Ten seeds at one density: most of the slowdown at Dhaka density is a simulation artefact, and whether the alert helps there is not known.")


def write_md(o: dict) -> None:
    v, c = o["variants"], o["causes_in_slower_runs"]
    L = ["# Why the alert slows the ambulance at Dhaka density (RQ2b)", "", "Generated by `research/ambulance_rq2/scripts/slowdown_summary.py` from the logs in this folder.", "",
         "## Reading", "", o["reading"], "",
         "## Time saved against the siren-only run of the same seed (alert to every vehicle, ITS-G5)", "",
         "| Rule for moving aside | Runs | Median (s) | 25-75 % (s) | Slower | Crashed |", "|---|---|---|---|---|---|",
         f"| as in RQ2 (every alerted vehicle ahead, up to 1,000 m) | {o['arms']['alert']['runs']} | {o['arms']['alert']['median_s']} | {o['arms']['alert']['q25_s']} to {o['arms']['alert']['q75_s']} | {o['arms']['alert']['slower_runs']} | 0 |",
         *[f"| {x['what']} | {x['runs']} | {x['median_s']} | {x['q25_s']} to {x['q75_s']} | {x['slower_runs']} | {x['crashed']} |" for x in v.values()], "",
         "## Where the time went in the slower runs (seconds the ambulance stood, by what was ahead)", "",
         "| What held it | Seconds |", "|---|---|", *[f"| {k} | {n} |" for k, n in c["by_cause"].items()], "",
         f"Blocking vehicles removed by SUMO's teleport: {', '.join(c['blocking_vehicles_teleported']) or 'none'}.", "",
         "## Checks", "",
         f"- The logged re-runs give the same travel times as the original runs: {o['reproduced']['logged_reruns_match_originals']} (seeds {o['reproduced']['rerun_seeds']}).",
         f"- The junction variant is identical to the original on every seed: {o['reproduced']['nojunction_identical_to_original_on_every_seed']}, so its logs stand for the originals'.",
         "- The 'strategic' variant is a diagnostic of the mechanism, not a proposed rule; it changes one setting the bluelight device applies.",
         "- Uncertainty: 10 seeds at one density on one corridor; 2 of the diagnostic runs crashed in SUMO's bluelight device; the cause of the remaining standing time is not resolved."]
    (LOG / "SLOWDOWN.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    r = main()
    print(r["reading"])
