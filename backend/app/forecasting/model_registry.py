"""THE OPERATIONAL MODEL REGISTRY — what may forecast a dataset or a city, and why.

One question answered per scope ("user:<id>" for an uploaded dataset, or a city id): which
models are *offered*, in four groups, and which one *Automatic* would use.

    recommended   Automatic — Recommended
    trained       STID · Graph WaveNet · STAEformer · DCRNN   (city-specific, trained here)
    pretrained    OpenCity-plus · Chronos-Bolt
    research      XGBoost · Random Forest · persistence · historical average

Every entry carries the gates it passed, read fresh from the cards on disk each call — a training
job that just finished appears without a restart:

    compatible        the model can serve this graph / history (the registry adapters' own gates)
    data_quality      the dataset passed the quality checks
    verified          the checkpoint reloaded and reproduced its reported test error
    beats_val         beat persistence on the VALIDATION split
    trust             passed the held-out test trust gate (ROUTING_ELIGIBLE)

Automatic chooses ONLY among entries with every gate passed, by validation MAE — never by name.
If nothing passes, Automatic falls back to persistence and says so.
"""
from __future__ import annotations

import sys

from backend.app import config

sys.path.insert(0, str(config.REPO))

TRAINED = ["STID", "GWNet", "STAEformer", "DCRNN"]
PRETRAINED = ["OpenCity-plus", "Chronos-Bolt"]
RESEARCH = ["XGBoost", "RandomForest", "persistence", "historical_average"]
LABEL = {"STID": "STID", "GWNet": "Graph WaveNet", "STAEformer": "STAEformer", "DCRNN": "DCRNN", "OpenCity-plus": "OpenCity-plus",
         "Chronos-Bolt": "Chronos-Bolt", "XGBoost": "XGBoost", "RandomForest": "Random Forest", "persistence": "Persistence",
         "historical_average": "Historical average"}


def _cards_for(scope: str) -> dict[str, dict]:
    from traffictwin.forecasting.training import basicts_train as bt
    out: dict[str, dict] = {}
    for c in bt.cards():
        if c["dataset"] == scope:
            prev = out.get(c["arch"])
            if prev is None or (c.get("trained_utc") or "") > (prev.get("trained_utc") or ""):
                out[c["arch"]] = c
    return out


def _latest_eval(cards: dict[str, dict]) -> dict | None:
    """The untrained baselines' scores on this dataset, merged from the cards' evaluations: for
    each baseline the most recent evaluation that actually scored it (research fits score only
    persistence / historical average; the deep-model jobs also score Chronos-Bolt)."""
    merged = {"validation": {}, "test": {}}
    for c in sorted(cards.values(), key=lambda c: c.get("trained_utc") or ""):
        ev = c.get("evaluation") or {}
        for split in ("validation", "test"):
            for m, tab in (ev.get(split) or {}).items():
                if m in PRETRAINED + ["persistence", "historical_average"] and isinstance(tab, dict) and "error" not in tab:
                    merged[split][m] = tab
    return merged if merged["validation"] else None


def current_dataset_hash(scope: str) -> str | None:
    """The hash of the data the harness would serve NOW for this scope (prepared on demand)."""
    from traffictwin.forecasting.training import basicts_train as bt
    from traffictwin.forecasting.training import train_eval as te
    name = bt.bts_name(scope)
    f = bt.BTS / "datasets" / name / "data.dat"
    if not f.exists():
        try:
            bt.prepare(scope)
        except BaseException:                            # noqa: BLE001 - no data, no hash
            return None
    return te.sha256_file(f) if f.exists() else None


def _gates_from_card(c: dict, current_hash: str | None = None) -> dict:
    ev = c.get("evaluation") or {}
    val = ev.get("validation") or {}
    mine = (val.get(c["arch"]) or {}).get("overall") or {}
    per = (val.get("persistence") or {}).get("overall") or {}
    beats_val = mine.get("MAE") is not None and per.get("MAE") is not None and mine["MAE"] < per["MAE"]
    tr = c.get("trust") or {}
    same_data = current_hash is None or c.get("dataset_hash") is None or c.get("dataset_hash") == current_hash
    return {"compatible": bool(same_data), "data_quality": bool((c.get("quality") or {}).get("passed")),
            "verified": bool((c.get("verification") or {}).get("passed")), "beats_val": bool(beats_val),
            "trust": bool(tr.get("eligible"))}


def _entry(model: str, family: str, gates: dict, **extra) -> dict:
    ok = all(gates.values())
    return {"model": model, "label": LABEL.get(model, model), "family": family, "gates": gates, "eligible": ok, **extra}


def registry(scope: str) -> dict:
    """The grouped menu for a scope, with Automatic's choice."""
    from backend.app.forecasting import scientific_prediction
    if scope in scientific_prediction.DATASETS:
        return scientific_prediction.registry(scope)
    from traffictwin.forecasting.training import train_eval as te
    is_dataset = scope.startswith("user:")
    cards = _cards_for(scope) if is_dataset else {}
    cur = current_dataset_hash(scope) if (is_dataset and cards) else None
    ev = _latest_eval(cards) if is_dataset else None
    entries: list[dict] = []
    # trained — city-specific checkpoints
    for m in TRAINED:
        c = cards.get(m)
        if c:
            g = _gates_from_card(c, cur)
            tr = c.get("trust") or {}
            val_mae = ((c.get("evaluation") or {}).get("validation_MAE") or {}).get(m)
            entries.append(_entry(m, "trained", g, trained=True, reason=None if g["compatible"] else "trained on an earlier version of this data — train again", checkpoint=c["checkpoint"].split("/")[-1], checkpoint_path=c["checkpoint"],
                                  cache_key=c.get("cache_key"), trained_utc=c.get("trained_utc"), trained_on=c.get("trained_on"),
                                  epochs=c.get("epochs"), validation_MAE=val_mae, trust=tr.get("label"), trust_message=tr.get("message"),
                                  test_skill=tr.get("skill"), paper=__import__("traffictwin.forecasting.training.basicts_train", fromlist=["ARCH_PAPER"]).ARCH_PAPER.get(m)))
        else:
            entries.append(_entry(m, "trained", {"compatible": is_dataset, "data_quality": False, "verified": False, "beats_val": False, "trust": False},
                                  trained=False, reason="not trained on this data yet" if is_dataset else "trains on uploaded datasets only"))
    # pretrained — scored (without training) by the latest evaluation on this dataset
    for m in PRETRAINED:
        if is_dataset and ev and m in (ev.get("validation") or {}) and "error" not in ev["validation"][m]:
            v = ev["validation"][m]["overall"]; p = ev["validation"]["persistence"]["overall"]
            t = (ev.get("test") or {}).get(m, {}).get("overall") or {}
            beats_val = v.get("MAE") is not None and v["MAE"] < p["MAE"]
            skill = t.get("skill_vs_persistence")
            # a pretrained model is scored on a SAMPLE of test windows for speed; routing trust needs the
            # whole held-out split, so a sampled score keeps it forecast-only until a full evaluation exists
            sampled = ev["validation"][m].get("sampled_windows"); full = ev["validation"][m].get("full_split", False)
            g = {"compatible": True, "data_quality": True, "verified": True, "beats_val": bool(beats_val),
                 "trust": bool(full) and skill is not None and skill >= te.MARGIN}
            entries.append(_entry(m, "pretrained", g, validation_MAE=v.get("MAE"), test_skill=skill, checkpoint=("amazon/chronos-bolt-small" if m == "Chronos-Bolt" else "OpenCity-plus.pth"),
                                  reason=None if full else f"scored on {sampled or '?'} sampled held-out windows — forecast only until scored on the whole split"))
        elif is_dataset:
            entries.append(_entry(m, "pretrained", {"compatible": True, "data_quality": True, "verified": True, "beats_val": False, "trust": False},
                                  reason="not yet scored on this data (train any model to score the baselines)" if m == "Chronos-Bolt"
                                  else "needs ≥ 9 roads and ≥ 288 five-minute steps; scored on the Prediction page"))
        else:
            entries.append(_entry(m, "pretrained", {"compatible": True, "data_quality": True, "verified": True, "beats_val": True, "trust": False},
                                  reason="live corridors: prediction only, no held-out test (Google-derived history is never a test set)"))
    # research
    for m in RESEARCH:
        c = cards.get(m)
        if c:
            g = _gates_from_card(c, cur); tr = c.get("trust") or {}
            entries.append(_entry(m, "research", g, trained=True, reason=None if g["compatible"] else "fitted on an earlier version of this data", checkpoint=c["checkpoint"].split("/")[-1], checkpoint_path=c["checkpoint"],
                                  validation_MAE=((c.get("evaluation") or {}).get("validation_MAE") or {}).get(m), trust=tr.get("label"), test_skill=tr.get("skill")))
        elif m in ("persistence", "historical_average"):
            v = ((ev or {}).get("validation") or {}).get(m, {}).get("overall", {}) if ev else {}
            entries.append(_entry(m, "research", {"compatible": True, "data_quality": True, "verified": True, "beats_val": m != "persistence" and False, "trust": False},
                                  validation_MAE=v.get("MAE"), reason="the floor" if m == "persistence" else "training-split mean per slot of day"))
        else:
            entries.append(_entry(m, "research", {"compatible": is_dataset, "data_quality": False, "verified": False, "beats_val": False, "trust": False},
                                  trained=False, reason="not fitted on this data yet"))
    # ---- pretrained models on a LIVE city: can they serve this history right now? (the adapters' own gates)
    if not is_dataset:
        avail = _live_availability(scope)
        for e in entries:
            if e["family"] == "pretrained" and e["model"] in avail:
                ok, reasons = avail[e["model"]]
                e["gates"]["compatible"] = ok
                e["can_forecast"] = ok
                e["reason"] = None if ok else (reasons[0] if reasons else "cannot serve this history")
    for e in entries:
        if "can_forecast" not in e:
            e["can_forecast"] = bool(e["gates"].get("compatible")) and (e.get("trained") is not False) and e["model"] != "OpenCity-plus" or \
                                (e["model"] == "OpenCity-plus" and bool(e["gates"].get("compatible")) and e.get("validation_MAE") is not None)
        if e["model"] in ("persistence", "historical_average"):
            e["can_forecast"] = True
    # ---- TWO decisions. (1) FORECAST: the best AVAILABLE predictor, by evidence, never by name.
    #      (2) ROUTING: only a model that passed the held-out trust gate may drive prediction-aware routing.
    def val(e):
        return (e.get("validation_MAE") is None, e.get("validation_MAE") or 1e9)
    validated_trained = sorted([e for e in entries if e["family"] == "trained" and e["eligible"]], key=val)
    validated_pre = sorted([e for e in entries if e["family"] == "pretrained" and e["eligible"]], key=val)
    validated_research = sorted([e for e in entries if e["family"] == "research" and e["eligible"] and e["model"] not in ("persistence", "historical_average")], key=val)
    forecast_only = sorted([e for e in entries if e["family"] == "pretrained" and e["can_forecast"] and not e["eligible"]], key=val)
    trained_unvalidated = sorted([e for e in entries if e["family"] == "trained" and e.get("trained") and not e["eligible"] and e["gates"].get("compatible")], key=val)
    if validated_trained:
        f = validated_trained[0]; forecast = {"model": f["model"], "label": f["label"], "checkpoint": f.get("checkpoint"), "status": "VALIDATED",
                                             "local_validation": "PASSED", "why": f"trained on this city and validated on its held-out data (validation MAE {f['validation_MAE']:.2f})"}
    elif validated_pre:
        f = validated_pre[0]; forecast = {"model": f["model"], "label": f["label"], "checkpoint": f.get("checkpoint"), "status": "VALIDATED",
                                         "local_validation": "PASSED", "why": "pretrained model validated on this city's held-out data"}
    elif validated_research:
        f = validated_research[0]; forecast = {"model": f["model"], "label": f["label"], "checkpoint": f.get("checkpoint"), "status": "VALIDATED",
                                              "local_validation": "PASSED", "why": "classical model validated on this city's held-out data"}
    elif forecast_only:
        f = forecast_only[0]
        beat = f["gates"].get("beats_val")
        forecast = {"model": f["model"], "label": f["label"], "checkpoint": f.get("checkpoint"), "status": "FORECAST_ONLY",
                    "local_validation": ("FAILED" if f.get("validation_MAE") is not None and not beat else "SAMPLED" if f.get("validation_MAE") is not None else "UNAVAILABLE"),
                    "why": ("pretrained model; it did not beat persistence on this city's held-out data" if f.get("validation_MAE") is not None and not beat
                            else "pretrained model; beat persistence on sampled held-out windows only — not a full validation" if f.get("validation_MAE") is not None
                            else "pretrained model; no permitted local dataset to validate it on yet")}
    elif trained_unvalidated:
        f = trained_unvalidated[0]; forecast = {"model": f["model"], "label": f["label"], "checkpoint": f.get("checkpoint"), "status": "FORECAST_ONLY",
                                               "local_validation": "FAILED", "why": "trained on this city but did not pass the held-out trust gate"}
    else:
        forecast = {"model": "persistence", "label": "Persistence", "checkpoint": None, "status": "BASELINE", "local_validation": "UNAVAILABLE",
                    "why": "no learned predictor can serve this history yet"}
    routing_model = validated_trained[0] if validated_trained else validated_pre[0] if validated_pre else validated_research[0] if validated_research else None
    routing = ({"policy": "PREDICTION_AWARE", "trusted_model": routing_model["model"], "label": routing_model["label"],
                "why": f"{routing_model['label']} passed the held-out trust gate on this city (skill {routing_model.get('test_skill'):+.0%})"} if routing_model
               else {"policy": "REACTIVE_FALLBACK", "trusted_model": None, "label": None,
                     "why": ("no model has passed a held-out trust gate on this city's own data — routing follows live traffic only"
                             if is_dataset else "no permitted local dataset to validate a forecast on — routing follows live traffic only (the Google-derived history is never a test set)")})
    forecast["routing_eligible"] = routing["policy"] == "PREDICTION_AWARE" and routing["trusted_model"] == forecast["model"]
    auto = {**forecast}                                   # "auto" resolves to the forecast decision
    # ---- the menu: AVAILABLE / VALIDATED ON THIS CITY / PRETRAINED / BASELINES / UNAVAILABLE
    def status_of(e):
        if e["eligible"]:
            return "VALIDATED"
        if e["can_forecast"]:
            return "AVAILABLE"
        return "UNAVAILABLE"
    for e in entries:
        e["status"] = status_of(e)
    def group_of(e):                                    # disjoint groups, in the order the operator reads them
        if e["model"] in ("persistence", "historical_average"):
            return "baselines"
        if e["status"] == "UNAVAILABLE":
            return "unavailable"
        if e["status"] == "VALIDATED":
            return "validated"
        if e["family"] == "pretrained":
            return "pretrained"
        if e["family"] == "research":
            return "baselines"
        return "available"
    titles = [("recommended", "Recommended"), ("available", "Available"), ("validated", "Validated on this city"), ("pretrained", "Pretrained"),
              ("baselines", "Baselines"), ("unavailable", "Unavailable")]
    groups = [{"key": k, "title": t, "items": ([{"model": "auto", "label": "Automatic — Recommended", "eligible": True, "family": "recommended",
                                                  "can_forecast": True, "status": "AVAILABLE", "resolves_to": auto}] if k == "recommended"
                                                else [e for e in entries if group_of(e) == k])} for k, t in titles]
    return {"scope": scope, "automatic": auto, "forecast": forecast, "routing": routing, "groups": groups,
            "n_trained": sum(1 for e in entries if e.get("trained"))}


def _live_availability(scope: str) -> dict[str, tuple[bool, list[str]]]:
    """For a live city: which pretrained adapters can serve its corridor history right now."""
    out: dict[str, tuple[bool, list[str]]] = {}
    try:
        from backend.app.routing import trip_analysis as analyze
        for m in analyze.models_for_city(scope):
            if m["model"] in PRETRAINED:
                out[m["model"]] = (bool(m.get("available")), list(m.get("reasons") or []))
    except (Exception, SystemExit) as exc:              # noqa: BLE001 - a missing recorded series is a reason, not a crash
        out["Chronos-Bolt"] = (False, [f"registry unavailable: {exc}"])
    return out


def state(scope: str) -> dict:
    """The two product decisions for a scope: what forecasts, and whether routing may trust it."""
    r = registry(scope)
    return {"scope": scope, "forecast": r["forecast"], "routing": r["routing"]}


def resolve(scope: str, requested: str | None) -> dict:
    """The entry a request maps to (Automatic resolved), with its checkpoint path when it has one."""
    r = registry(scope)
    want = (requested or "auto").strip()
    if want.lower() in ("auto", "automatic", "best", ""):
        want = r["forecast"]["model"]
    for g in r["groups"]:
        for e in g["items"]:
            if e["model"] == want and e["model"] != "auto":
                return {**e, "requested": requested or "auto", "automatic": r["automatic"], "forecast_decision": r["forecast"], "routing": r["routing"]}
    return {"model": want, "label": want, "eligible": False, "can_forecast": False, "reason": "unknown model", "requested": requested,
            "automatic": r["automatic"], "forecast_decision": r["forecast"], "routing": r["routing"]}
