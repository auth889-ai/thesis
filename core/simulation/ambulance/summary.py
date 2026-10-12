"""RQ2 summary: time saved by each arm against the siren-only run of the same seed and density (paired), over density and equipped
share; where the alert stops helping; why, from the free space and the queues measured in the same runs. Sentences come from the
numbers. Writes results/emergency/dhaka/rq2/summary.json and .md, figures/, and evidence/ambulance_rq2/SHA256SUMS."""
from __future__ import annotations

import hashlib
import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from core.common.paths import REPO
from core.simulation.ambulance.study import CITY, DEMAND, PAIRS_WANTED, RQ2, RUNS, RUNS_V2, SHARES

EVIDENCE = REPO / "evidence/ambulance_rq2"
HELP_PCT = 10.0
WORSE_S = 5.0                                     # "slower": more than this many seconds slower than the siren-only run of the same seed                                   # "helps": saves at least this share of the siren-only trip
DHATRAX = REPO / "data/recorded/dhatrax/Traffic_Analysis/combined_traffic_5min.csv"
ARMS = {"alert": "Alert to vehicles", "alert_preemption": "Alert + signal preemption", "rl_signals": "Q-learning signals (sumo-rl), no alert",
        "rl_signals_alert": "Q-learning signals (sumo-rl) + alert"}


DHAKA = "dhaka"                                    # RQ2b's level: the corridor with DhaTraX's recorded counts, at the scale matching INT's recorded density
DD = REPO / "evidence/ambulance_rq2/dhaka_density"
K = lambda lv: lv if isinstance(lv, str) else f"{lv:g}"
LABEL = lambda lv: "Dhaka density" if lv == DHAKA else f"x{lv:g}"
NAME = lambda lv: "the Dhaka-density corridor" if lv == DHAKA else f"demand x{lv:g}"


ALERTING = ("alert", "alert_preemption", "rl_signals_alert")                # the arms in which vehicles are alerted, so the make-way rule runs


def rows(version: int = 2) -> pd.DataFrame:
    """Every finished run. version 2 (current): siren-only and Q-learning-without-alert runs from runs/ (no make-way in them), the
    alerting arms from runs_v2/ (make-way v2). version 1: everything from runs/ (make-way v1; the labelled record). Never mixed."""
    out = []
    pick = lambda root: [*(root / CITY / DEMAND).glob("*/metrics.json"), *(root / CITY / "dhaka_density").glob("*/metrics.json")]
    files = pick(RUNS) if version == 1 else [f for f in pick(RUNS) if json.loads(f.read_text())["arm"] not in ALERTING] + pick(RUNS_V2)
    for f in files:
        m = json.loads(f.read_text())
        if m.get("state") == "sumo_crashed":
            continue
        w = m.get("why") or {}
        dk = m.get("demand_id") == "dhaka_density"
        out.append({"arm": m["arm"], "share": m.get("equipped_share") or 0.0, "seed": m["seed"], "scale": float(m.get("scale", 1.0)),
                    "level": DHAKA if dk else f"{float(m.get('scale', 1.0)):g}",
                    "arrived": bool(m["ambulance"].get("arrived")), "travel_s": m["ambulance"].get("travel_time_s"), "free_width_m": w.get("free_width_m"),
                    "blocked_s": w.get("blocked_s"), "yield_share": w.get("yield_share"), "queue": w.get("queue_at_signals"),
                    "others_loss_s": (m.get("others") or {}).get("mean_time_loss_s")})
    return pd.DataFrame(out)


def paired(df: pd.DataFrame) -> pd.DataFrame:
    """Each run joined to the no-alert run of the same seed and density: saved_s and saved_pct (positive = faster)."""
    base = df[df.arm == "no_alert"][["seed", "level", "travel_s", "free_width_m", "queue", "blocked_s"]].rename(
        columns={"travel_s": "base_s", "free_width_m": "base_free", "queue": "base_queue", "blocked_s": "base_blocked"})
    j = df[df.arm != "no_alert"].merge(base, on=["seed", "level"])
    j = j[j.travel_s.notna() & j.base_s.notna()].copy()
    j["saved_s"] = j.base_s - j.travel_s
    j["saved_pct"] = 100 * j.saved_s / j.base_s
    return j


def spearman(x, y, n_boot: int = 2000, seed: int = 11) -> dict:
    """Spearman's rho with a bootstrap 95 % CI. Pure numpy; tested."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    if len(x) < 5:
        return {"rho": None, "n": int(len(x))}
    r = lambda a, b: float(np.corrcoef(pd.Series(a).rank(), pd.Series(b).rank())[0, 1])
    rng = np.random.default_rng(seed)
    boots = [r(x[i], y[i]) for i in (rng.integers(0, len(x), len(x)) for _ in range(n_boot))]
    return {"rho": round(r(x, y), 3), "ci95": [round(float(np.nanpercentile(boots, 2.5)), 3), round(float(np.nanpercentile(boots, 97.5)), 3)], "n": int(len(x))}


def table(j: pd.DataFrame) -> dict:
    """{arm: {share: {scale: {saved_s, saved_s_sd, saved_pct, seeds}}}}"""
    out: dict = defaultdict(lambda: defaultdict(dict))
    for (arm, share, level), g in j.groupby(["arm", "share", "level"]):
        out[arm][f"{share:g}"][level] = {"saved_s": round(float(g.saved_s.mean()), 1), "saved_s_sd": round(float(g.saved_s.std(ddof=1)), 1) if len(g) > 1 else None,
                                                 "saved_s_median": round(float(g.saved_s.median()), 1), "saved_pct": round(float(g.saved_pct.mean()), 1),
                                                 "saved_pct_median": round(float(g.saved_pct.median()), 1), "seeds": int(len(g)),
                                                 "saved_s_q25": round(float(g.saved_s.quantile(.25)), 1), "saved_s_q75": round(float(g.saved_s.quantile(.75)), 1),
                                                 "slower_runs": int((g.saved_s < -WORSE_S).sum())}   # the alert made the ambulance slower than the siren alone
    return json.loads(json.dumps(out))


def frontier(tab: dict, levels: list[float]) -> dict:
    """For each density, the lowest equipped share whose alert saves >= HELP_PCT %; and the first density where no share does. Pure."""
    out = {}
    for arm in ("alert", "alert_preemption"):
        per = {}
        for lv in levels:
            k = K(lv)
            helping = [float(s) for s, by in tab.get(arm, {}).items() if by.get(k, {}).get("saved_pct_median", -1e9) >= HELP_PCT]   # the median: a few blocked runs do not decide it
            per[k] = min(helping) if helping else None
        stops = next((lv for lv in levels if lv != DHAKA and per[K(lv)] is None), None)
        out[arm] = {"lowest_share_that_helps": per, "stops_helping_at_scale": stops}
    return out


def dhaka_anchor(ladder: list[dict]) -> dict:
    """The density level whose simulated INT-section density is closest to DhaTraX INT's recorded 07:00-08:00 median."""
    d = pd.read_csv(DHATRAX)
    x = d[(d.site == "INT") & (d.interval_start.str[11:13] == "07")]
    rec = round(float(x.density_veh_per_km.median()), 1)
    lv = [l for l in ladder if l.get("section_density_veh_km") is not None]
    best = min(lv, key=lambda l: abs(l["section_density_veh_km"] - rec)) if lv else None
    reached = any(l["section_density_veh_km"] >= rec for l in lv)
    return {"recorded_veh_km": rec, "recorded_window": "DhaTraX INT, 2026-04-19 07:00-08:00, median of 5-minute intervals", "closest_scale": best and best["scale"],
            "closest_simulated_veh_km": best and best["section_density_veh_km"], "reached_before_gridlock": reached,
            "caveat": "DhaTraX speeds and densities come from camera tracking whose calibration the authors did not validate; a camera density counts every vehicle in about 90 m, two- and three-wheelers included"}


def density_gap(dl: dict | None = None) -> dict | None:
    """The measured explanation of the INT density gap (research/ambulance_rq2/scripts/density_gap.py -> evidence/ambulance_rq2/density_gap.json),
    as a sentence built from its numbers; None when the check has not been run."""
    p = EVIDENCE / "density_gap.json"
    if not p.exists():
        return None
    g = json.loads(p.read_text())
    rec, jam = g["dhatrax_int"], g["lane_based_jam_density"]
    d, t = {r["variant"]: r for r in g["runs"]}["default"], {r["variant"]: r for r in g["runs"]}["tight"]
    elsewhere = max(e["veh_km"] for e in d["densest_edges_peak_veh_km"])
    text = (f"Why the simulation stays far below Dhaka's recorded density at the INT camera ({rec['density_07_veh_km']} vehicles/km, 07:00-08:00): "
            f"(1) not the definition: both count every vehicle class on the whole road over about 90 m ({rec['zone_length_m']} m camera zone, "
            f"{g['sumo_section']['length_m']} m simulated section); "
            f"(2) not the space per vehicle: SUMO's lengths and gaps for this mix allow about {jam['jam_density_veh_km_3_lanes']} vehicles/km on those 3 lanes, "
            f"and other roads in the same run reach {elsewhere} vehicles/km at gridlock; "
            f"(3) partly lane discipline: with smaller lateral gaps for two-wheelers, rickshaws and CNGs the section's mean density rises from "
            f"{d['section_density_mean_veh_km']} to {t['section_density_mean_veh_km']} vehicles/km, still below the recorded value; "
            f"(4) mainly supply: only {d['section_entered_per_hour']} vehicles an hour enter the section in the simulation, against {rec['flow_07_veh_h']} recorded, "
            "because the generated trips do not load this road and the network gridlocks elsewhere first. "
            "So the whole-network ambulance results come from a simulation that does not reach Dhaka's recorded density on the road it measures.")
    if dl and dl.get("reached"):
        text += (f" (5) Supply tested: a corridor {dl['buffer_m']:g} m around the route, loaded with the recorded counts at INT and BM and the smaller lateral gaps, "
                 f"overshoots at the full counts ({dl['full_counts_INT_density_median']} vehicles/km on INT) and reaches {dl['INT_density_median']} vehicles/km "
                 f"at x{dl['scale']:g} of the counts, inside the recorded range ({dl['recorded']['density_q25']}-{dl['recorded']['density_q75']}); "
                 f"but only {dl['INT_entered_per_hour_median']} vehicles an hour pass, against {dl['recorded']['flow_veh_h_median']} recorded. "
                 "The density is reached; the recorded flow at that density is not.")
    return {"text": text, "numbers": {"recorded_veh_km": rec["density_07_veh_km"], "recorded_flow_veh_h": rec["flow_07_veh_h"], "sim_entered_veh_h": d["section_entered_per_hour"],
                                      "sim_mean_veh_km": d["section_density_mean_veh_km"], "tight_mean_veh_km": t["section_density_mean_veh_km"],
                                      "jam_density_veh_km": jam["jam_density_veh_km_3_lanes"], "elsewhere_peak_veh_km": elsewhere,
                                      **({"corridor_veh_km": dl["INT_density_median"], "corridor_full_veh_km": dl["full_counts_INT_density_median"], "corridor_scale": dl["scale"],
                                          "corridor_flow_veh_h": dl["INT_entered_per_hour_median"]} if dl and dl.get("reached") else {})}}


def dhaka_label(median: float, rec: dict, scale: float) -> str:
    """"Dhaka density" only when the corridor's median INT density lies inside the recorded 07:00-08:00 interquartile range. Pure; tested."""
    return "Dhaka density" if rec["density_q25"] <= median <= rec["density_q75"] else f"corridor x{scale:g}"


def dhaka_level() -> dict | None:
    """RQ2b: what the corridor with DhaTraX's recorded counts reaches on the INT section at the chosen scale (corridor.match / corridor.density),
    beside the recorded 07:00-08:00 values. The "Dhaka density" label holds only when the median over seeds is inside the recorded IQR."""
    if not (DD / "match.json").exists():
        return None
    m, cal = json.loads((DD / "match.json").read_text()), json.loads((DD / "calibration.json").read_text())
    sc = m["chosen_scale"]
    if sc is None:
        return {"reached": False, "tried": m["tried"], "recorded": m["recorded_INT"]}
    d = json.loads((DD / f"density_x{sc:g}.json").read_text())
    full = json.loads((DD / "density.json").read_text())
    dens = [r["INT_density_mean"] for r in d["runs"]]
    rec = m["recorded_INT"]
    return {"reached": True, "scale": sc, "label": dhaka_label(d["INT_density_median_over_seeds"], rec, sc),
            "INT_density_median": d["INT_density_median_over_seeds"], "INT_density_q25": round(float(np.percentile(dens, 25)), 1),
            "INT_density_q75": round(float(np.percentile(dens, 75)), 1), "density_seeds": [r["seed"] for r in d["runs"]],
            "INT_entered_per_hour_median": d["INT_entered_median"], "recorded": rec,
            "full_counts_INT_density_median": round(float(np.median([r["INT_density_mean"] for r in full["runs"]])), 1),
            "full_counts_INT_entered_median": int(np.median([r["INT_entered_per_hour"] for r in full["runs"]])),
            "tried": m["tried"], "edges_kept": cal["edges_kept"], "edges_full": cal["edges_full"], "buffer_m": cal["buffer_m"],
            "signals_same_programme": all(t["same_programme"] for t in cal["route_signals_after_cut"]),
            "sampled_trips": cal["demand"]["sampled_through_counted_sections"], "background_trips": cal["demand"]["background_uncalibrated"]}


def dhaka_sentence(dl: dict, tab: dict) -> str | None:
    """The plain finding for the Dhaka-density row, from the numbers; None until its runs exist."""
    if not dl or not dl.get("reached"):
        return None
    a, p, r = tab.get("alert", {}).get("1", {}).get(DHAKA), tab.get("alert_preemption", {}).get("1", {}).get(DHAKA), tab.get("rl_signals", {}).get("0", {}).get(DHAKA)
    if not a:
        return None
    say = lambda c: f"{'saves' if c['saved_s_median'] >= 0 else 'costs'} a median {abs(c['saved_s_median'])} s (time saved, 25-75 %: {c['saved_s_q25']} to {c['saved_s_q75']} s)"
    s = (f"At the density the corridor reaches ({dl['INT_density_median']} vehicles/km on the INT section against the recorded {dl['recorded']['density_median']}), "
         f"the alert to every vehicle {say(a)} over {a['seeds']} paired seeds, {a['slower_runs']} of them slower than the siren alone")
    if p:
        s += f"; with signal preemption it {say(p)}"
    if r:
        s += f"; with Q-learning signals and no alert it {say(r)}"
    return s + (f". Only {dl['INT_entered_per_hour_median']} vehicles an hour pass the section there, against {dl['recorded']['flow_veh_h_median']} recorded: "
                "the density matches, the flow does not.")


def findings(tab: dict, front: dict, why: dict, ladder: list[dict], anchor: dict, j: pd.DataFrame, levels: list) -> dict:
    f = {}
    levels = [lv for lv in levels if lv != DHAKA]                               # the whole-network sentences; the corridor row has dhaka_sentence
    a100 = tab.get("alert", {}).get("1", {})
    if a100:
        lo, hi = levels[0], levels[-1]
        f["density"] = ("With every vehicle equipped, the alert's median saving is " + "; ".join(
            f"{a100[K(lv)]['saved_s_median']} s ({a100[K(lv)]['saved_pct_median']} %) at demand x{lv:g}" for lv in levels if K(lv) in a100) + ".")
    lo = {k: v for k, v in front.get("alert", {}).get("lowest_share_that_helps", {}).items() if k != DHAKA}
    yes = [k for k, v in lo.items() if v is not None]
    no = [k for k, v in lo.items() if v is None]
    nm = lambda k: f"demand x{k}"
    f["stops"] = (f"A median saving of {HELP_PCT:g} % or more is reached only at " + ", ".join(f"{nm(k)} (from {lo[k] * 100:g} % equipped)" for k in yes)
                  + (f"; at " + ", ".join(nm(k) for k in no) + " no equipped share reaches it." if no else ".")) if yes else \
                 f"No equipped share reaches a median saving of {HELP_PCT:g} % at any density."
    if why.get("saved_vs_free_width", {}).get("rho") is not None:
        w, q = why["saved_vs_free_width"], why.get("saved_vs_queue", {})
        word = lambda c: "is not clearly related to" if c["ci95"][0] <= 0 <= c["ci95"][1] else ("rises with" if c["rho"] > 0 else "falls with")
        f["why"] = (f"Time saved {word(w)} the free width ahead of the ambulance in the siren-only run (Spearman rho {w['rho']}, 95 % CI {w['ci95'][0]} to {w['ci95'][1]}, "
                    f"{w['n']} paired runs) and {word(q)} the queue at the route's signals (rho {q.get('rho')}, CI {q['ci95'][0]} to {q['ci95'][1]}).")
        y = why.get("saved_vs_yield_share", {})
        if y.get("rho") is not None:
            f["why"] += f" It {word(y)} the share of alerted vehicles that actually moved aside (rho {y['rho']}, CI {y['ci95'][0]} to {y['ci95'][1]})."
        b = why.get("saved_vs_siren_blocked_s", {})
        if b.get("rho") is not None:
            f["why"] += f" It {word(b)} how long the siren-only ambulance stood blocked (rho {b['rho']}, CI {b['ci95'][0]} to {b['ci95'][1]})."
        fw = why.get("free_width_by_scale", {})
        if fw:
            f["why"] += (f" The free width ahead hardly changes with density ({min(fw.values())}-{max(fw.values())} m over all levels): on this route there is room to "
                         "move aside at every level, so room is not what limits the alert.")
        rl, al = tab.get("rl_signals", {}).get("0", {}), tab.get("alert", {}).get("1", {})
        common = [k for k in rl if k in al and k != DHAKA]
        if common:
            beats = sum(rl[k]["saved_s_median"] > al[k]["saved_s_median"] for k in common)
            f["why"] += (f" Smarter signals do more: the Q-learning signals' median saving beats the alert to every vehicle at {beats} of {len(common)} densities, "
                         "which suggests the ambulance's delay on this route sits at the junctions more than behind vehicles that could move aside.")
    sl = j[j.arm.isin(["alert", "alert_preemption"]) & (j.level != DHAKA)]
    if len(sl):
        worse = sl[sl.saved_s < -WORSE_S]
        f["backfire"] = (f"In {len(worse)} of {len(sl)} alert runs the ambulance was more than {WORSE_S:g} s slower than with the siren alone"
                         + (f" (worst {round(float(-worse.saved_s.min()))} s slower, at demand x{worse.loc[worse.saved_s.idxmin(), 'level']}); these runs are kept in every mean, not dropped." if len(worse) else "."))
    rl = {k: v for k, v in tab.get("rl_signals", {}).get("0", {}).items() if k != DHAKA}
    if rl:
        f["rl"] = "Q-learning signals without the alert: median saving " + ", ".join(f"{v['saved_s_median']} s at x{k}" for k, v in sorted(rl.items(), key=lambda kv: float(kv[0]))) + \
                  " against SUMO's own signal programmes (3 signals near the route controlled)."
    f["dhaka"] = (f"On the whole network, Dhaka's recorded density at the INT camera ({anchor['recorded_veh_km']} vehicles/km, 07:00-08:00) "
                  + (f"is matched closest by demand x{anchor['closest_scale']:g} ({anchor['closest_simulated_veh_km']} vehicles/km)." if anchor["reached_before_gridlock"]
                     else f"is not reached before the simulation gridlocks: the densest run gives {anchor['closest_simulated_veh_km']} vehicles/km on that section."))
    return f


def settings_makeway() -> dict:
    from core.simulation.ambulance.service import settings
    return dict(settings()["alert"].get("makeway") or {"version": 1})


def makeway_sentence(mc: dict) -> str:
    """How alerted vehicles move aside in the current results, and how the distance was chosen. From choice.json."""
    a = mc["amendment"]
    return (f"Moving aside (make-way v2): alerted vehicles keep their own route lane changes, and only those within {mc['chosen_distance_m']:g} m ahead of the "
            "ambulance move aside. No published distance at which drivers act on an electronic alert was found, so 50 m and 100 m were piloted at the "
            "Dhaka-density level and chosen by a rule fixed before the pilot (the longer, unless it still produced a circular wait). The rule as fixed rejected "
            f"both, only on waits that also occur identically in the siren-only runs of the same seeds; the owner amended it after the pilot ({a['rule']}), "
            f"which gives {mc['chosen_distance_m']:g} m. Time saved was not used in the choice.")


def slowdown() -> dict | None:
    """RQ2b: the inspected cause of the alert's slowdown at Dhaka density (research/ambulance_rq2/scripts/slowdown_summary.py)."""
    p = EVIDENCE / "inspect/dhaka/slowdown.json"
    return json.loads(p.read_text()) if p.exists() else None


def plain(tab: dict, j: pd.DataFrame) -> dict | None:
    """The everyday pages' ambulance sentence (Emergency, 3D City, Tour; CLAUDE.md plain language rule 5), from the same table as the
    Research card: at the Dhaka-density level once its runs are complete, else at demand x1 (the generated demand the earlier
    Emergency sentence used). The alert to every vehicle, the Q-learning signals, the siren-only trip, and how often an alert
    run was slower than the siren alone over the whole-network levels (the "backfire" finding). Pure; tested."""
    al = tab.get("alert", {}).get("1", {})
    done = lambda lv: al.get(lv, {}).get("seeds", 0) >= PAIRS_WANTED and tab.get("rl_signals", {}).get("0", {}).get(lv, {}).get("seeds", 0) >= PAIRS_WANTED
    level = DHAKA if done(DHAKA) else "1"                                       # the Dhaka-density row only once every arm there is complete
    if level not in al:
        return None
    a, r = al[level], tab.get("rl_signals", {}).get("0", {}).get(level)
    base = j[(j.arm == "alert") & (j.share == 1.0) & (j.level == level)].base_s
    sl = j[(j.arm == "alert") & (j.share == 1.0) & (j.level == level)]          # the same runs as the sentence: alert to every vehicle, at its level
    up = lambda x: int(np.floor(x + 0.5))                                        # half up, so 32.5 s on Research reads "about 33 s"
    return {"level": level, "trip_s": up(float(base.median())), "alert_s": up(a["saved_s_median"]), "alert_q25_s": a["saved_s_q25"],
            "alert_reliable": bool(a["saved_s_q25"] > 0 and a["slower_runs"] == 0), "signals_s": up(r["saved_s_median"]) if r else None,
            "signals_more": bool(r and r["saved_s_median"] > max(a["saved_s_median"], 0)),   # "did more" only when the signals actually saved time
            "slower_runs": int((sl.saved_s < -WORSE_S).sum()), "alert_runs": int(len(sl)),
            "not_every_time": bool(len(sl) and (sl.saved_s < -WORSE_S).sum() / len(sl) >= 0.3)}     # the everyday sentence says "though not every time", no counts


WORD = lambda c: "is not clearly related to" if c["ci95"][0] <= 0 <= c["ci95"][1] else ("rises with" if c["rho"] > 0 else "falls with")


def why_dhaka_sentence(w: dict, whole_fw: dict | None = None) -> str | None:
    """The Why for the Dhaka-density row alone, from its own alert runs, in the whole-network Why's words. Pure."""
    f, q, b = w.get("saved_vs_free_width", {}), w.get("saved_vs_queue", {}), w.get("saved_vs_siren_blocked_s", {})
    if f.get("rho") is None:
        return None
    return (f"At the Dhaka-density level, time saved {WORD(f)} the free width ahead (rho {f['rho']}, CI {f['ci95'][0]} to {f['ci95'][1]}, {f['n']} paired runs), "
            f"{WORD(q)} the queue at the route's signals (rho {q['rho']}, CI {q['ci95'][0]} to {q['ci95'][1]}) and {WORD(b)} how long the siren-only ambulance "
            f"stood blocked (rho {b['rho']}, CI {b['ci95'][0]} to {b['ci95'][1]}; median {w['siren_blocked_s_median']} s blocked). Free width ahead averages "
            f"{w['free_width_m_mean']} m there" + (f" (whole network: {min(whole_fw.values())}-{max(whole_fw.values())} m)." if whole_fw else "."))


def old_vs_new(v1: dict, v2: dict) -> dict:
    """Per alerting arm, share and level: median saved, 25-75 % and slower runs with make-way v1 (record) beside v2 (current). Pure."""
    pick = lambda c: c and {k: c[k] for k in ("saved_s_median", "saved_s_q25", "saved_s_q75", "slower_runs", "seeds")}
    out: dict = {}
    for arm in ALERTING:
        for share in sorted(set(v1.get(arm, {})) | set(v2.get(arm, {})), key=float):
            for lv in sorted(set(v1.get(arm, {}).get(share, {})) | set(v2.get(arm, {}).get(share, {})), key=lambda k: (k == DHAKA, k != DHAKA and float(k))):
                out.setdefault(arm, {}).setdefault(share, {})[lv] = {"v1": pick(v1.get(arm, {}).get(share, {}).get(lv)), "v2": pick(v2.get(arm, {}).get(share, {}).get(lv))}
    return out


def qlearning_dhaka() -> dict | None:
    """RQ2c: where the ambulance stood when Q-learning signals made it slower at Dhaka density (research/ambulance_rq2/scripts/qlearning_inspect_summary.py)."""
    p = EVIDENCE / "inspect/dhaka/qlearning.json"
    return json.loads(p.read_text()) if p.exists() else None


def makeway_choice() -> dict | None:
    p = EVIDENCE / "makeway_v2/choice.json"
    return json.loads(p.read_text()) if p.exists() else None


def why_dhaka(a: pd.DataFrame) -> dict:
    """The Why correlations for the Dhaka-density row alone (its alert runs)."""
    d = a[a.level == DHAKA]
    return {} if d.empty else {"saved_vs_free_width": spearman(d.base_free, d.saved_s), "saved_vs_queue": spearman(d.base_queue, d.saved_s),
                               "saved_vs_siren_blocked_s": spearman(d.base_blocked, d.saved_s), "saved_vs_yield_share": spearman(d.yield_share, d.saved_s),
                               "free_width_m_mean": round(float(d.base_free.mean()), 2), "queue_mean": round(float(d.base_queue.mean()), 2),
                               "siren_blocked_s_median": round(float(d.base_blocked.median()), 1)}


def figures(tab: dict, front: dict, j: pd.DataFrame, levels: list, anchor: dict, dl: dict | None = None) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fd = RQ2 / "figures"
    fd.mkdir(parents=True, exist_ok=True)
    paths = []
    f, ax = plt.subplots(figsize=(6.5, 4.2))
    for i, (arm, share) in enumerate((("alert", "1"), ("alert_preemption", "1"), ("rl_signals", "0"), ("rl_signals_alert", "1"))):
        by = tab.get(arm, {}).get(share, {})
        xs = [lv for lv in levels if lv != DHAKA and K(lv) in by]
        if xs:
            med = [by[K(x)]["saved_s_median"] for x in xs]
            ax.errorbar(xs, med, yerr=[[m - by[K(x)]["saved_s_q25"] for m, x in zip(med, xs)], [by[K(x)]["saved_s_q75"] - m for m, x in zip(med, xs)]],
                        marker="o", capsize=3, label=ARMS[arm] + (" (all equipped)" if share == "1" else ""))
        if DHAKA in by and dl and dl.get("reached"):
            c, xd = by[DHAKA], max(l for l in levels if l != DHAKA) + 1.5
            ax.errorbar([xd + (i - 1.5) * 0.15], [c["saved_s_median"]], yerr=[[c["saved_s_median"] - c["saved_s_q25"]], [c["saved_s_q75"] - c["saved_s_median"]]], marker="D", capsize=3,
                        color=ax.lines[-1].get_color() if ax.lines else None, linestyle="none")
    if dl and dl.get("reached") and any(DHAKA in tab.get(a, {}).get(s, {}) for a, s in (("alert", "1"), ("rl_signals", "0"))):
        xd = max(l for l in levels if l != DHAKA) + 1.5
        ax.axvline(xd - .75, color="grey", lw=.6)
        gl = [l for l in levels if l != DHAKA]
        ax.set_xticks(gl + [xd], [f"x{l:g}" for l in gl] + [f"{dl['label']}\n{dl['INT_density_median']:g} vs {dl['recorded']['density_median']:g}\nveh/km recorded"], fontsize=7)
    if anchor.get("reached_before_gridlock") and anchor.get("closest_scale"):
        ax.axvline(anchor["closest_scale"], color="grey", linestyle=":", label="closest to Dhaka's recorded density")
    ax.axhline(0, color="black", lw=.6); ax.set_xlabel("demand (x the generated Dhaka demand)"); ax.set_ylabel("ambulance time saved (s): median, bars 25-75 %")
    ax.set_title("RQ2: time saved against density" + ("\nwhole network (lines): Dhaka's recorded density not reached; corridor at Dhaka density (diamonds)" if not anchor.get("reached_before_gridlock") else ""), fontsize=8); ax.grid(alpha=.3); ax.legend(fontsize=7)
    f.tight_layout(); p = fd / "rq2_density.png"; f.savefig(p, dpi=130); plt.close(f); paths.append(p)
    f, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    for ax, arm in zip(axes, ("alert", "alert_preemption")):
        for lv in levels:
            xs = [float(s) * 100 for s in SHARES if K(lv) in tab.get(arm, {}).get(f"{s:g}", {})]
            if xs:
                ax.plot([0] + xs, [0] + [tab[arm][f"{s / 100:g}"][K(lv)]["saved_pct_median"] for s in xs], label=NAME(lv), **({"color": "black", "linestyle": "--", "marker": "D"} if lv == DHAKA else {"marker": "o"}))
        ax.axhline(HELP_PCT, color="grey", linestyle="--", lw=.8)
        ax.set_title(ARMS[arm], fontsize=10); ax.set_xlabel("vehicles that receive the alert (%)"); ax.set_ylabel("median time saved (% of siren-only trip)"); ax.grid(alpha=.3); ax.legend(fontsize=6.5)
    f.suptitle(f"Where the alert stops helping (dashed: {HELP_PCT:g} %)", fontsize=10)
    f.tight_layout(); p = fd / "rq2_share.png"; f.savefig(p, dpi=130); plt.close(f); paths.append(p)
    a = j[j.arm.isin(["alert", "alert_preemption"])]
    f, axes = plt.subplots(1, 3, figsize=(15, 4.2))
    axes[0].scatter(a.base_free, a.saved_s, s=10, alpha=.5); axes[0].set_xlabel("free width ahead of the ambulance, siren-only run (m)")
    axes[1].scatter(a.base_queue, a.saved_s, s=10, alpha=.5, color="tab:red"); axes[1].set_xlabel("queue at the route's signals, siren-only run (vehicles)")
    axes[2].scatter(a.base_blocked, a.saved_s, s=10, alpha=.5, color="tab:green"); axes[2].set_xlabel("seconds the siren-only ambulance stood blocked")
    for ax in axes:
        ax.set_ylabel("time saved by the alert (s)"); ax.grid(alpha=.3); ax.axhline(0, color="black", lw=.6)
    f.suptitle("Why: room to move aside, queues, and time blocked (each point a paired run)", fontsize=10)
    f.tight_layout(); p = fd / "rq2_why.png"; f.savefig(p, dpi=130); plt.close(f); paths.append(p)
    return [str(x.relative_to(REPO)) for x in paths]


def build() -> str:
    ladder = json.loads((RQ2 / "ladder.json").read_text())["levels"]
    df = rows(2)
    tab_v1 = table(paired(rows(1)))                                             # the make-way v1 record, for the old-vs-new table only
    dl = dhaka_level()
    levels = [l["scale"] for l in ladder] + ([DHAKA] if (df.get("level") == DHAKA).any() else [])
    j = paired(df)
    tab = table(j)
    front = frontier(tab, levels)
    a = j[j.arm.isin(["alert", "alert_preemption"])]
    g = a[a.level != DHAKA]                                                     # the whole-network Why, unchanged; the corridor's is why_dhaka
    why = {"saved_vs_free_width": spearman(g.base_free, g.saved_s), "saved_vs_queue": spearman(g.base_queue, g.saved_s),
           "saved_vs_siren_blocked_s": spearman(g.base_blocked, g.saved_s),
           "saved_vs_yield_share": spearman(g.yield_share, g.saved_s), "free_width_by_scale": {s: round(float(x.base_free.mean()), 2) for s, x in g.groupby("level")},
           "queue_by_scale": {s: round(float(x.base_queue.mean()), 2) for s, x in g.groupby("level")},
           "yield_share_by_scale": {s: round(float(x.yield_share.dropna().mean()), 3) for s, x in g.groupby("level") if x.yield_share.notna().any()}}
    anchor = dhaka_anchor(ladder)
    gap = density_gap(dl)
    fig = figures(tab, front, j, levels, anchor, dl)
    dsent = dhaka_sentence(dl, tab)
    sd, ql, mc = slowdown(), qlearning_dhaka(), makeway_choice()
    wd = why_dhaka(a)
    ovn = old_vs_new(tab_v1, tab)
    summary = {"generated_utc": datetime.now(timezone.utc).isoformat(), "city": "Dhaka", "dataset": "Dhaka twin, generated demand (SYNTHETIC_WHAT_IF, uncalibrated), OpenStreetMap network",
               "question": "How much time does the ambulance alert save, at which traffic densities and equipped shares, against which baselines, and why?",
               "ladder": ladder, "saved": tab, "frontier": front, "why": why, "dhaka_anchor": anchor, "arms": ARMS, "help_pct": HELP_PCT,
               "runs": int(len(df)), "paired_runs": int(len(j)), "findings": {**findings(tab, front, why, ladder, anchor, j, levels), **({"dhaka_density": dsent} if dsent else {}),
                            **({"why_dhaka": why_dhaka_sentence(wd, why["free_width_by_scale"])} if why_dhaka_sentence(wd) else {}),
                            **({"makeway": makeway_sentence(mc)} if mc else {}),
                            **({"qlearning_dhaka": ql["reading"]} if ql else {}), **({"density_gap": gap["text"]} if gap else {})},
               "dhaka_level": dl, "why_dhaka": wd, "plain": plain(tab, j), "city_id": CITY,
               "makeway": {"current": settings_makeway(), "choice": mc and {k: mc[k] for k in ("rule", "why_not_a_cited_value", "chosen_by_rule_as_fixed", "amendment", "chosen_distance_m")}},
               "v1_record": {"folder": "results/emergency/dhaka/rq2/record_v1_makeway_artefact", "slowdown": sd, "reading": sd and sd["reading"]},
               "old_vs_new": ovn, "qlearning_dhaka": ql,
               "density_gap": gap, "figures": fig,
               "caveats": ["all traffic is simulated (SUMO); the demand is generated, not calibrated to Dhaka counts",
                           "the ambulance's 3.4 km route crosses 2 signals; the Q-learning baseline controls the 3 signals within 500 m of it",
                           "ITS-G5 only in the sweep; C-V2X and 4G at one density are in the earlier table",
                           "SUMO 1.27.1's bluelight device crashes on some seeds; a crashed seed is replaced by the next one",
                           "the simulation does not reach Dhaka's recorded density on the INT section (see density_gap): every ambulance number here is from traffic lighter "
                           "on that road than Dhaka's recorded morning, and is not a statement about Dhaka at its recorded density",
                           *([f"Dhaka-density row: a corridor cut {dl['buffer_m']:g} m around the route ({dl['edges_kept']} of {dl['edges_full']} roads), with no traffic from the rest of the city",
                              "Dhaka-density row: one recorded day per camera (INT 2026-04-19, BM 2026-04-20), two different days merged into one 07:00-08:00 window",
                              f"Dhaka-density row: the density matches ({dl['INT_density_median']} vs {dl['recorded']['density_median']} vehicles/km) but the flow does not "
                              f"({dl['INT_entered_per_hour_median']} vs {dl['recorded']['flow_veh_h_median']} vehicles/h): at the same density, traffic on the simulated section moves slower than the recorded traffic",
                              f"Dhaka-density row: at the full recorded counts the corridor overshoots ({dl['full_counts_INT_density_median']} vehicles/km on INT, {dl['full_counts_INT_entered_median']} vehicles/h through); "
                              f"the counts are scaled to x{dl['scale']:g} to match the density, and the density reached does not rise smoothly with the scale (see tried scales)",

                              "Dhaka-density row: the route's signal programmes are unchanged by the cut" if dl["signals_same_programme"] else "Dhaka-density row: netconvert changed a route signal programme (see calibration.json)"]
                             if dl and dl.get("reached") else []),
                           "every alerting arm uses make-way v2 (configs/ambulance.yaml): alerted vehicles keep their own route lane changes and only those within "
                           f"{settings_makeway().get('distance_m')} m ahead move aside; no published distance for an electronic alert exists, so 50 and 100 m were piloted and "
                           "chosen by a rule fixed beforehand and amended once by the owner after the pilot (evidence/ambulance_rq2/makeway_v2/choice.json)",
                           "the make-way v1 results (a circular-wait artefact) are kept as a labelled record in record_v1_makeway_artefact/ and appear only in the old-vs-new table"]}
    RQ2.mkdir(parents=True, exist_ok=True)
    p = RQ2 / "summary.json"
    p.write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    md = ["# RQ2 ambulance alert — summary", "", *[f"- {v}" for v in summary["findings"].values()], "", "## Time saved (s): median [25 %, 75 %]; mean ± sd; runs more than 5 s slower than the siren alone", "",
          "| Arm | Share | " + " | ".join(LABEL(lv) for lv in levels) + " |", "|---|---|" + "---|" * len(levels)]
    for arm in ARMS:
        for share, by in sorted(tab.get(arm, {}).items(), key=lambda kv: float(kv[0])):
            md.append(f"| {ARMS[arm]} | {float(share) * 100:g} % | " + " | ".join(
                (f"{by[K(lv)]['saved_s_median']} [{by[K(lv)]['saved_s_q25']}, {by[K(lv)]['saved_s_q75']}]; {by[K(lv)]['saved_s']} ± {by[K(lv)]['saved_s_sd']}; {by[K(lv)]['slower_runs']} slower"
                 if K(lv) in by else "–") for lv in levels) + " |")
    md += ["", "## Density ladder (siren only)", "", "| Demand | Vehicles | Section density (veh/km) | Ambulance (s) | Not arrived | Teleports | Gridlock |", "|---|---|---|---|---|---|---|"]
    md += [f"| x{l['scale']:g} | {l['vehicles']} | {l['section_density_veh_km']} | {l['no_alert_travel_s']} | {l['ambulance_not_arrived']}/{len(l['seeds'])} | {l['teleport_share']:.1%} | {'yes' if l['gridlock'] else 'no'} |" for l in ladder]
    if dl and dl.get("reached"):
        md += [f"| {dl['label']} (corridor x{dl['scale']:g}) | – | {dl['INT_density_median']} (INT, median of {len(dl['density_seeds'])} seeds; recorded {dl['recorded']['density_median']}) | – | – | – | – |"]
    md += ["", "## Old (make-way v1, artefact) against new (v2): median saved [25 %, 75 %]; slower runs", "",
           "| Arm | Share | Level | v1 | v2 |", "|---|---|---|---|---|"]
    fmt = lambda c: f"{c['saved_s_median']} [{c['saved_s_q25']}, {c['saved_s_q75']}]; {c['slower_runs']} of {c['seeds']} slower" if c else "–"
    md += [f"| {ARMS[arm]} | {float(sh) * 100:g} % | {LABEL(lv if lv == DHAKA else float(lv))} | {fmt(c['v1'])} | {fmt(c['v2'])} |"
           for arm, by in ovn.items() for sh, lvs in by.items() for lv, c in lvs.items()]
    md += ["", "## Figures", "", *[f"- `{x}`" for x in fig]]
    (RQ2 / "summary.md").write_text("\n".join(md) + "\n")
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    files = sorted([p, RQ2 / "summary.md", RQ2 / "ladder.json", *(RQ2 / "figures").glob("*.png"), *(RQ2 / "rl").glob("*.json"),
                    *[x for x in (EVIDENCE / "density_gap.json", EVIDENCE / "inspect/slow_alert_run.md", EVIDENCE / "inspect/dhaka/slowdown.json",
                       EVIDENCE / "inspect/dhaka/SLOWDOWN.md", EVIDENCE / "inspect/dhaka/qlearning.json", EVIDENCE / "inspect/dhaka/QLEARNING.md",
                       EVIDENCE / "makeway_v2/choice.json") if x.exists()], *DD.glob("*.json")])
    (EVIDENCE / "SHA256SUMS").write_text("".join(f"{hashlib.sha256(x.read_bytes()).hexdigest()}  {x.relative_to(REPO)}\n" for x in files))
    return str(p)
