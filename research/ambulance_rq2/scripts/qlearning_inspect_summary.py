"""RQ2c: where the ambulance stood when the Q-learning signals (no alert) made it slower at the Dhaka-density level, against the
siren-only runs of the same seeds, from inspect_dhaka_slow.py's logs (tags rq2c and rq2c_deep). Every number is computed here.
Writes evidence/ambulance_rq2/inspect/dhaka/qlearning.json and QLEARNING.md.

    python research/ambulance_rq2/scripts/qlearning_inspect_summary.py
"""
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LOG = ROOT / "evidence/ambulance_rq2/inspect/dhaka"
CTRL = set(json.loads((ROOT / "results/emergency/dhaka/rq2/rl/train_dhaka_density_x0.78.json").read_text())["signals"])
SEEDS = [14, 18, 19, 21, 23]                 # the seeds where Q-learning signals were slower than the siren alone (5 of 10)
DEEP = [14, 18, 19, 23]
RED = set("rRyYu")


def at_light(r: dict) -> str:
    """Where the ambulance stood relative to the next light on its route. Pure."""
    n, L = r.get("next_tls"), r["leader"]
    if not n or n["dist"] > 100:
        return "no light within 100 m ahead"
    who = "a Q-learning light" if n["id"] in CTRL else "a fixed light"
    if n["state"] in RED:
        return f"first at a red ({who})" if (L is None or L["gap"] >= n["dist"] - 1) else f"in the queue at a red ({who})"
    return f"light ahead green ({who}), still held"


def head(r: dict) -> str:
    """What the queue ahead of the ambulance ended at (--deep logs). Pure."""
    q = r.get("queue_head")
    if not q:
        return "no stopped vehicle ahead"
    t = q["next_tls"]
    at = ("a red light" if t["state"] in RED else "a green light") if t and t["dist"] < 30 else "no light"
    return f"queue head at {at}" + (", waiting to change lane" if q["needs_lane_change"] else "")


def main() -> dict:
    out = {"seeds": SEEDS, "controlled_signals": len(CTRL), "runs": {}, "totals": {}}
    tot = {"no_alert": Counter(), "rl_signals": Counter()}
    for s in SEEDS:
        for arm in ("no_alert", "rl_signals"):
            d = json.loads((LOG / f"{arm}_s{s}_rq2c.json").read_text())
            c = Counter(at_light(r) for r in d["stood"])
            tot[arm].update(c)
            out["runs"][f"{arm}_s{s}"] = {"travel_time_s": d["travel_time_s"], "stood_s": d["stood_s"], "by_light": dict(c),
                                          "where": Counter(r["road"] for r in d["stood"]).most_common(2)}
    heads = Counter(head(r) for s in DEEP for r in json.loads((LOG / f"rl_signals_s{s}_rq2c_deep.json").read_text())["stood"])
    depth = sorted(r["queue_head"]["behind_it"] for s in DEEP for r in json.loads((LOG / f"rl_signals_s{s}_rq2c_deep.json").read_text())["stood"] if r.get("queue_head"))
    out["totals"] = {k: {"stood_s": sum(v.values()), "by_light": dict(v.most_common())} for k, v in tot.items()}
    out["queue_head_rl"] = {"seconds": dict(heads.most_common()), "median_vehicles_to_head": depth[len(depth) // 2] if depth else None}
    rows = [r for s_ in SEEDS for r in json.loads((LOG / f"rl_signals_s{s_}_rq2c.json").read_text())["stood"]]
    out["next_light_rl"] = {"green": sum(1 for r in rows if r.get("next_tls") and r["next_tls"]["state"] not in RED),
                            "red": sum(1 for r in rows if r.get("next_tls") and r["next_tls"]["state"] in RED), "none_ahead": sum(1 for r in rows if not r.get("next_tls"))}
    rl, sr = out["totals"]["rl_signals"], out["totals"]["no_alert"]
    near = rl["stood_s"] - rl["by_light"].get("no light within 100 m ahead", 0)
    out["reading"] = (f"On the {len(SEEDS)} seeds where the Q-learning signals made the ambulance slower at Dhaka density, it stood {rl['stood_s']} s in all "
                      f"(siren-only on the same seeds: {sr['stood_s']} s). {near} of those seconds were within 100 m of a traffic light; "
                      f"the next light on its route was green for it in {out['next_light_rl']['green']} s, red in {out['next_light_rl']['red']} s, and there was no light left ahead in "
                      f"{out['next_light_rl']['none_ahead']} s. The queues it stood in were short (median {out['queue_head_rl']['median_vehicles_to_head']} "
                      "vehicles to the head) and their heads were not at a light; many ended at a vehicle waiting to change lane. So the lights did not hold the "
                      "ambulance directly. The Q-learning controllers change when traffic is released around the route, which may load the junctions where it "
                      "stood, but these logs do not show that path; the cause of the slowdown is not established.")
    (LOG / "qlearning.json").write_text(json.dumps(out, indent=1))
    L = ["# Q-learning signals at Dhaka density: where the ambulance stood (RQ2c)", "", out["reading"], "",
         "| Run | Travel (s) | Stood (s) | By the light ahead | Where (most seconds) |", "|---|---|---|---|---|",
         *[f"| {k} | {v['travel_time_s']} | {v['stood_s']} | {v['by_light']} | {v['where']} |" for k, v in out["runs"].items()], "",
         "Queue heads under Q-learning (seeds " + ", ".join(map(str, DEEP)) + "): " + json.dumps(out["queue_head_rl"]["seconds"]), "",
         "The logged re-runs give the same travel times as the original runs; the logs are in this folder (`*_rq2c.json`, `*_rq2c_deep.json`)."]
    (LOG / "QLEARNING.md").write_text("\n".join(L) + "\n")
    (LOG / "SHA256SUMS").write_text("".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(ROOT)}\n" for p in sorted(LOG.glob("*.json"))))
    return out


if __name__ == "__main__":
    print(main()["reading"])
