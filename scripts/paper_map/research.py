"""The research questions, read from their summary files: one place that both docs/PAPER_MAP.md (scripts/paper_map/build.py) and the
README (scripts/readme/build.py) are written from. Every number is read from a file named here, never typed; a measure for which a paper
publishes no comparable number says so instead of an estimate.

Numbering (fixed by the owner on 2026-10-09): ML RQ1-RQ2, networking and safety RQ3-RQ6, then one supporting measurement and the
questions planned but not run. NUMBERING maps every earlier number to the new one, so no frozen question disappears silently.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NONE_PUBLISHED = "— (none published for this measure)"


def load(rel: str):
    return json.loads((ROOT / rel).read_text())


def sha_block(rel: str) -> list[str]:
    p = ROOT / rel
    return ["```", p.read_text().strip(), "```"] if p.exists() else [f"`{rel}` (not found)"]


# (new, question, status, earlier number in docs/EXPERIMENT_PROTOCOL.md, earlier number in the code, result folders and in the app)
NUMBERING = [
    ("RQ1", "Forecasting transfer to Dhaka", "done", "RQ4", "RQ1"),
    ("RQ2", "Forecast-aware closed-loop routing against reactive routing", "Los Angeles only; not run in Dhaka", "RQ1 and RQ6", "—"),
    ("RQ3", "V2X ambulance alert and signal control, corrected make-way rule", "done", "RQ5 (part)", "RQ2"),
    ("RQ4", "Offline phone-to-phone mesh: Epidemic, Spray and Wait, PRoPHET", "done (sparse setting)", "—", "—"),
    ("RQ5", "Weak-signal prefetch: time to a usable route and radio energy", "done", "—", "—"),
    ("RQ6", "Crash detection on the phone, WreckWatch rule", "done (synthetic traces)", "—", "—"),
    ("Supporting", "Ambulance reach from hospitals (isochrones)", "done", "—", "—"),
    ("Planned", "Uncertainty and on-time arrival", "not run", "RQ2", "—"),
    ("Planned", "Sensor coverage needed before forecasts help", "not run", "RQ3", "—"),
]

PLANNED = [
    ("Uncertainty and on-time arrival",
     "not run: RQ1 found no model that beats \"no change\" at 60 minutes in Dhaka, so there is no forecast whose intervals are worth calibrating there yet; "
     "it needs more recorded Dhaka days first."),
    ("Sensor coverage needed before forecasts help",
     "not run: RQ2 has not yet shown a traffic benefit from forecasts in Los Angeles, so there is no benefit yet to measure against sensor coverage."),
]


def numbering_table() -> list[str]:
    return ["| New | Question | Status | Earlier number in `docs/EXPERIMENT_PROTOCOL.md` | Earlier number in code, result folders and the app |",
            "|---|---|---|---|---|", *[f"| {a} | {b} | {c} | {d} | {e} |" for a, b, c, d, e in NUMBERING]]


def _repro(model: str, dataset: str) -> dict:
    return next(r for r in load("results/upstream/REPRODUCTIONS.json") if r["model"] == model and r["dataset"] == dataset)


def _rq3_module():
    spec = importlib.util.spec_from_file_location("paper_map_rq3", ROOT / "research/ambulance_rq2/scripts/paper_map_rq2.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ------------------------------------------------------------------------------------------------------------------------------ RQ1
def rq1() -> dict:
    S = load("results/forecasting/rq1/summary.json")
    rep = load("evidence/forecasting/reproduce/SUMMARY.json")
    md = (ROOT / "results/forecasting/rq1/summary.md").read_text()
    tables = md[md.index("## Los Angeles"):md.index("## Figures")].replace("## ", "#### ")
    patch = next(r for r in load("results/forecasting/patchstg_largest.json") if r["region"] == "SD" and r["mode"] == "train")
    bolt = next(r for r in rep["chronos_bolt_small"]["rows"] if r["dataset"] == "exchange_rate")
    d = S["dhaka"]
    best = lambda h: min(((k, v[h]["mae"]) for k, v in d.items() if k != "persistence" and h in v), key=lambda kv: kv[1])
    names = S["names"]
    readme_rows = []
    for model, ds in (("Graph WaveNet", "METR-LA"), ("Graph WaveNet", "PEMS-BAY"), ("OpenCity", "cross-city (zero-shot)")):
        r = _repro(model, ds)
        readme_rows.append((f"{model}, {ds}, {r['metric']}", f"{r['published']:g}", f"{r['ours']:g}", "—"))
    readme_rows.append(("PatchSTG, LargeST-SD, 12-step average MAE (trained with the authors' recipe)", f"{patch['published']['mae']:g}", f"{patch['average']['mae']:g}", "—"))
    readme_rows.append(("Chronos-Bolt-small, exchange_rate, MASE", f"{bolt['published_MASE']:g}", f"{bolt['ours_MASE']:g}", "—"))
    for h in ("15", "60"):
        k, v = best(h)
        readme_rows.append((f"Dhaka (DhaTraX), {h}-minute MAE km/h: best zero-shot ({names.get(k, k)}) against persistence", NONE_PUBLISHED,
                            "—", f"{v} against {d['persistence'][h]['mae']}"))
    section = [
        "**Question.** " + S["question"], "",
        "**Data.**",
        "- **METR-LA** (Los Angeles, 207 loop detectors, 2012-03-01 to 2012-06-27) and **PEMS-BAY** (San Francisco Bay Area, 325 detectors, 2017-01-01 to 2017-06-30). Both from the DCRNN release (Li et al., ICLR 2018), in mph.",
        "- **DhaTraX v1.0** (Dhaka, CC BY 4.0): 5-minute median speed in km/h at three camera sites, one recorded day each (BS 2026-04-06, INT 2026-04-19, BM 2026-04-20). The authors did not validate the calibration.", "",
        "**Models and licences** (`third_party/SOURCES.md`, \"Forecasting comparison, RQ1\"):",
        "- **Baselines:** persistence; the historical average by time of day; the historical average by time of day and weekday (from the train split).",
        "- **Classical:** random forest and XGBoost.",
        "- **Zero-shot:** Chronos-Bolt-small, Chronos-2 (one road at a time, and all roads together) and TimesFM 2.5, all Apache-2.0.",
        "- **Trained** with the BasicTS harness (Apache-2.0): DCRNN, GWNet, MegaCRN, STAEformer, STID and D2STGNN on METR-LA; GWNet, STID and DCRNN on PEMS-BAY.", "",
        "**Reproduced first** (`results/upstream/REPRODUCTIONS.json`, `results/forecasting/patchstg_largest.json`, `evidence/forecasting/reproduce/SUMMARY.json`):",
        *[f"- **{m}, {ds}** ({_repro(m, ds)['metric']}): published {_repro(m, ds)['published']:g} ({_repro(m, ds)['published_source']}), ours {_repro(m, ds)['ours']:g}: {_repro(m, ds)['verdict']}."
          for m, ds in (("Graph WaveNet", "METR-LA"), ("Graph WaveNet", "PEMS-BAY"), ("OpenCity", "cross-city (zero-shot)"))],
        f"- **PatchSTG, LargeST-SD**, 12-step average MAE: published {patch['published']['mae']:g}, ours {patch['average']['mae']:g} (trained with the authors' `main.py`, best epoch {patch['best_epoch']}).",
        f"- **TimesFM 2.5:** its own example matches the output it ships, with a largest difference of {rep['timesfm_2p5']['max_abs_diff']:.1e}.",
        f"- **Chronos-Bolt-small:** {rep['chronos_bolt_small']['verdict']} (rule: {rep['chronos_bolt_small']['rule']}); see the investigation in the file.",
        f"- **Chronos-2:** {rep['chronos_2']['note']}.", "",
        "**Protocol.**",
        "- **METR-LA and PEMS-BAY:** a chronological 70/10/20 split; per seed (11, 23, 37), a contiguous block of 120 test windows; context 96 steps; every road.",
        "- **Dhaka:** rolling origin over each day, with a one-hour context.",
        "- **Metrics:** BasicTS's masked MAE, RMSE and MAPE (0 = sensor outage), at 15, 30 and 60 minutes. Mean ± sd over seeds; for Dhaka, over the three sites.",
        "- **Unseen city:** trees trained on METR-LA only, on speeds scaled by each window's own context mean, run unchanged on PEMS-BAY and Dhaka, and compared with the same recipe trained at home.",
        "- **Why Dhaka differs:** weekday 06:00-19:00 days; stop-and-go share (steps changing by more than 30 % of free-flow), congested share, coefficient of variation, and autocorrelation at 5-60 minutes.", "",
        "### Results", "", tables.rstrip(), "",
        "### The finding", "", *[f"- {x}" for x in S["findings"]["lab"]], f"- {S['findings']['unseen_city']}", "",
        "### Why", "", S["findings"]["why"], "",
        "### Figures", "", *[f"- `{x}`" for x in S["figures"]], "",
        "### Threats to validity", "", *[f"- {c}" for c in S["caveats"]],
        "- Protocol B scores 120 windows per seed, not the full test split; our trained models' full-split numbers against the published ones are in `results/forecasting/trained_results.json`.", "",
        "### Evidence", "", "SHA-256 of every result file and figure (`evidence/forecasting/rq1/SHA256SUMS`):", "", *sha_block("evidence/forecasting/rq1/SHA256SUMS"), ""]
    k60, v60 = best("60")
    return {"id": "RQ1", "group": "ML", "title": "Forecasting transfer to Dhaka: how far ahead, and why Dhaka differs", "city": "Los Angeles, San Francisco Bay Area, Dhaka",
            "summary": "results/forecasting/rq1/summary.json", "readme_rows": readme_rows,
            "finding": S["findings"]["lab"][2], "why": S["findings"]["why"].split(". So ")[0] + ".",
            "plain_finding": f"In Dhaka no model beats \"no change\" an hour ahead ({names.get(k60, k60)} {v60} km/h against persistence {d['persistence']['60']['mae']} km/h); at 15 and 30 minutes zero-shot models are slightly better.",
            "caveats": S["caveats"], "section": section}


# ------------------------------------------------------------------------------------------------------------------------------ RQ2
def rq2() -> dict:
    C = load("results/v2x/controller_status.json")["current"]
    pct = lambda x: f"{x['mean_pct']:+.2f} % (95 % CI {x['ci95'][0]:+.2f} to {x['ci95'][1]:+.2f}; {x['wins']} wins, {x['losses']} losses): {x['label']}"
    readme_rows = [("Vehicle-hours against reactive rerouting (Los Angeles twin)", NONE_PUBLISHED, "—", pct(C["vs_reactive"])),
                   ("Vehicle-hours against no rerouting", NONE_PUBLISHED, "—", pct(C["vs_baseline"])),
                   ("Oracle (perfect future speeds) against reactive: is future information worth anything?", NONE_PUBLISHED, "—", pct(C["oracle_vs_reactive"])),
                   ("Dhaka", "—", "—", "not run (RQ1: no Dhaka forecast with skill an hour ahead)")]
    section = [
        "**Question.** Does forecast-aware closed-loop routing, which reroutes equipped vehicles on predicted rather than current speeds, reduce total travel time against reactive rerouting in the digital twin?", "",
        "**Data.** The Los Angeles twin (SUMO on OpenStreetMap); the scenario is named by its run folder. "
        f"Run folder: `{C['run']}` (kept on Google Drive after the storage move; its summary stays here).", "",
        "**Arms (baselines).** No rerouting (baseline) · reactive rerouting on current speeds · oracle rerouting on the true future speeds · the forecast-aware controller "
        f"(`{C['arm']}`); {len(C['seeds'])} evaluation seeds ({', '.join(map(str, C['seeds']))}), unseen during tuning; {C['reroutes_applied']} reroutes applied; forked runs identical up to the fork: {C['fork_identical']}.", "",
        f"**Rule, fixed beforehand.** {C['rule']}.", "",
        "### Results", "",
        "| Comparison (vehicle-hours, mean over paired seeds) | Result |", "|---|---|",
        f"| Forecast-aware against no rerouting | {pct(C['vs_baseline'])} |",
        f"| Forecast-aware against reactive | {pct(C['vs_reactive'])} |",
        f"| Oracle against reactive | {pct(C['oracle_vs_reactive'])} |",
        f"| Teleports against no rerouting | {C['teleports_vs_baseline']} |", "",
        "### The finding", "",
        f"- Future information is worth something: rerouting on the true future speeds beats reactive rerouting ({pct(C['oracle_vs_reactive'])}). Status: FUTURE_INFORMATION_VALUE {C['FUTURE_INFORMATION_VALUE']}.",
        f"- Our forecasts do not yet turn that into a traffic benefit: against reactive {pct(C['vs_reactive'])}. Status: {C['status']}.",
        "- Not run in Dhaka: RQ1 found no model with skill an hour ahead there, and the Dhaka twin's demand is not calibrated.", "",
        "### Why", "", "The oracle arm bounds what any forecast could give on this network. Why the forecast-aware arm falls short of it has not been isolated; "
        "every earlier attempt is kept in `results/v2x/controller_status.json` (`history`), none established.", "",
        "### Threats to validity", "", "- One Los Angeles scenario and one equipped share in the headline run.", "- Five evaluation seeds: the confidence intervals are wide.", "",
        "### Evidence", "", "- `results/v2x/controller_status.json` (`current` and `history`)", f"- controller config hash `{C['controller_config_hash']}`, computed {C['computed_utc']}", ""]
    return {"id": "RQ2", "group": "ML", "title": "Forecast-aware closed-loop routing against reactive routing", "city": "Los Angeles (twin); not run in Dhaka",
            "summary": "results/v2x/controller_status.json", "readme_rows": readme_rows,
            "finding": f"Perfect future speeds beat reactive rerouting ({pct(C['oracle_vs_reactive'])}); our forecasts do not yet ({pct(C['vs_reactive'])}).",
            "why": "Future speeds are worth something here (the oracle), but why our forecasts fall short of it has not been isolated.",
            "caveats": ["one Los Angeles scenario; five evaluation seeds", "not run in Dhaka"], "section": section}


# ------------------------------------------------------------------------------------------------------------------------------ RQ3
def rq3() -> dict:
    m = _rq3_module()
    S = m.S
    P = S["plain"]
    rep = load("evidence/ambulance_rq2/reproduce/SUMMARY.json")["verdict"]
    q = S["saved"]
    dl = S["dhaka_level"]
    readme_rows = [("sumo-rl Q-learning against fixed timing, waiting time over the last 20 % of steps (s)", NONE_PUBLISHED + "; direction of its README figure",
                    f"{rep['ql_last20_mean']} against {rep['fixed_last20_mean']}: {'pass' if rep['pass'] else 'FAIL'}", "—"),
                   *[(f"{S['arms'][arm]}, time saved, s (Dhaka-density corridor, {dl['INT_density_median']} against recorded {dl['recorded']['density_median']} vehicles/km)",
                      NONE_PUBLISHED, "—", f"median {c['saved_s_median']} (25-75 %: {c['saved_s_q25']} to {c['saved_s_q75']}); {c['slower_runs']} of {c['seeds']} runs slower than the siren alone")
                     for arm, share in (("alert", "1"), ("alert_preemption", "1"), ("rl_signals", "0")) for c in [q[arm][share]["dhaka"]]]]
    return {"id": "RQ3", "group": "Networking and safety", "title": "V2X ambulance alert and signal control (make-way v2)", "city": "Dhaka (simulated, generated demand)",
            "summary": "results/emergency/dhaka/rq2/summary.json", "readme_rows": readme_rows,
            "finding": S["findings"]["dhaka_density"], "why": S["findings"]["why"].split(". ")[-1],
            "plain": m.readme_sentence(), "caveats": S["caveats"][:5], "section": m.section()[2:]}


# ------------------------------------------------------------------------------------------------------------------------------ RQ4
def rq4() -> dict:
    M = load("evidence/mesh/dhaka/results.json")
    f = lambda x: f"{x['mean']} ± {x['sd']} (n={x['n']})"
    rows = [(f"{r['name']}: delivery ratio", NONE_PUBLISHED, "—", f(r["delivery_ratio"])) for r in M["rows"]]
    sc = M["scope"]
    dr = [r["delivery_ratio"]["mean"] for r in M["rows"]]
    fewest = min(M["rows"], key=lambda r: r["copies_per_message"]["mean"])
    most = max(r["copies_per_message"]["mean"] for r in M["rows"])
    finding = (f"In this sparse setting the three routers deliver {min(dr) * 100:.1f}-{max(dr) * 100:.1f} % of messages; {fewest['name']} needs "
               f"{fewest['copies_per_message']['mean']} copies per message against up to {most}.")
    section = [
        "**Question.** When the mobile network is down, how many alerts reach other vehicles phone to phone, how fast, and at what cost in copies, with Epidemic, Spray and Wait and PRoPHET?", "",
        f"**Data.** Dhaka's SUMO network (`{M['dataset']['network']}`), demand {M['dataset']['demand']['kind']}, seed {M['dataset']['demand']['seed']}; {M['dataset']['sumo']}.", "",
        f"**Simulator.** {sc['simulator']} (PONS, MIT; `third_party/SOURCES.md`), routers at PONS defaults. Radio {sc['radio']['name']}, range {sc['radio']['range_m']} m ({sc['radio']['source'][:60]}…).", "",
        f"**Protocol.** Window {sc['window_s'][0]}-{sc['window_s'][1]} s; {sc['vehicles_simulated']} of {sc['vehicles_seen']} vehicles present throughout take part; one {sc['messages']['size_bytes']}-byte message every {sc['messages']['interval_s']} s, TTL {sc['messages']['ttl_s']} s; seeds {sc['seeds']}.", "",
        "**Reproduced first.** PONS publishes no reference numbers for this setting; it is used as released (`research/mesh_pons/RESULTS.md`).", "",
        "### Results (SIMULATED, mean ± sd over seeds)", "",
        "| Router | Delivery ratio | Delay of delivered messages, s | Copies per message |", "|---|---|---|---|",
        *[f"| {r['name']} | {f(r['delivery_ratio'])} | {f(r['delay_s'])} | {f(r['copies_per_message'])} |" for r in M["rows"]], "",
        "### The finding", "", f"- {finding}", "",
        "### Why", "", M["reading_rules"][1], "",
        "### Threats to validity", "", *[f"- {x}" for x in M["reading_rules"]], "",
        "### Evidence", "", "- `evidence/mesh/dhaka/results.json` (per-run SHA-256 in `run_sha256`)", "- `research/mesh_pons/RESULTS.md`", ""]
    return {"id": "RQ4", "group": "Networking and safety", "title": "Offline phone-to-phone mesh (Epidemic, Spray and Wait, PRoPHET)", "city": "Dhaka (simulated, sparse setting)",
            "summary": "evidence/mesh/dhaka/results.json", "readme_rows": rows,
            "finding": finding,
            "why": M["reading_rules"][1][0].upper() + M["reading_rules"][1][1:] + ".", "caveats": M["reading_rules"][:2], "section": section}


# ------------------------------------------------------------------------------------------------------------------------------ RQ5
def rq5() -> dict:
    E = load("evidence/prefetch/summary.json")
    rows = {(r["condition"], r["arm"]): r for r in E["rows"]}
    en = E["energy"]["rows"]
    sv = lambda share: [r["saving_vs_as_needed_pct"] for r in en if r["weak_share"] == share]
    same = sum(r["bartendr_j"] == r["now_j"] for r in en)                    # rows where Bartendr's schedule is one download now (audit 2026-10-10)
    sched = (f"Bartendr's schedule adds no extra saving in our runs: in {same} of {len(en)} rows it chose a single download at once, "
             f"the same energy as downloading the pack now")
    readme_rows = [("Time to a usable route on a 2G-like link, s (without → with prefetch)", NONE_PUBLISHED, "—",
                    f"{rows[('2g_like', 'without_prefetch')]['median_time_to_route_s']} → {rows[('2g_like', 'with_prefetch')]['median_time_to_route_s']}"),
                   ("Radio energy saved by prefetching the pack on a good signal against downloading as needed (" + sched.split(":")[0] + ")", NONE_PUBLISHED + " (Bartendr's own setting differs)", "—",
                    f"{min(sv(0.1))}-{max(sv(0.5))} % (estimated from Bartendr's measured power, not measured)")]
    section = [
        "**Question.** Does fetching the route pack while the signal is good (BreadCrumbs) and scheduling downloads into strong-signal stretches (Bartendr) shorten the time to a usable route and save radio energy on a weak link?", "",
        f"**Network.** {E['network']}", "",
        f"**Protocol.** {E['runs_total']} runs in headless Chromium; route pack median {E['pack_bytes_median']} bytes. Energy: {E['energy']['label']}; {E['energy']['profiles']}", "",
        "**References.** " + "; ".join(E["references"]) + ".", "",
        "### Results (SIMULATED network conditions)", "",
        "| Condition | Arm | Route shown | Median time to route, s | Median MB |", "|---|---|---|---|---|",
        *[f"| {r['condition']} | {r['arm']} | {r['route_shown']} | {r['median_time_to_route_s']} | {r['median_mb']} |" for r in E["rows"]], "",
        "| Weak share of route | Seed | Now, J | As needed, J | Bartendr, J | Saving against as needed, % |", "|---|---|---|---|---|---|",
        *[f"| {r['weak_share']} | {r['seed']} | {r['now_j']} | {r['as_needed_j']} | {r['bartendr_j']} | {r['saving_vs_as_needed_pct']} |" for r in en], "",
        "### The finding", "",
        f"- On a 2G-like link the route appears in {rows[('2g_like', 'with_prefetch')]['median_time_to_route_s']} s with the pack against {rows[('2g_like', 'without_prefetch')]['median_time_to_route_s']} s without; on fast 4G there is no difference.",
        f"- Prefetching the pack while the signal is good is estimated to save {min(sv(0.1))}-{max(sv(0.5))} % of radio energy against downloading as needed, more the weaker the route.",
        f"- {sched}.", "",
        "### Why", "", "A weak radio sends slowly and stays powered longer per byte (Bartendr's measurement); fetching once in a strong stretch avoids both.", "",
        "### Threats to validity", "", f"- Not measured: {E['not_measured']}.", f"- Energy is {E['energy']['label']}.", f"- {E['energy']['throughput_rule']}", "",
        "### Evidence", "", f"- `evidence/prefetch/summary.json` (SHA-256 `{E['sha256']}`), `evidence/prefetch/runs/`", ""]
    return {"id": "RQ5", "group": "Networking and safety", "title": "Weak-signal prefetch: time to a usable route and radio energy (Bartendr, BreadCrumbs)",
            "city": "Dhaka route, emulated network", "summary": "evidence/prefetch/summary.json", "readme_rows": readme_rows,
            "finding": f"On a 2G-like link the route appears in {rows[('2g_like', 'with_prefetch')]['median_time_to_route_s']} s with the pack against {rows[('2g_like', 'without_prefetch')]['median_time_to_route_s']} s without; prefetching on a good signal is estimated to save {min(sv(0.1))}-{max(sv(0.5))} % of radio energy ({sched}).", "why": "A weak radio sends slowly and stays powered longer per byte; fetching once in a strong stretch avoids both.",
            "caveats": [f"energy is {E['energy']['label']}", f"not measured: {E['not_measured']}"], "section": section}


# ------------------------------------------------------------------------------------------------------------------------------ RQ6
def rq6() -> dict:
    R = load("evidence/sos/results.json")
    rule = R["rule"]
    readme_rows = [(f"{r['kind']}: peak {r['peak_g']} g", NONE_PUBLISHED, "—", "detected" if r["detected"] else "not detected") for r in R["rows"]]
    section = [
        "**Question.** Does the WreckWatch rule, run on the phone, flag a crash and leave normal riding and hard braking alone?", "",
        f"**Rule.** {rule['source']}. Ours: {rule['threshold_g']} g and {rule['min_speed_kmh']} km/h, then a {rule['countdown_s']} s countdown the person can cancel; nothing is sent outside TEST mode.", "",
        f"**Data.** SYNTHETIC traces: {R['generator']['rate_hz']} Hz, {R['generator']['seconds']} s, seed {R['generator']['seed']}, noise sd {R['generator']['noise_sd_g']} g.", "",
        "### Results (SYNTHETIC)", "", "| Trace | Peak, g | Detected | At, s | Note |", "|---|---|---|---|---|",
        *[f"| {r['kind']} | {r['peak_g']} | {r['detected']} | {r['at_s']} | {r['note']} |" for r in R["rows"]], "",
        "### The finding", "", f"- On these synthetic traces the rule flags the crash jolt only ({R['plain']['detected']} of {R['plain']['traces']}).", "",
        "### Why", "", f"Only the crash jolt passes the {rule['threshold_g']} g threshold; hard braking peaks at {R['plain']['peak_g']['hard_brake']} g.", "",
        "### Threats to validity", "", "- Synthetic traces only: no recorded crash. The speed floor was not exercised (no speed in the traces).", "",
        "### Evidence", "", f"- `evidence/sos/results.json` (SHA-256 `{R['sha256']}`), `evidence/sos/traces.SHA256SUMS`", ""]
    return {"id": "RQ6", "group": "Networking and safety", "title": "Crash detection on the phone (WreckWatch rule)", "city": "none (synthetic traces)",
            "summary": "evidence/sos/results.json", "readme_rows": readme_rows,
            "finding": f"On synthetic traces the rule flags the crash jolt only ({R['plain']['detected']} of {R['plain']['traces']}).",
            "why": f"Only the crash jolt passes {rule['threshold_g']} g.", "caveats": ["synthetic traces only; no recorded crash"], "section": section}


# ------------------------------------------------------------------------------------------------------------------------------ reach
def reach() -> dict:
    R = load("results/reach/dhaka/summary.json")
    p = R["plain"]["map_pct"]
    readme_rows = [(f"Share of Dhaka's {R['grid']['points']} grid points within {b} minutes of an emergency hospital", NONE_PUBLISHED, "—", f"{p[str(b)]} %") for b in R["bounds_min"]]
    section = [
        "**Question.** How much of Dhaka can reach a hospital with an emergency department within 10, 20 and 30 minutes by car?", "",
        f"**Data.** {R['hospitals_file']['rule']} (fetched {R['hospitals_file']['fetched_utc'][:10]}); OpenStreetMap extract {R['extract']['path']} {R['extract']['date']}; routed by {R['engine']} ({R['profile']}), {R['time_source']}. {R['credit']}.", "",
        f"**Protocol.** A {R['grid']['step_m']} m grid ({R['grid']['points']} points); each point's time to its nearest hospital.", "",
        "### Results", "", "| Within | Share of grid points (map speeds) |", "|---|---|", *[f"| {b} min | {p[str(b)]} % |" for b in R["bounds_min"]], "",
        "### The finding", "", f"- {p['30']} % of the grid is within 30 minutes of an emergency hospital at map speeds.", "",
        "### Threats to validity", "", "- Map speeds, not live traffic." + (" With DhaTraX's recorded speeds on the two camera sections, every share is unchanged." if R["plain"]["recorded_pct"] == p else ""), "",
        "### Evidence", "", f"- `results/reach/dhaka/summary.json` (SHA-256 `{R['sha256']}`), `evidence/reach/dhaka/`", ""]
    return {"id": "Supporting", "group": "Supporting", "title": "Ambulance reach from hospitals (isochrones)", "city": "Dhaka (map speeds)",
            "summary": "results/reach/dhaka/summary.json", "readme_rows": readme_rows,
            "finding": f"{p['30']} % of Dhaka's grid is within 30 minutes of an emergency hospital at map speeds ({p['10']} % within 10).",
            "why": "Not analysed: the study measures reach; it does not test causes.", "caveats": ["map speeds, not live traffic"], "section": section}


def all_questions() -> list[dict]:
    return [rq1(), rq2(), rq3(), rq4(), rq5(), rq6(), reach()]
