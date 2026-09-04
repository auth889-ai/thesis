"""The digital twin, live: SUMO stepping in a thread, every vehicle on the map, every second.

    sim = LiveSim()
    sim.start({"scale": 0.25, "duration_s": 900, "seed": 11, "arm": "reactive"})
    sim.state()          # KPIs + vehicle positions for the map, refreshed every step
    sim.pause() / sim.resume() / sim.stop()

This is the SAME twin the experiments run — the calibrated Dhaka R1 network, the calibrated
demand, the observed congestion applied to the corridor edges, and the three routing arms — but
stepped under a viewer's eye instead of to completion. Positions come from TraCI subscriptions
(one per vehicle, read once per step) and are converted with sumolib, so what the map shows is
what SUMO computed; nothing is animated for effect. Finished runs are scored with the chain's own
`parse_metrics`, so a live run and a batch run report the same numbers.
"""
from __future__ import annotations

import json
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import config

sys.path.insert(0, str(config.REPO))

OUT_ROOT = config.REPO / "results/live/sim"
HISTORY = config.REPO / "results/live/sim_history.json"
MAX_VEHICLES_SHOWN = 2000
ARMS = ("baseline", "reactive", "prediction_aware")
DEFAULTS = {"scale": None, "duration_s": 900, "seed": 11, "compliance": 0.3, "arm": "reactive",
            "levels": "observed", "step_delay_ms": 100, "v2x": "ideal", "horizon_min": 15}


class LiveSim:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._pause = threading.Event()
        self._net = None
        self._snapshot: dict = {"status": "idle"}
        self._history: list[dict] = self._load_history()

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _load_history() -> list[dict]:
        try:
            return json.loads(HISTORY.read_text()) if HISTORY.exists() else []
        except json.JSONDecodeError:
            return []

    def _net_obj(self):
        if self._net is None:
            import sumolib
            from pipeline.core.network_file import ensure_net
            from pipeline.routing import predictive_routing as pr
            self._net = sumolib.net.readNet(str(ensure_net(Path(pr.DEFAULT_NET))))
        return self._net

    def _set(self, **kw) -> None:
        with self._lock:
            self._snapshot.update(kw)

    # ------------------------------------------------------------------ lifecycle
    def start(self, params: dict | None = None) -> dict:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return {"started": False, "reason": "a live simulation is already running",
                        "run_id": self._snapshot.get("run_id")}
        from pipeline.routing import integrated_chain as ic
        cfg = {**DEFAULTS, **{k: v for k, v in (params or {}).items() if v is not None}}
        if cfg["arm"] not in ARMS:
            return {"started": False, "reason": f"arm must be one of {ARMS}"}
        if cfg["scale"] is None:
            sc = config.REPO / "results/routing/SCALE_CHOICE.json"
            cfg["scale"] = json.loads(sc.read_text()).get("scale", 0.25) if sc.exists() else 0.25
        cfg["scale"] = float(cfg["scale"]); cfg["duration_s"] = int(cfg["duration_s"])
        cfg["seed"] = int(cfg["seed"]); cfg["compliance"] = float(cfg["compliance"])
        run_id = datetime.now(timezone.utc).strftime("live_%Y%m%dT%H%M%SZ_") + uuid.uuid4().hex[:6]
        self._stop.clear(); self._pause.clear()
        with self._lock:
            self._snapshot = {"status": "starting", "run_id": run_id, "params": cfg,
                              "started_utc": datetime.now(timezone.utc).isoformat(),
                              "kpis": {}, "vehicles": [], "sim_time_s": 0, "message": "preparing"}
        self._thread = threading.Thread(target=self._run, args=(run_id, cfg), daemon=True,
                                        name=f"live-sim-{run_id}")
        self._thread.start()
        return {"started": True, "run_id": run_id, "params": cfg}

    def pause(self) -> dict:
        self._pause.set(); self._set(status="paused"); return self.state(with_vehicles=False)

    def resume(self) -> dict:
        self._pause.clear(); self._set(status="running"); return self.state(with_vehicles=False)

    def stop(self) -> dict:
        self._stop.set(); self._pause.clear()
        if self._thread:
            self._thread.join(timeout=30)
        return self.state(with_vehicles=False)

    def state(self, with_vehicles: bool = True) -> dict:
        with self._lock:
            s = dict(self._snapshot)
        if not with_vehicles:
            s.pop("vehicles", None)
        return s

    def history(self) -> list[dict]:
        with self._lock:
            return list(self._history)

    # ------------------------------------------------------------------ the run
    def _run(self, run_id: str, cfg: dict) -> None:
        import argparse
        import traci
        import traci.constants as tc
        from pipeline.routing import integrated_chain as ic, live_chain as lc
        from pipeline.routing import predictive_routing as pr
        from pipeline.routing.forecast_to_costs import (build_table, fetch_forecast,
                                                        recorded_city_data, write_weights)
        out = OUT_ROOT / run_id
        out.mkdir(parents=True, exist_ok=True)
        t_wall = time.time()
        try:
            net = self._net_obj()
            a = argparse.Namespace(net=str(pr.DEFAULT_NET), routes=str(pr.DEFAULT_ROUTES),
                                   scale=cfg["scale"], horizon=cfg["duration_s"],
                                   compliance=cfg["compliance"], v2x=cfg["v2x"],
                                   horizon_min=cfg["horizon_min"])
            # 1. the observed congestion, made real on the corridor edges in every arm
            self._set(message="reading the observed congestion state")
            levels = {}
            if cfg["levels"] == "observed":
                _, observed = recorded_city_data("dhaka", "peak")
                levels = {k: float(v) for k, v in observed["levels"].items()}
            elif cfg["levels"]:
                levels = {k: float(v) for k, v in (kv.split("=") for kv in str(cfg["levels"]).split(","))}
            cmap = json.loads((config.REPO / "data/forecasting/live_dhaka/corridor_edges.json").read_text())
            slow = lc.affected_edges(levels, cmap)
            deliver_p, v2x = ic.delivery_fraction(cfg["v2x"])
            # 2. the forecast, only for the arm that routes on it
            routes, changed, advised, forecast = Path(a.routes), 0, 0, None
            if cfg["arm"] == "prediction_aware":
                self._set(message="running the forecast and pricing the edges")
                res = fetch_forecast("dhaka", cfg["horizon_min"], None, source="recorded", as_of="peak")
                table = build_table(res, cfg["horizon_min"], Path(a.net))
                weights = write_weights(table, out / "forecast_weights.xml", 0.0, float(cfg["duration_s"]))
                forecast = table["forecast"]
                routes, changed, advised = ic.predeparture_routes(a, cfg["seed"], weights, out, deliver_p)
            ns = argparse.Namespace(net=a.net, routes=str(routes), seed=cfg["seed"], scale=cfg["scale"],
                                    horizon=cfg["duration_s"], edgedata_period=300,
                                    time_to_teleport=300, sumo_binary="sumo")
            self._set(message="starting SUMO", edges_congested=len(slow), delivery_fraction=deliver_p,
                      forecast=forecast, advised=advised, routes_changed=changed)
            import subprocess
            port = pr.free_port()
            proc = subprocess.Popen(pr.base_cmd(ns, out) + ["--remote-port", str(port)],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            last = None
            for _ in range(50):                                  # SUMO needs a moment to listen
                try:
                    traci.init(port, label=f"live-{run_id}", numRetries=1)
                    break
                except Exception as exc:                          # noqa: BLE001
                    last = exc
                    if proc.poll() is not None:
                        raise RuntimeError(f"SUMO exited early: {(proc.stderr.read() or '')[-800:]}")
                    time.sleep(0.2)
            else:
                raise RuntimeError(f"could not connect to SUMO on port {port}: {last}")
            applied = 0
            for eid, m in slow.items():
                try:
                    for i in range(traci.edge.getLaneNumber(eid)):
                        lid = f"{eid}_{i}"
                        traci.lane.setMaxSpeed(lid, max(traci.lane.getMaxSpeed(lid) / m, 0.5))
                    applied += 1
                except traci.TraCIException:
                    pass
            self._set(status="running", message="", edges_slowed=applied)

            import hashlib
            sub = [tc.VAR_POSITION, tc.VAR_SPEED, tc.VAR_WAITING_TIME]
            arrived = teleports = reroutes = 0
            t = 0
            while not self._stop.is_set() and t < cfg["duration_s"] and traci.simulation.getMinExpectedNumber() > 0:
                if self._pause.is_set():
                    time.sleep(0.1); continue
                traci.simulationStep()
                t = int(traci.simulation.getTime())
                for vid in traci.simulation.getDepartedIDList():
                    traci.vehicle.subscribe(vid, sub)
                arrived += traci.simulation.getArrivedNumber()
                teleports += traci.simulation.getStartingTeleportNumber()
                if cfg["arm"] == "reactive":
                    for vid in traci.vehicle.getIDList():
                        if not pr.equipped(vid, cfg["compliance"]):
                            continue
                        if not ic.delivered(vid, deliver_p, cfg["v2x"], cfg["seed"]):
                            continue
                        if (int(hashlib.md5(vid.encode()).hexdigest()[8:12], 16) + t) % 60 == 0:
                            try:
                                traci.vehicle.rerouteTraveltime(vid, currentTravelTimes=True)
                                reroutes += 1
                            except traci.TraCIException:
                                pass
                res = traci.vehicle.getAllSubscriptionResults()
                vehicles, speeds, waits, halting = [], [], [], 0
                for vid, d in res.items():
                    x, y = d[tc.VAR_POSITION]
                    v = float(d[tc.VAR_SPEED]); w = float(d[tc.VAR_WAITING_TIME])
                    if v < 0 or x < -1e6:                         # arrived this step: INVALID values
                        continue
                    speeds.append(v); waits.append(w); halting += v < 0.1
                    if len(vehicles) < MAX_VEHICLES_SHOWN:
                        lon, lat = net.convertXY2LonLat(x, y)
                        vehicles.append([round(lon, 5), round(lat, 5), round(v * 3.6, 1),
                                         int(pr.equipped(vid, cfg["compliance"]))])
                n = len(res)
                self._set(sim_time_s=t, vehicles=vehicles, kpis={
                    "vehicles_on_road": n, "shown": len(vehicles),
                    "mean_speed_kmh": round(sum(speeds) / n * 3.6, 2) if n else 0.0,
                    "mean_waiting_s": round(sum(waits) / n, 2) if n else 0.0,
                    "halting": halting, "arrived": arrived, "teleports": teleports,
                    "reroutes": reroutes, "sim_time_s": t, "wall_s": round(time.time() - t_wall, 1),
                    "progress": round(t / cfg["duration_s"], 3)})
                if cfg["step_delay_ms"]:
                    time.sleep(cfg["step_delay_ms"] / 1000)
            traci.close()
            try:
                proc.wait(timeout=180)              # SUMO writes tripinfo/statistic on shutdown
            except subprocess.TimeoutExpired:
                proc.kill(); proc.wait()
            metrics = pr.parse_metrics(out, horizon=cfg["duration_s"])
            rec = {"run_id": run_id, "params": cfg, "stopped_early": bool(self._stop.is_set()),
                   "sim_time_s": t, "reroutes": reroutes, "advised": advised, "routes_changed": changed,
                   "edges_slowed": applied, "delivery_fraction": deliver_p,
                   "forecast": forecast, "metrics": metrics, "out_dir": str(out.relative_to(config.REPO)),
                   "finished_utc": datetime.now(timezone.utc).isoformat(),
                   "wall_s": round(time.time() - t_wall, 1)}
            (out / "result.json").write_text(json.dumps(rec, indent=1, default=str))
            with self._lock:
                self._history.insert(0, rec)
                self._history = self._history[:50]
                HISTORY.parent.mkdir(parents=True, exist_ok=True)
                HISTORY.write_text(json.dumps(self._history, indent=1, default=str))
            self._set(status="stopped" if self._stop.is_set() else "done", result=rec, vehicles=[])
        except Exception as exc:                        # noqa: BLE001 - shown on the page, never lost
            try:
                import traci
                traci.close()
            except Exception:                           # noqa: BLE001
                pass
            try:
                proc.kill()                             # noqa: F821 - only bound after Popen
            except Exception:                           # noqa: BLE001
                pass
            self._set(status="failed", message=f"{type(exc).__name__}: {exc}", vehicles=[])


live_sim = LiveSim()
