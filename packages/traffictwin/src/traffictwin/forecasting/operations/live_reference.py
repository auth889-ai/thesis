"""Short-horizon congestion prediction for a live Dhaka corridor — and an honest label on it.

    from predict_live import predictor
    predictor.predict("karwanbazar_to_shahbagh", current_state="TRAFFIC_JAM")

TWO THINGS ARE KEPT STRICTLY APART, because conflating them is the easiest way to lie with this
project:

    LIVE DHAKA INPUT
        The current state comes from a live Google Routes call on a real Dhaka corridor. The
        forward projection uses an empirical transition model built from THIS PROJECT'S OWN
        recorded congestion verdicts — derived classes we computed and are entitled to keep, not
        stored Google route content.

    MODEL VALIDATED ON REAL BENCHMARK DATA
        Graph WaveNet, STID and STAEformer reproduce their published error on METR-LA and PEMS-BAY.
        Those are Los Angeles and Bay Area loop detectors. They say nothing about Dhaka.

WHAT IS DELIBERATELY NOT CLAIMED
    No Dhaka MAE. The recorded history is ~21 hours of one weekday over six corridors, and the
    labels are congestion CLASSES derived from Google ETAs, not measured ground truth. That is
    enough for a runtime heuristic and nowhere near enough to validate accuracy, so every response
    carries `dhaka_accuracy_claimed: false` and the hit rate below is labelled
    NOT_A_VALIDATED_ACCURACY_CLAIM. When enough lawful Dhaka ground truth exists this module is
    where a real evaluation would go.

METHOD
    For each horizon we count, over the recorded history, how often a corridor observed in state S
    was in state S' roughly h minutes later. Pairs are matched on TIME rather than on position in
    the series: the recorder's spacing is irregular (median ~152 s, with occasional 15-minute
    gaps), so a positional offset would quietly pair observations nowhere near the intended
    horizon. The prediction is that empirical distribution conditioned on the live state.
    Persistence — the state simply holds — is reported alongside as the floor any method must beat.
"""
from __future__ import annotations

import json
from bisect import bisect_left
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from traffictwin.common.evidence_paths import REPO
HISTORY = REPO / "results/artifacts/live_dhaka/normalized/google_routes_runtime_reference.jsonl"
BIN_S = 300
HORIZONS_MIN = (5, 15, 30, 60)

# The recorder's four classes; the live API's three map onto them.
STATES = ("FREE_FLOW", "SLOW", "CONGESTED", "SEVERE")
LIVE_TO_RECORDED = {"NORMAL": "FREE_FLOW", "SLOW": "SLOW", "TRAFFIC_JAM": "CONGESTED"}
RECORDED_TO_LIVE = {"FREE_FLOW": "NORMAL", "SLOW": "SLOW",
                    "CONGESTED": "TRAFFIC_JAM", "SEVERE": "TRAFFIC_JAM"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Predictor:
    def __init__(self) -> None:
        self._transitions: dict[int, dict[str, Counter]] = {}
        self._n_rows = 0
        self._span: tuple[str, str] | None = None
        self._hit_rate: dict[int, dict] = {}
        self._loaded = False

    # ------------------------------------------------------------- history
    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not HISTORY.exists():
            return
        series: dict[str, list[tuple[datetime, str]]] = defaultdict(list)
        rows = 0
        for line in HISTORY.read_text().splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
                t = datetime.fromisoformat(r["captured_utc"])
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
            state = r.get("congestion_state")
            if state in STATES:
                series[r["corridor_id"]].append((t, state))
                rows += 1
        self._n_rows = rows
        if not rows:
            return
        allt = sorted(t for v in series.values() for t, _ in v)
        self._span = (allt[0].isoformat(), allt[-1].isoformat())

        for h in HORIZONS_MIN:
            target = h * 60.0
            # The recorder's spacing is irregular (median ~152 s, with gaps of 15+ min), so pairs
            # are matched on TIME, not on position in the list. A positional offset would silently
            # pair observations minutes away from the intended horizon.
            tol = min(max(90.0, target * 0.25), 300.0)
            trans: dict[str, Counter] = {s: Counter() for s in STATES}
            persist_hits = 0
            for _cid, obs in series.items():
                obs.sort(key=lambda x: x[0])
                times = [t for t, _ in obs]
                for i, (t0, s0) in enumerate(obs):
                    want = t0.timestamp() + target
                    j = bisect_left(times, want, key=lambda t: t.timestamp())
                    best, best_gap = None, None
                    for k in (j - 1, j, j + 1):
                        if i < k < len(obs):
                            gap = abs(times[k].timestamp() - want)
                            if best_gap is None or gap < best_gap:
                                best, best_gap = k, gap
                    if best is None or best_gap > tol:
                        continue
                    s1 = obs[best][1]
                    trans[s0][s1] += 1
                    if s0 == s1:
                        persist_hits += 1
            self._transitions[h] = trans
            total = sum(sum(c.values()) for c in trans.values())
            hits = sum(c.most_common(1)[0][1] for c in trans.values() if c)
            self._hit_rate[h] = {
                "pairs": total,
                "match_tolerance_s": tol,
                "modal_transition_hit_rate": round(hits / total, 4) if total else None,
                "persistence_hit_rate": round(persist_hits / total, 4) if total else None,
                "label": "NOT_A_VALIDATED_ACCURACY_CLAIM",
                "why": ("computed on ~21 h of one weekday, over congestion CLASSES derived from "
                        "Google ETAs rather than measured ground truth; a runtime heuristic, not "
                        "an evaluation, and not comparable to the benchmark MAE figures"),
            }

    # ------------------------------------------------------------ predicting
    def coverage(self) -> dict:
        self._load()
        return {"rows": self._n_rows, "span_utc": self._span, "bin_s": BIN_S,
                "corridors_with_history": sorted(
                    {s for h in self._transitions.values() for s in h if any(h[s].values())})
                if self._transitions else []}

    def predict(self, corridor_id: str, current_state: str,
                duration_s: float | None = None, static_s: float | None = None) -> dict:
        self._load()
        recorded_now = LIVE_TO_RECORDED.get(current_state, current_state)
        known = recorded_now in STATES

        horizons = []
        for h in HORIZONS_MIN:
            trans = self._transitions.get(h, {})
            counts = trans.get(recorded_now) if known else None
            if counts and sum(counts.values()) >= 10:
                n = sum(counts.values())
                dist = {s: round(counts.get(s, 0) / n, 4) for s in STATES}
                modal = max(dist, key=dist.get)
                horizons.append({
                    "horizon_min": h,
                    "method": "empirical_transition",
                    "predicted_state": modal,
                    "predicted_live_category": RECORDED_TO_LIVE.get(modal, "UNKNOWN"),
                    "confidence": dist[modal],
                    "distribution": dist,
                    "n_observations": n,
                    "persistence_state": recorded_now,
                    "agrees_with_persistence": modal == recorded_now,
                })
            else:
                horizons.append({
                    "horizon_min": h,
                    "method": "persistence_only",
                    "predicted_state": recorded_now if known else "UNKNOWN",
                    "predicted_live_category": RECORDED_TO_LIVE.get(recorded_now, "UNKNOWN"),
                    "confidence": None,
                    "distribution": None,
                    "n_observations": int(sum(counts.values())) if counts else 0,
                    "persistence_state": recorded_now if known else "UNKNOWN",
                    "agrees_with_persistence": True,
                    "note": ("not enough recorded history for this state at this horizon — "
                             "persistence is reported rather than a fabricated distribution"),
                })

        return {
            "corridor_id": corridor_id,
            "generated_at": _now(),
            "input": {
                "label": "LIVE DHAKA INPUT",
                "current_live_category": current_state,
                "mapped_recorded_state": recorded_now if known else "UNKNOWN",
                "duration_s": duration_s,
                "static_duration_s": static_s,
                "source": "google_routes, TRAFFIC_AWARE_OPTIMAL, live",
            },
            "horizons": horizons,
            "method": {
                "name": "empirical transition model over this project's own recorded verdicts",
                "history_rows": self._n_rows,
                "history_span_utc": self._span,
                "hit_rate_on_recorded_history": self._hit_rate,
                "floor": "persistence (the state simply holds) is reported for every horizon",
                "modal_equals_persistence": all(
                    (self._hit_rate.get(h, {}).get("modal_transition_hit_rate")
                     == self._hit_rate.get(h, {}).get("persistence_hit_rate"))
                    for h in HORIZONS_MIN if self._hit_rate.get(h)),
                "reading": ("On this history the modal transition IS persistence at every horizon "
                            "— congestion classes are sticky over an hour. The transition model "
                            "therefore adds a probability distribution and a confidence, not a "
                            "different point prediction. Stated plainly rather than presented as "
                            "if the model were outperforming its own floor."),
            },
            "dhaka_accuracy_claimed": False,
            "why_not": ("~21 h of one weekday, six corridors, labels derived from Google ETAs "
                        "rather than measured ground truth. That is not sufficient lawful Dhaka "
                        "history to state an accuracy figure, so none is given."),
            "benchmark_validation": {
                "label": "MODEL VALIDATED ON REAL BENCHMARK DATA",
                "note": ("Graph WaveNet / STID / STAEformer reproduce their published error on "
                         "METR-LA and PEMS-BAY — Los Angeles and Bay Area loop detectors. Those "
                         "results validate the modelling pipeline, NOT Dhaka accuracy."),
                "evidence": "results/forecasting/phase1_comparison.md",
            },
        }


predictor = Predictor()
