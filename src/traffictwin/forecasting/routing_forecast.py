"""Adapt recorded observation windows and fresh inference to routing edge costs."""
import json
import math
from pathlib import Path
from traffictwin.paths import REPO
from traffictwin.optimization import edge_costs as ec
from traffictwin.networking.observed_costs import fuse_observed

MPH = 0.44704

def moment_for(rule: str, seed: int, T: int, test_lo: int) -> int:
    """The dataset moment the run starts from — a SCENARIO choice declared in the protocol, never read
    from outcomes. `rule`: the v1 hash rule (a random held-out moment, mostly off-peak); `peak`: the
    weekday 17:30 (METR-LA clock, 2012-03-01 00:00 = index 0) of the seed-th weekday inside the
    held-out split — the evening rush hour that the detectors actually record as congested."""
    if rule == "rule":
        return int(test_lo + 12 + (seed * 97) % ((T - test_lo) - 24))
    from datetime import datetime, timedelta
    t0 = datetime(2012, 3, 1)
    hour, minute = {"peak": (17, 30), "prepeak": (16, 15)}[rule]      # prepeak: the evening build-up is still ahead — a FORECASTABLE deterioration, no incident
    days = []
    for i in range(test_lo + 12, T - 24):
        d = t0 + timedelta(minutes=5 * i)
        if d.weekday() < 5 and d.hour == hour and d.minute == minute:
            days.append(i)
    if not days:
        raise SystemExit("no weekday 17:30 inside the held-out split")
    return days[seed % len(days)]


class Forecaster:
    """Compatibility adapter around the canonical ForecastService.

    The routing loop keeps its established edge/cap APIs, while every fresh DL forward pass and
    its provenance are now supplied by ``traffictwin.forecasting.ForecastService``.
    """

    def __init__(self, P: dict, seed: int):
        from pipeline.forecasting import train_eval as te
        from traffictwin.forecasting import ForecastService
        self.service = ForecastService.metr_la_gwnet()
        self.raw, self.vals = self.service.raw, self.service.values
        T = self.raw.shape[0]; lo = te.splits(T)["test"][0]
        self.as_of0 = moment_for(P["moment"], seed, T, lo)
        self.strict_fresh = P.get("strict_fresh", False)
        if "observation_as_of_index" in P:
            self.as_of0 = P["observation_as_of_index"]
            if type(self.as_of0) is not int or not 12 <= self.as_of0 <= T - 12 - math.ceil(P["simulation_duration_s"] / 300):
                raise ValueError("Observation window cannot cover the requested execution without clamping.")
        self.card = self.service.card
        mapping = json.loads((REPO / P["mapping_file"]).read_text())
        self.good = [r for r in mapping["records"] if r["quality"] == "GOOD"]
        self.cmap = {f"S{r['node_index']}": {"edges": [r["edge"]], "sensor_id": r["sensor_id"], "quality": "GOOD"} for r in self.good}
        self.free = {f"S{r['node_index']}": float(r["speed_limit_mps"]) for r in self.good}
        self.contract = self.service.spec.public()

    def moment(self, sim_t: float) -> int:
        return min(self.raw.shape[0] - 12, self.as_of0 + int(sim_t // 300))

    def predict(self, sim_t: float) -> dict:
        as_of = self.moment(sim_t)
        out = self.service.predict(as_of, include_tensor_hash=True) if self.strict_fresh else self.service.predict(as_of)
        if self.strict_fresh and out.get("nonfinite_values_replaced"):
            raise RuntimeError("Fresh checkpoint inference produced non-finite values; no fallback permitted.")
        return {"as_of": out["as_of"], "pred": out["prediction"], "now": out["now"],
                "inference_seconds": out["inference_runtime_s"], "raw_prediction_hash": out["raw_prediction_hash"],
                "input_window_hash": out["input_window_hash"], "input_tensor_sha256": out.get("input_tensor_sha256"), "forecast_contract": out["contract"]}

    def table(self, F: dict, horizon_min: int, cfg: dict, net_path: Path, observed: dict | None = None) -> dict:
        k = max(0, min(11, horizon_min // 5 - 1))
        values = {node: float(F["pred"][k, int(node[1:])]) * MPH for node in self.cmap}
        t = ec.build(values, "speed_mps", self.cmap, net_path, horizon_min, cfg, None, "GWNet-207", None, corridor_free_speed=self.free)
        if observed:
            t = fuse_observed(t, observed, net_path, cfg)
        return t

    def tables(self, F: dict, cfg: dict, net_path: Path, horizons=(0, 15, 30, 60)) -> dict[int, dict]:
        """One production edge-cost table per horizon; horizon 0 = the detectors' current readings."""
        out = {}
        for h in horizons:
            src = F["now"] if h == 0 else F["pred"][max(0, min(11, h // 5 - 1))]
            values = {node: float(src[int(node[1:])]) * MPH for node in self.cmap}
            out[h] = ec.build(values, "speed_mps", self.cmap, net_path, h or 15, cfg, None, "GWNet-207" if h else "now", None, corridor_free_speed=self.free)
        return out

    def caps(self, duration_s: int) -> dict:
        """edge -> [(t_from_s, cap_mps)]: the measured detector speeds after the moment, every 300 s."""
        sched = {}
        for r in self.good:
            j = r["node_index"]; limit = float(r["speed_limit_mps"]); steps = []
            for k in range(int(math.ceil(duration_s / 300))):
                v = self.vals[min(self.as_of0 + k, self.vals.shape[0] - 1), j]
                steps.append((k * 300, round(max(1.0, min(limit, v * MPH)), 3) if v > 0 else limit))
            sched[r["edge"]] = steps
        return sched

