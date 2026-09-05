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

import config

sys.path.insert(0, str(config.REPO))

TRAINED = ["STID", "GWNet", "STAEformer", "DCRNN"]
PRETRAINED = ["OpenCity-plus", "Chronos-Bolt"]
RESEARCH = ["XGBoost", "RandomForest", "persistence", "historical_average"]
LABEL = {"STID": "STID", "GWNet": "Graph WaveNet", "STAEformer": "STAEformer", "DCRNN": "DCRNN", "OpenCity-plus": "OpenCity-plus",
         "Chronos-Bolt": "Chronos-Bolt", "XGBoost": "XGBoost", "RandomForest": "Random Forest", "persistence": "Persistence",
         "historical_average": "Historical average"}


def _cards_for(scope: str) -> dict[str, dict]:
    from pipeline.forecasting import basicts_train as bt
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


def _gates_from_card(c: dict) -> dict:
    ev = c.get("evaluation") or {}
    val = ev.get("validation") or {}
    mine = (val.get(c["arch"]) or {}).get("overall") or {}
    per = (val.get("persistence") or {}).get("overall") or {}
    beats_val = mine.get("MAE") is not None and per.get("MAE") is not None and mine["MAE"] < per["MAE"]
    tr = c.get("trust") or {}
    return {"compatible": True, "data_quality": bool((c.get("quality") or {}).get("passed")),
            "verified": bool((c.get("verification") or {}).get("passed")), "beats_val": bool(beats_val),
            "trust": bool(tr.get("eligible"))}


def _entry(model: str, family: str, gates: dict, **extra) -> dict:
    ok = all(gates.values())
    return {"model": model, "label": LABEL.get(model, model), "family": family, "gates": gates, "eligible": ok, **extra}


def registry(scope: str) -> dict:
    """The grouped menu for a scope, with Automatic's choice."""
    from pipeline.forecasting import train_eval as te
    is_dataset = scope.startswith("user:")
    cards = _cards_for(scope) if is_dataset else {}
    ev = _latest_eval(cards) if is_dataset else None
    entries: list[dict] = []
    # trained — city-specific checkpoints
    for m in TRAINED:
        c = cards.get(m)
        if c:
            g = _gates_from_card(c)
            tr = c.get("trust") or {}
            val_mae = ((c.get("evaluation") or {}).get("validation_MAE") or {}).get(m)
            entries.append(_entry(m, "trained", g, trained=True, checkpoint=c["checkpoint"].split("/")[-1], checkpoint_path=c["checkpoint"],
                                  cache_key=c.get("cache_key"), trained_utc=c.get("trained_utc"), trained_on=c.get("trained_on"),
                                  epochs=c.get("epochs"), validation_MAE=val_mae, trust=tr.get("label"), trust_message=tr.get("message"),
                                  test_skill=tr.get("skill"), paper=__import__("pipeline.forecasting.basicts_train", fromlist=["ARCH_PAPER"]).ARCH_PAPER.get(m)))
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
            g = {"compatible": True, "data_quality": True, "verified": True, "beats_val": bool(beats_val),
                 "trust": skill is not None and skill >= te.MARGIN}
            entries.append(_entry(m, "pretrained", g, validation_MAE=v.get("MAE"), test_skill=skill, checkpoint=("amazon/chronos-bolt-small" if m == "Chronos-Bolt" else "OpenCity-plus.pth")))
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
            g = _gates_from_card(c); tr = c.get("trust") or {}
            entries.append(_entry(m, "research", g, trained=True, checkpoint=c["checkpoint"].split("/")[-1], checkpoint_path=c["checkpoint"],
                                  validation_MAE=((c.get("evaluation") or {}).get("validation_MAE") or {}).get(m), trust=tr.get("label"), test_skill=tr.get("skill")))
        elif m in ("persistence", "historical_average"):
            v = ((ev or {}).get("validation") or {}).get(m, {}).get("overall", {}) if ev else {}
            entries.append(_entry(m, "research", {"compatible": True, "data_quality": True, "verified": True, "beats_val": m != "persistence" and False, "trust": False},
                                  validation_MAE=v.get("MAE"), reason="the floor" if m == "persistence" else "training-split mean per slot of day"))
        else:
            entries.append(_entry(m, "research", {"compatible": is_dataset, "data_quality": False, "verified": False, "beats_val": False, "trust": False},
                                  trained=False, reason="not fitted on this data yet"))
    # Automatic: only fully-passing entries, by validation MAE
    passing = [e for e in entries if e["eligible"] and e["model"] not in ("persistence",)]
    passing.sort(key=lambda e: (e.get("validation_MAE") is None, e.get("validation_MAE") or 1e9))
    auto = {"model": passing[0]["model"], "label": passing[0]["label"], "checkpoint": passing[0].get("checkpoint"),
            "why": f"lowest validation MAE ({passing[0]['validation_MAE']:.2f}) among models that passed every gate"} if passing else \
           {"model": "persistence", "label": "Persistence (fallback)", "checkpoint": None,
            "why": "no model passed every gate on this data — reactive fallback" if is_dataset else "live city: the registry's default model, no held-out test"}
    groups = [{"key": "recommended", "title": "Recommended", "items": [{"model": "auto", "label": "Automatic — Recommended", "eligible": True, "family": "recommended",
                                                                        "resolves_to": auto}]},
              {"key": "trained", "title": "Trained on your city", "items": [e for e in entries if e["family"] == "trained"]},
              {"key": "pretrained", "title": "Pretrained", "items": [e for e in entries if e["family"] == "pretrained"]},
              {"key": "research", "title": "Compare models / Research", "items": [e for e in entries if e["family"] == "research"]}]
    return {"scope": scope, "automatic": auto, "groups": groups, "n_trained": sum(1 for e in entries if e.get("trained"))}


def resolve(scope: str, requested: str | None) -> dict:
    """The entry a request maps to (Automatic resolved), with its checkpoint path when it has one."""
    r = registry(scope)
    want = (requested or "auto").strip()
    if want.lower() in ("auto", "automatic", "best", ""):
        want = r["automatic"]["model"]
    for g in r["groups"]:
        for e in g["items"]:
            if e["model"] == want:
                return {**e, "requested": requested or "auto", "automatic": r["automatic"]}
    return {"model": want, "label": want, "eligible": False, "reason": "unknown model", "requested": requested, "automatic": r["automatic"]}
