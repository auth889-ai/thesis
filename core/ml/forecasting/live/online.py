"""Three forecasters, side by side, on the live twin's detector speeds (core/simulation/live_twin). Every simulated minute each one
predicts every road's speed 15 minutes ahead:

  online     River (BSD-3, 0.26.1): StandardScaler | LinearRegression, one model shared by all roads, learning from each new value.
             Features: the road's speed now and 1, 2, 4, 9 and 14 minutes earlier, each divided by the road's speed limit, plus the
             demand scale. Target: the change from now to 15 minutes later, over the limit; the forecast is the last value plus that
             change, so the untrained model starts as "no change" and anything it gains over "no change" it has learned. A sample is learned only when its true value arrives,
             15 simulated minutes after the prediction, so the model never sees the answer early.
  chronos    Chronos-Bolt-small (Apache-2.0), zero-shot, released weights at the revision RQ1 used, the last 60 minutes as context
             with gaps left as NaN (as RQ1's predict_chronos does). One batched call per minute on a worker thread; if the previous
             call has not finished, that minute has no Chronos forecast (it is not invented).
  no_change  the road's last value.

Scoring (the chart shows both the running error and the error over the last 10 scored minutes): a (road, minute) pair is scored only when all three forecasters predicted it and its true value exists; the running
error is each forecaster's mean absolute error in km/h over those same pairs. Missing inputs (a minute in which no vehicle passed
a road) are carried forward as model inputs only; a missing true value is never scored.

Not RQ1's graph models: those are tied to METR-LA's 207 sensors and cannot run on these roads.
"""
from __future__ import annotations

import math
import threading

HORIZON = 15                       # minutes ahead
LAGS = (0, 1, 2, 4, 9, 14)         # minutes before "now" used by the online model
CONTEXT = 60                       # Chronos context, minutes
ROLLING = 10                       # minutes in the rolling error
NAMES = ("online", "chronos", "no_change")
CHRONOS_MODEL, CHRONOS_REVISION = "amazon/chronos-bolt-small", "772f3d25d38aec6d914c8949dab4462e2d46f5d8"   # RQ1's (third_party/SOURCES.md)


class Chronos:
    """The released pipeline, loaded once per process."""
    _pipe = None
    _lock = threading.Lock()

    @classmethod
    def available(cls) -> tuple[bool, str]:
        try:
            import chronos  # noqa: F401
            import torch  # noqa: F401
        except ImportError as exc:
            return False, f"Chronos is not installed on this server ({exc.name})"
        return True, ""

    @classmethod
    def predict(cls, series: list[list[float]], steps: int) -> list[list[float]]:
        import torch
        with cls._lock:
            if cls._pipe is None:
                from chronos import BaseChronosPipeline
                cls._pipe = BaseChronosPipeline.from_pretrained(CHRONOS_MODEL, revision=CHRONOS_REVISION, device_map="cpu", torch_dtype=torch.float32)
            ctx = [torch.tensor([math.nan if v is None else v for v in s], dtype=torch.float32) for s in series]
            q, _ = cls._pipe.predict_quantiles(ctx, prediction_length=steps, quantile_levels=[0.5])
            return q[:, :, 0].detach().cpu().numpy().tolist()


class Forecasters:
    def __init__(self, limits_kmh: dict[str, float], use_chronos: bool = True, sync: bool = False):
        from river import compose, linear_model, preprocessing
        self.roads = sorted(limits_kmh)
        self.limit = limits_kmh
        self.model = compose.Pipeline(preprocessing.StandardScaler(), linear_model.LinearRegression())
        self.series: dict[str, list[float | None]] = {r: [] for r in self.roads}     # observed value per minute (None: no vehicle)
        self.filled: dict[str, list[float | None]] = {r: [] for r in self.roads}     # carried forward, inputs only
        self.pending: dict[int, dict] = {}         # minute the truth arrives -> {"x": {road: features}, "pred": {name: {road: value}}}
        self.minute = -1
        self.abs_err = {n: 0.0 for n in NAMES}
        self.count = {n: 0 for n in NAMES}           # scored pairs per forecaster (Chronos may stop; the others go on)
        self.scored = 0
        self.learned = 0
        self.recent: list[tuple[int, dict]] = []      # (pairs, summed error per forecaster) for the last ROLLING scored minutes
        self.history: list[dict] = []              # one point per minute with scores: {"minute", online, chronos, no_change, "pairs"}
        self.latest: dict[str, dict[str, float]] = {n: {} for n in NAMES}
        ok, why = Chronos.available() if use_chronos else (False, "Chronos is switched off")
        self.chronos_ok, self.chronos_why = ok, why
        self._chronos_job: threading.Thread | None = None
        self._chronos_out: tuple[int, dict[str, float]] | None = None
        self.chronos_skipped = 0
        self.sync = sync                           # tests: wait for each Chronos call instead of skipping a busy minute

    # ------------------------------------------------------------------ inputs
    def _features(self, road: str, scale: float) -> dict | None:
        f = self.filled[road]
        if len(f) <= max(LAGS) or any(f[-1 - k] is None for k in LAGS):
            return None
        lim = self.limit[road]
        return {**{f"lag{k}": f[-1 - k] / lim for k in LAGS}, "scale": scale}

    def observe(self, speeds: dict[str, float | None], scale: float) -> dict:
        """One simulated minute's detector speeds. Scores what is due, learns, then predicts 15 minutes ahead."""
        self.minute += 1
        m = self.minute
        for r in self.roads:
            v = speeds.get(r)
            self.series[r].append(v)
            prev = self.filled[r][-1] if self.filled[r] else None
            self.filled[r].append(v if v is not None else prev)
        self._collect_chronos(wait=self.sync)
        self._score_and_learn(m)
        pred = {n: {} for n in NAMES}
        x = {}
        for r in self.roads:
            fx = self._features(r, scale)
            if fx is None:
                continue
            x[r] = fx
            pred["online"][r] = max(0.0, self.filled[r][-1] + self.model.predict_one(fx) * self.limit[r])
            pred["no_change"][r] = self.filled[r][-1]
        self._start_chronos(m)
        self.pending[m + HORIZON] = {"x": x, "pred": pred, "made": m}
        self.latest["online"], self.latest["no_change"] = pred["online"], pred["no_change"]
        return self.view()

    # ------------------------------------------------------------------ chronos
    def _start_chronos(self, m: int) -> None:
        if not self.chronos_ok:
            return
        if self._chronos_job and self._chronos_job.is_alive():
            self.chronos_skipped += 1
            return
        roads = [r for r in self.roads if sum(v is not None for v in self.series[r][-CONTEXT:]) >= 8]
        if not roads:
            return
        ctx = [self.series[r][-CONTEXT:] for r in roads]

        def work():
            try:
                out = Chronos.predict(ctx, HORIZON)
                self._chronos_out = (m, {r: max(0.0, o[-1]) for r, o in zip(roads, out)})
            except Exception as exc:                                   # noqa: BLE001 - shown, not hidden
                self.chronos_ok, self.chronos_why = False, f"Chronos failed: {type(exc).__name__}: {exc}"
        self._chronos_job = threading.Thread(target=work, daemon=True, name=f"chronos-{m}")
        self._chronos_job.start()

    def _collect_chronos(self, wait: bool = False) -> None:
        if wait and self._chronos_job:
            self._chronos_job.join()
        if self._chronos_out is None:
            return
        made, values = self._chronos_out
        self._chronos_out = None
        due = self.pending.get(made + HORIZON)
        if due is not None:
            due["pred"]["chronos"] = values
        self.latest["chronos"] = values

    # ------------------------------------------------------------------ scoring and learning
    def _score_and_learn(self, m: int) -> None:
        due = self.pending.pop(m, None)
        if due is None:
            return
        names = NAMES if self.chronos_ok else ("online", "no_change")      # without Chronos the other two are still compared
        err = {n: 0.0 for n in NAMES}
        pairs = 0
        for r, fx in due["x"].items():
            truth = self.series[r][-1]
            if truth is None:
                continue                                  # no true value: not learned, not scored
            self.model.learn_one(fx, truth / self.limit[r] - fx["lag0"])
            self.learned += 1
            preds = {n: due["pred"].get(n, {}).get(r) for n in names}
            if any(p is None for p in preds.values()):
                continue
            pairs += 1
            for n in names:
                err[n] += abs(preds[n] - truth)
        if pairs:
            self.scored += pairs
            for n in names:
                self.abs_err[n] += err[n]
                self.count[n] += pairs
            self.recent.append((pairs, {n: err[n] if n in names else None for n in NAMES}))
            self.recent = self.recent[-ROLLING:]
            self.history.append({"minute": m, "pairs": pairs, **{n: self._mae(n) if n in names else None for n in NAMES},
                                 **{f"{n}_10": self._rolling(n) for n in NAMES}})

    def _rolling(self, n: str) -> float | None:
        """Mean absolute error over the last ROLLING scored minutes: shows a forecaster improving, which the running mean hides."""
        got = [(p, e[n]) for p, e in self.recent if e[n] is not None]
        return round(sum(e for _, e in got) / sum(p for p, _ in got), 3) if got else None

    def _mae(self, n: str) -> float | None:
        return round(self.abs_err[n] / self.count[n], 3) if self.count[n] else None

    def view(self) -> dict:
        return {"minute": self.minute, "horizon_min": HORIZON, "scored_pairs": self.scored, "learned": self.learned,
                "running_mae_kmh": {n: self._mae(n) for n in NAMES} if self.scored else None,
                "history": self.history[-240:], "chronos": {"ok": self.chronos_ok, "why": self.chronos_why, "skipped_minutes": self.chronos_skipped}}

    def predictions(self, name: str) -> dict[str, float]:
        return {r: round(v, 1) for r, v in self.latest.get(name, {}).items()}

