"""RQ2c: choose the make-way distance by the rule fixed before the pilot (plan, 2026-10-09), never by time saved:
use 100 m unless, at the Dhaka-density level over the 10 seeds, it still produces the circular wait (an alerted vehicle waiting
at a lane end it may not leave blocks the ambulance for 60 s or more in a row, or is teleported while blocking it); then 50 m;
if 50 m also does, stop. Reads the pilot logs (inspect_dhaka_slow.py --variant v2d100 / v2d50); writes
evidence/ambulance_rq2/makeway_v2/choice.json.

    cd backend && python ../research/ambulance_rq2/scripts/choose_makeway.py
"""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LOG = ROOT / "evidence/ambulance_rq2/inspect/dhaka"
OUT = ROOT / "evidence/ambulance_rq2/makeway_v2"
SEEDS = [11, 12, 13, 15, 17, 18, 19, 20, 21, 22]
MIN_S = 60
spec = importlib.util.spec_from_file_location("sd", Path(__file__).with_name("slowdown_summary.py"))
sd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sd)
LANE_END = "behind a vehicle waiting at a lane end it may not leave (alerted)"


def circular(run: dict) -> dict:
    """The longest stretch of consecutive seconds held by an alerted vehicle at a lane end, and blockers teleported while alerted. Pure."""
    longest = cur = 0
    last = None
    for r in run["stood"]:
        hit = sd.cause(r) == LANE_END
        cur = cur + 1 if hit and last is not None and r["t"] == last + 1 else (1 if hit else 0)
        longest, last = max(longest, cur), r["t"]
    held = {}                                                     # second -> the vehicles holding the ambulance then (leader and the three ahead of it)
    for r in run["stood"]:
        held[r["t"]] = ({r["leader"]["id"]} if r["leader"] else set()) | {c["id"] for c in r.get("ahead_of_leader", [])}
    tele = sorted({x["vehicle"] for x in run["teleports_near"] if x["alerted"] and x["vehicle"] in held.get(x["t"] - 1, set()) | held.get(x["t"], set())})   # teleported WHILE blocking
    return {"longest_lane_end_wait_s": longest, "alerted_blockers_teleported": tele, "circular": longest >= MIN_S or bool(tele)}


def main() -> dict:
    per = {}
    for v in ("v2d100", "v2d50"):
        runs = {s: json.loads((LOG / f"alert_s{s}_{v}.json").read_text()) for s in SEEDS}
        per[v] = {s: {"state": runs[s]["state"], "travel_time_s": runs[s]["travel_time_s"], **circular(runs[s])} for s in SEEDS}
    hit = {v: [s for s, r in per[v].items() if r["circular"]] for v in per}           # the rule as fixed before the pilot
    choice_as_fixed = 100.0 if not hit["v2d100"] else 50.0 if not hit["v2d50"] else None
    siren = {}                                                    # the flagged seeds' siren-only runs, logged the same way: are the same waits there without any alert?
    for sd_ in sorted({x for v in hit.values() for x in v}):
        f = LOG / f"no_alert_s{sd_}.json"
        if f.exists():
            r = json.loads(f.read_text())
            any_end = dict(r, stood=[dict(x, leader=dict(x["leader"], making_way=True) if x["leader"] else None,
                                          ahead_of_leader=[dict(c, making_way=True) for c in x.get("ahead_of_leader", [])]) for x in r["stood"]],
                           teleports_near=[dict(t, alerted=True) for t in r["teleports_near"]])   # count every vehicle, since none is alerted here
            siren[sd_] = {"travel_time_s": r["travel_time_s"], **circular(any_end)}
    def caused(v, s_):
        """Amended rule (owner, 2026-10-09, after the pilot rejected both): a flagged wait counts only if the siren-only run of the same seed does not show it."""
        r, b = per[v][s_], siren.get(s_)
        if b is None:
            return r["circular"]
        return (r["longest_lane_end_wait_s"] >= MIN_S and b["longest_lane_end_wait_s"] < MIN_S) or bool(set(r["alerted_blockers_teleported"]) - set(b["alerted_blockers_teleported"]))
    hit_amended = {v: [s_ for s_ in hit[v] if caused(v, s_)] for v in per}
    choice = 100.0 if not hit_amended["v2d100"] else 50.0 if not hit_amended["v2d50"] else None
    body = {"rule": f"100 m unless it still produces the circular wait at Dhaka density (lane-end wait >= {MIN_S} s in a row, or an alerted blocker teleported); "
                    "then 50 m; if both do, stop. Fixed before the pilot; time saved is not used.",
            "why_not_a_cited_value": "no published distance at which drivers act on an electronic alert was found; the sources found describe siren audibility "
                                     "(8-12 m into a closed car at urban junctions, US DOT via EMS World; 10-50 m detection window, arXiv 2109.14797), the siren-only world",
            "seeds_with_circular_wait": hit, "chosen_by_rule_as_fixed": choice_as_fixed,
            "amendment": {"when": "2026-10-09, after the pilot, approved by the owner", "why": "both distances were rejected only by waits that also occur, identically, "
                          "in the siren-only runs of the same seeds (same lane-end waits, same blockers teleported), i.e. corridor congestion the alert did not cause",
                          "rule": "a flagged wait counts only if the siren-only run of the same seed does not show it", "seeds_with_alert_caused_wait": hit_amended},
            "per_run": per, "chosen_distance_m": choice,
            "siren_only_same_seeds": siren,
            "note": "the rule is applied as fixed; siren_only_same_seeds shows whether a flagged wait also happens with no alert at all (any vehicle counted)"}
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "choice.json"
    p.write_text(json.dumps(body, indent=1))
    (OUT / "choice.sha256").write_text(hashlib.sha256(p.read_bytes()).hexdigest() + "  choice.json\n")
    return body


if __name__ == "__main__":
    b = main()
    print(json.dumps({"as_fixed": b["seeds_with_circular_wait"], "amended": b["amendment"]["seeds_with_alert_caused_wait"], "chosen_distance_m": b["chosen_distance_m"]}))
    print("siren only, same seeds:", {s: (r["travel_time_s"], r["longest_lane_end_wait_s"], r["alerted_blockers_teleported"]) for s, r in b["siren_only_same_seeds"].items()})
    for v, rs in b["per_run"].items():
        print(v, {s: (r["travel_time_s"], r["longest_lane_end_wait_s"], r["alerted_blockers_teleported"]) for s, r in rs.items()})
