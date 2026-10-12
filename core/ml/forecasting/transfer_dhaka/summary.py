"""RQ1 summary: tables (mean ± sd over seeds), three figures, and "The finding" / "Why" sentences computed from the numbers
(never typed in). Writes results/forecasting/rq1/summary.json and .md, figures/, and copies the hashes to evidence/forecasting/rq1/."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import numpy as np

from core.ml.forecasting.transfer_dhaka.run import CITY, DATASETS, EVIDENCE, OUT

HORIZONS = ("15", "30", "60")
FOUNDATION = ("chronos", "chronos2", "chronos2_mv", "timesfm")
NAMES = {"persistence": "Persistence", "historical_average": "Historical average (time of day)", "historical_average_weekday": "Historical average (time of day + weekday)",
         "random_forest": "Random forest", "xgboost": "XGBoost", "chronos": "Chronos-Bolt-small (zero-shot)", "chronos2": "Chronos-2 (zero-shot)",
         "chronos2_mv": "Chronos-2, all roads together (zero-shot)", "timesfm": "TimesFM 2.5 (zero-shot)"}


def _read(name: str) -> dict:
    p = OUT / name
    return json.loads(p.read_text()) if p.exists() else {}


def lab_table() -> dict:
    """{dataset: {model: {h: {mae, mae_sd, rmse, rmse_sd, mape_pct, mape_pct_sd, seeds}}}}"""
    out: dict = {}
    for r in _read("lab_scores.json").get("rows", []):
        if "results" not in r:
            continue
        for m, by_h in r["results"].items():
            for h, v in by_h.items():
                out.setdefault(r["dataset"], {}).setdefault(m, {}).setdefault(str(h), []).append(v)
    table: dict = {}
    for ds, models in out.items():
        for m, by_h in models.items():
            for h, vs in by_h.items():
                row = {"seeds": len(vs)}
                for k in ("mae", "rmse", "mape_pct"):
                    a = np.array([v[k] for v in vs])
                    row[k], row[f"{k}_sd"] = round(float(a.mean()), 3), (round(float(a.std(ddof=1)), 3) if len(a) > 1 else None)
                table.setdefault(ds, {}).setdefault(m, {})[h] = row
    return table


def dhaka_table() -> dict:
    """{model: {h: {mae (mean over sites), mae_sd (over sites), per_site: {site: mae}}}}"""
    sites = _read("dhaka_scores.json").get("sites", [])
    out: dict = {}
    for s in sites:
        for m, by_h in s["results"].items():
            for h, v in by_h.items():
                out.setdefault(m, {}).setdefault(str(h), {})[s["site"]] = v["mae"]
    return {m: {h: {"mae": round(float(np.mean(list(v.values()))), 3), "mae_sd": round(float(np.std(list(v.values()), ddof=1)), 3) if len(v) > 1 else None, "per_site": v}
                for h, v in by_h.items()} for m, by_h in out.items()}


def transfer_table() -> dict:
    rows = _read("transfer_scores.json").get("rows", [])
    out: dict = {}
    for r in rows:
        for m, by_h in r["results"].items():
            for h, v in by_h.items():
                out.setdefault(m, {}).setdefault(str(h), []).append(v["mae"])
    return {m: {h: {"mae": round(float(np.mean(v)), 3), "mae_sd": round(float(np.std(v, ddof=1)), 3) if len(v) > 1 else None} for h, v in by_h.items()} for m, by_h in out.items()}


def best(models: dict, h: str, among=None) -> tuple[str, float]:
    c = {m: v[h]["mae"] for m, v in models.items() if h in v and (among is None or m in among)}
    m = min(c, key=c.get)
    return m, c[m]


def findings(lab: dict, dk: dict, tr: dict, ch: dict) -> dict:
    """Sentences from the numbers. Each names its city and dataset."""
    out = {}
    lines = []
    for ds in DATASETS:
        if ds not in lab:
            continue
        m, v = best(lab[ds], "60")
        p = lab[ds]["persistence"]["60"]["mae"]
        f, fv = best(lab[ds], "60", FOUNDATION)
        lines.append(f"{CITY[ds]} ({ds}): at 60 minutes the best is {NAMES.get(m, m)} at {v} mph mean absolute error, against {p} for persistence; "
                     f"the best zero-shot model is {NAMES.get(f, f)} at {fv}.")
    if dk:
        nm = lambda m: NAMES.get(m, m.replace("_from_metr_la", " trained on METR-LA"))
        parts = []
        for h in HORIZONS:
            m, v = best({k: x for k, x in dk.items() if k != "persistence"}, h)
            p = dk["persistence"][h]["mae"]
            parts.append(f"at {h} minutes {nm(m)} {v} km/h against persistence {p}" + (" (better)" if v < p else " (not better)"))
        lines.append("Dhaka (DhaTraX, three camera sites, one day each), the best model other than persistence: " + "; ".join(parts) + ".")
    out["lab"] = lines
    if tr:
        moved, home = tr.get("xgboost_trained_on_metr_la", {}).get("60", {}).get("mae"), tr.get("xgboost_trained_on_pems_bay", {}).get("60", {}).get("mae")
        if moved and home:
            out["unseen_city"] = (f"XGBoost trained on METR-LA (Los Angeles) and run unchanged on PEMS-BAY (San Francisco Bay Area) scores {moved} mph at 60 minutes, "
                                  f"against {home} when trained on PEMS-BAY itself: moving cities costs {round((moved / home - 1) * 100, 1)} %. "
                                  "The six graph models cannot move at all: each is fixed to METR-LA's 207 sensors.")
    if ch:
        la, bay, d = ch.get("METR-LA", {}), ch.get("PEMS-BAY", {}), ch.get("DhaTraX", {}).get("sites", {})
        if la and d:
            sg = [round(v["stop_and_go_share"] * 100, 1) for v in d.values()]
            cv = [round(v["cv"], 2) for v in d.values()]
            a12 = [round(v["acf_12"], 2) for v in d.values()]
            cv_sites = ", ".join(f"{k} {round(v['cv'], 2)}" for k, v in d.items())
            out["why"] = (f"Dhaka's speeds jump: {min(sg)}-{max(sg)} % of 5-minute steps change by more than 30 % of free-flow, against "
                          f"{round(la['stop_and_go_share']['median'] * 100, 1)} % on a median METR-LA sensor-day and {round(bay['stop_and_go_share']['median'] * 100, 1)} % on PEMS-BAY. "
                          f"{sum(c > la['cv']['median'] for c in cv)} of {len(cv)} sites vary more than a median Los Angeles sensor-day (coefficient of variation "
                          f"{cv_sites} against {la['cv']['median']}, and {bay['cv']['median']} in the Bay Area); "
                          f"{sum(a < la['acf_12']['median'] for a in a12)} of {len(a12)} remember less an hour ahead "
                          f"(autocorrelation at 60 minutes {min(a12)}-{max(a12)} against {la['acf_12']['median']} and {bay['acf_12']['median']}).")
            moved = dk.get("xgboost_from_metr_la", {}).get("60", {}).get("mae")
            pd_, cost = dk.get("persistence", {}).get("60", {}).get("mae"), None
            if tr.get("xgboost_trained_on_metr_la") and tr.get("xgboost_trained_on_pems_bay"):
                cost = round((tr["xgboost_trained_on_metr_la"]["60"]["mae"] / tr["xgboost_trained_on_pems_bay"]["60"]["mae"] - 1) * 100, 1)
            if moved and pd_ and cost is not None:
                out["why"] += (f" So what a model learns from Los Angeles's smooth roads does not carry: XGBoost trained on METR-LA is {round((moved / pd_ - 1) * 100, 1)} % worse "
                               f"than persistence in Dhaka at 60 minutes, while moving it to the Bay Area costs {cost} %.")
            g = lab.get("METR-LA", {})
            if g.get("persistence") and g:
                b, bv = best({k: v for k, v in g.items() if k not in FOUNDATION and not k.startswith(("historical", "random", "xgboost", "persistence"))}, "60")
                out["why"] += (f" And the models that win in Los Angeles ({NAMES.get(b, b)} {bv} against persistence {g['persistence']['60']['mae']} at 60 minutes) learned months of "
                               "each sensor's history; a Dhaka camera site has one recorded day, so there is nothing to train them on, and only zero-shot models can be used.")
    return out


def figures(lab: dict, dk: dict, tr: dict, ch: dict) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig_dir = OUT / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    show = ("persistence", "historical_average_weekday", "xgboost", "chronos", "chronos2", "timesfm", "GWNet", "STID")
    panels = [(ds, lab[ds], "mph") for ds in DATASETS if ds in lab] + ([("DhaTraX (Dhaka)", dk, "km/h")] if dk else [])
    order = list(show) + ["xgboost_from_metr_la"]
    colour = {m: plt.cm.tab10(i % 10) for i, m in enumerate(order)}                 # one colour per model in every panel
    f, axes = plt.subplots(1, len(panels), figsize=(5.4 * len(panels), 4.4), squeeze=False)
    for ax, (title, models, unit) in zip(axes[0], panels):
        for m in [m for m in order if m in models]:
            y = [models[m][h]["mae"] for h in HORIZONS]
            e = [models[m][h].get("mae_sd") or 0 for h in HORIZONS]
            ax.errorbar([15, 30, 60], y, yerr=e, marker="o", capsize=3, color=colour[m], label=NAMES.get(m, m.replace("_from_metr_la", " (trained on METR-LA)")))
        ax.set_title(title); ax.set_xlabel("horizon (minutes)"); ax.set_ylabel(f"MAE ({unit})"); ax.set_xticks([15, 30, 60]); ax.grid(alpha=.3)
        ax.legend(fontsize=6.5)
    f.suptitle("RQ1: forecast error against horizon (mean ± sd over seeds; Dhaka: over sites)")
    f.tight_layout(); p = fig_dir / "rq1_error_vs_horizon.png"; f.savefig(p, dpi=130); plt.close(f); paths.append(p)
    if tr:
        f, ax = plt.subplots(figsize=(6, 4))
        for name in ("random_forest", "xgboost"):
            for where, style in (("trained_on_pems_bay", "-"), ("trained_on_metr_la", "--")):
                k = f"{name}_{where}"
                if k in tr:
                    ax.errorbar([15, 30, 60], [tr[k][h]["mae"] for h in HORIZONS], yerr=[tr[k][h]["mae_sd"] or 0 for h in HORIZONS], linestyle=style, marker="o", capsize=3,
                                label=f"{NAMES[name]}, {where.replace('_', ' ').replace('metr la', 'METR-LA').replace('pems bay', 'PEMS-BAY')}")
        ax.set_title("Unseen city: PEMS-BAY, trained in LA vs at home", fontsize=10); ax.set_xlabel("horizon (minutes)"); ax.set_ylabel("MAE (mph)"); ax.set_xticks([15, 30, 60]); ax.grid(alpha=.3); ax.legend(fontsize=7)
        f.tight_layout(); p = fig_dir / "rq1_unseen_city.png"; f.savefig(p, dpi=130); plt.close(f); paths.append(p)
    if ch:
        f, axes = plt.subplots(1, 2, figsize=(10, 4))
        for ax, key, label in ((axes[0], "stop_and_go_share", "stop-and-go share of 5-minute steps"), (axes[1], "acf_12", "autocorrelation at 60 minutes")):
            for i, ds in enumerate(DATASETS):
                s = ch[ds][key]
                ax.errorbar([i], [s["median"]], yerr=[[s["median"] - s["p10"]], [s["p90"] - s["median"]]], marker="s", capsize=4, color="tab:blue")
            for j, (site, v) in enumerate(ch["DhaTraX"]["sites"].items()):
                ax.plot([2 + j * 0.15], [v[key]], "o", color="tab:red")
                ax.annotate(site, (2 + j * 0.15, v[key]), fontsize=7, xytext=(3, 3), textcoords="offset points")
            ax.set_xticks([0, 1, 2.15]); ax.set_xticklabels(["METR-LA\n(sensor-days)", "PEMS-BAY\n(sensor-days)", "Dhaka\n(DhaTraX sites)"]); ax.set_ylabel(label); ax.grid(alpha=.3)
        f.suptitle("Why Dhaka differs (LA: median and 10-90 % of sensor-days; Dhaka: each site-day)")
        f.tight_layout(); p = fig_dir / "rq1_why_dhaka.png"; f.savefig(p, dpi=130); plt.close(f); paths.append(p)
    return [str(p.relative_to(OUT.parents[2])) for p in paths]


def build() -> str:
    lab, dk, tr = lab_table(), dhaka_table(), transfer_table()
    ch = _read("character.json").get("measures", {})
    fig = figures(lab, dk, tr, ch)
    summary = {"generated_utc": datetime.now(timezone.utc).isoformat(), "question": "How well can traffic speed be forecast 15, 30 and 60 minutes ahead, in LA and in Dhaka, and why does Dhaka differ?",
               "lab": lab, "dhaka": dk, "unseen_city": tr, "cannot_transfer": _read("transfer_scores.json").get("cannot_transfer", {}), "character": ch,
               "findings": findings(lab, dk, tr, ch), "figures": fig, "names": NAMES,
               "sources": {"metrics": "BasicTS masked metrics (Apache-2.0)", "models": "Chronos-Bolt-small, Chronos-2, TimesFM 2.5 (Apache-2.0); trained checkpoints via BasicTS",
                           "data": "METR-LA and PEMS-BAY (DCRNN release, Li et al., ICLR 2018); DhaTraX v1.0 (CC BY 4.0)"},
               "caveats": ["DhaTraX speeds come from camera tracking whose calibration the authors did not validate; one day per site",
                           "LA units are mph (loop detectors); Dhaka units are km/h (camera median speed)",
                           "the foundation models are deterministic; seeds vary the scored test block and the trees' training"]}
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "summary.json"
    p.write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    md = ["# RQ1 forecasting — summary", "", *[f"- {l}" for l in summary["findings"].get("lab", [])], "", f"**Unseen city.** {summary['findings'].get('unseen_city', '')}", "",
          f"**Why Dhaka differs.** {summary['findings'].get('why', '')}", ""]
    for ds, models in lab.items():
        md += [f"## {CITY[ds]} — {ds} (mph, mean ± sd over seeds)", "", "| Model | 15 min MAE | 30 min MAE | 60 min MAE | 60 min RMSE | 60 min MAPE % |", "|---|---|---|---|---|---|"]
        for m, v in sorted(models.items(), key=lambda kv: kv[1]["60"]["mae"]):
            sd = lambda h, k="mae": f"{v[h][k]} ± {v[h][k + '_sd']}" if v[h].get(k + "_sd") is not None else f"{v[h][k]}"
            md.append(f"| {NAMES.get(m, m)} | {sd('15')} | {sd('30')} | {sd('60')} | {sd('60', 'rmse')} | {sd('60', 'mape_pct')} |")
        md.append("")
    if dk:
        md += ["## Dhaka — DhaTraX (km/h, mean ± sd over 3 sites)", "", "| Model | 15 min | 30 min | 60 min |", "|---|---|---|---|"]
        for m, v in sorted(dk.items(), key=lambda kv: kv[1]["60"]["mae"]):
            md.append(f"| {NAMES.get(m, m.replace('_from_metr_la', ' (trained on METR-LA)'))} | " + " | ".join(f"{v[h]['mae']} ± {v[h]['mae_sd']}" for h in HORIZONS) + " |")
        md.append("")
    md += ["## Figures", "", *[f"- `{f}`" for f in fig]]
    (OUT / "summary.md").write_text("\n".join(md) + "\n")
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    files = sorted([*OUT.glob("*.json"), OUT / "summary.md", *(OUT / "figures").glob("*.png")])
    (EVIDENCE / "SHA256SUMS").write_text("".join(f"{hashlib.sha256(f.read_bytes()).hexdigest()}  {f.relative_to(OUT.parents[2])}\n" for f in files))
    return str(p)
