"""The ambulance study's section of docs/PAPER_MAP.md (RQ3 since 2026-10-09; its result folders keep the name rq2) and the README's everyday
sentence, from results/emergency/dhaka/rq2/summary.json; every number is inserted, never typed. Imported by scripts/paper_map/build.py,
which writes the whole paper map; run alone, it runs that build."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
S = json.loads((ROOT / "results/emergency/dhaka/rq2/summary.json").read_text())
rep = ROOT / "evidence/ambulance_rq2/reproduce/SUMMARY.json"
rep = json.loads(rep.read_text())["verdict"] if rep.exists() else None
md = (ROOT / "results/emergency/dhaka/rq2/summary.md").read_text()
tables = md[md.index("## Time saved"):md.index("## Figures")].replace("## ", "#### ")
ev = (ROOT / "evidence/ambulance_rq2/SHA256SUMS").read_text().strip()
f = S["findings"]
DL = S.get("dhaka_level") or {}


def dhaka_method() -> list[str]:
    """RQ2b: how the Dhaka-density row was built and what it reached, from summary.json's dhaka_level (corridor.py's evidence)."""
    if not DL.get("reached"):
        return ["**Dhaka-density row (RQ2b).** No scale of the recorded counts put the INT section's density inside the recorded range; no row is run.", ""]
    rec = DL["recorded"]
    return ["**Dhaka-density row (RQ2b).**",
            f"- **Corridor:** the edges within {DL['buffer_m']:g} m of the ambulance route ({DL['edges_kept']} of {DL['edges_full']}), cut with SUMO's `netconvert --keep-edges.input-file`, "
            "so gridlock on unrelated roads cannot starve the corridor. " + ("The route's signal programmes are unchanged by the cut." if DL["signals_same_programme"] else "netconvert changed a route signal programme."),
            f"- **Demand:** SUMO's `routeSampler.py` matched to DhaTraX's recorded 5-minute counts at INT and BM, 07:00-08:00 ({DL['sampled_trips']} sampled trips plus "
            f"{DL['background_trips']} uncalibrated background trips), the Dhaka class mix, and the smaller lateral gaps for two-wheelers, rickshaws and CNGs (sublane model, 0.8 m).",
            f"- **Density reached (INT, no ambulance):** at the full counts, {DL['full_counts_INT_density_median']} vehicles/km (overshoot). Scales tried (median over 5 seeds): "
            + "; ".join(f"x{t['scale']:g}: {t['INT_density_median_over_seeds']}" for t in DL["tried"])
            + f". Chosen x{DL['scale']:g}: **{DL['INT_density_median']} vehicles/km** (seeds' 25-75 %: {DL['INT_density_q25']}-{DL['INT_density_q75']}) against the recorded "
            f"**{rec['density_median']}** (07:00-08:00, 25-75 %: {rec['density_q25']}-{rec['density_q75']}); label \"{DL['label']}\".",
            f"- **Flow at that density:** {DL['INT_entered_per_hour_median']} vehicles/h through INT against {rec['flow_veh_h_median']} recorded.",
            "- **Arms:** siren only, alert and alert plus preemption at 25-100 % equipped, Q-learning signals trained 30 episodes on the corridor, with and without the alert; 10 paired seeds each.", ""]


L = ["## RQ3 — V2X ambulance alert and signal control: how far it helps, and why", "",
     "*Result folders and code keep the earlier name RQ2 (`results/emergency/dhaka/rq2/`), because evidence hashes point at them.*", "",
     f"**Question.** {S['question']}", "",
     "**Data.**",
     "- **Network:** the Dhaka twin's OpenStreetMap network.",
     "- **Demand:** the generated demand (randomTrips, SYNTHETIC_WHAT_IF, not calibrated), scaled by SUMO `--scale`.",
     "- **Trip:** the ambulance's 3.4 km route crosses 2 signals and the DhaTraX INT camera section.", "",
     "**Arms (baselines).**",
     "- Siren only (SUMO's bluelight behaviour, no message).",
     "- The alert to equipped vehicles, over ITS-G5.",
     "- The alert plus signal preemption (adaptive-traffic-signal-rl, MIT, reproduced earlier).",
     "- **sumo-rl** Q-learning signals (MIT, commit 86f0fc4), with and without the alert. It controls the 3 signals within 500 m of the route, with 30 training episodes per density level on separate seeds, then frozen.", "",
     "**Reproduced first.** sumo-rl's own `ql_single-intersection.py` against its fixed timing. " + (f"Q-learning's mean total waiting time over the last 20 % of steps is {rep['ql_last20_mean']} s against fixed timing's {rep['fixed_last20_mean']} s: {'pass' if rep['pass'] else 'FAIL'}. The repository publishes no number, so this checks the direction of its README figure. **The fixed-timing comparison is lopsided:** with 42 s greens on this example's routes, the queue under fixed timing grows throughout the run, so the comparison passes trivially. The real evidence is the learning curve: in each of three runs, Q-learning's waiting time falls from " + ", ".join(f"{r['first_10pct']}" for r in json.loads((ROOT / "evidence/ambulance_rq2/reproduce/SUMMARY.json").read_text())["ql"]) + " s in the first tenth to " + ", ".join(f"{r['last_20pct']}" for r in json.loads((ROOT / "evidence/ambulance_rq2/reproduce/SUMMARY.json").read_text())["ql"]) + " s in the last fifth." if rep else "(not yet run)"), "",
     "**Protocol.**",
     "- **Density ladder:** demand ×" + ", ×".join(f"{l['scale']:g}" for l in S["ladder"]) + f", until gridlock ({json.loads((ROOT / 'results/emergency/dhaka/rq2/ladder.json').read_text())['gridlock_rule']}).",
     "- **Equipped shares:** 25, 50, 75 and 100 %.",
     "- **Seeds:** 5 siren-only seeds per level for the gridlock verdict; 10 finished (arm, siren-only) pairs per table cell. A seed is replaced when SUMO's bluelight device crashes.",
     "- **Time saved:** each run against the siren-only run of the same seed and density.",
     *([f"- **Moving aside:** {f['makeway']}"] if f.get("makeway") else []),
     "- **Measures, per run:** free width ahead of the ambulance, the share of alerted vehicles that moved aside, seconds blocked, and queues at the route's signals.", "",
     *(dhaka_method() if S.get("dhaka_level") else []),
     "### Results", "", tables,
     "### The finding", "", *[f"- {v}" for k, v in f.items() if k not in ("why", "why_dhaka", "qlearning_dhaka", "makeway", "density_gap")], "",
     "### Why", "", f.get("why", ""), "", *([f["why_dhaka"], ""] if f.get("why_dhaka") else []), *([f"**Q-learning signals at Dhaka density (inspected).** {f['qlearning_dhaka']} Details: `evidence/ambulance_rq2/inspect/dhaka/QLEARNING.md`.", ""] if f.get("qlearning_dhaka") else []),
     *([f"**Make-way v1, a record (RQ2b).** The earlier results came from a make-way rule with a circular-wait artefact, now corrected: {S['v1_record']['reading']} "
        f"Those results are kept in `{S['v1_record']['folder']}/` and appear only in the old-against-new table.", ""] if S.get("v1_record", {}).get("reading") else []), f.get("density_gap", ""), "",
     "### Figures", "", *[f"- `{x}`" for x in S["figures"]], "",
     "### Threats to validity", "", *[f"- {c}" for c in S["caveats"]], "",
     "### Evidence", "", "```", ev, "```", ""]
# README: the everyday ambulance sentence, filled from the app's own English strings (frontend ambulanceSentence.ts does the same)
import re
EN = json.loads((ROOT / "frontend/src/i18n/locales/en.json").read_text())
fill = lambda k, **v: re.sub(r"\{(\w+)\}", lambda m: str(v[m.group(1)]), EN[k])


def readme_sentence() -> str | None:
    """The everyday sentence, with its tag and where to check it; None before the summary has a plain block."""
    P = S.get("plain")
    if not P:
        return None
    alert = fill("plain.amb.sooner", s=P["alert_s"], trip=P["trip_s"]) if P["alert_s"] > 0 else \
        fill("plain.amb.later", s=-P["alert_s"], trip=P["trip_s"]) if P["alert_s"] < 0 else fill("plain.amb.none", trip=P["trip_s"])
    sent = fill("plain.amb.sentence", where=EN["plain.amb.where.dhaka" if P["level"] == "dhaka" else "plain.amb.where.light"], alert=alert,
                odds=EN["plain.amb.notEveryTime"] if P.get("not_every_time") and P["alert_s"] > 0 else "",
                lights="" if P["signals_s"] is None else fill("plain.amb.lightsLater", s=-P["signals_s"]) if P["signals_s"] < 0 else
                EN["plain.amb.lightsNone"] if P["signals_s"] == 0 else fill("plain.amb.lightsMore" if P["signals_more"] else "plain.amb.lights", s=P["signals_s"]))
    sent = re.sub(r"\s+([;.])", r"\1", sent)
    block = f"> {sent} *(Simulation, Dhaka; demand level: {'the Dhaka-density corridor' if P['level'] == 'dhaka' else 'x' + P['level']}. How we know: `docs/PAPER_MAP.md`, RQ3, and the ambulance card on Research.)*"
    return block


def section() -> list[str]:
    return L


if __name__ == "__main__":
    import runpy
    runpy.run_path(str(ROOT / "scripts/paper_map/build.py"), run_name="__main__")
