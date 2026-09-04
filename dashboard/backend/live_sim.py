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
            "levels": "observed", "step_delay_ms": 100, "v2x": "ideal", "horizon_min": 15,
            "continuous": False}
LIVE_REFRESH_S = 300          # the provider's own cadence; the recorder samples at the same rate
DEMAND_PERIOD_S = 3600        # the calibrated demand file covers one hour; it is replayed hourly


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
        cfg["continuous"] = bool(cfg["continuous"]) or int(cfg["duration_s"]) == 0
        if cfg["continuous"]:
            cfg["duration_s"] = 10 ** 8        # runs until stopped; demand is replayed every hour
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
        log = (out / "run.log").open("a")

        def note(msg: str) -> None:
            log.write(f"{time.strftime('%H:%M:%S')} +{time.time() - t_wall:6.1f}s {msg}\n"); log.flush()
        note(f"thread {threading.current_thread().name} cfg={cfg}")

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
            last, conn = None, None
            for _ in range(50):                                  # SUMO needs a moment to listen
                try:
                    # a Connection OBJECT, not the module: the module-level traci keeps one
                    # "current" connection per process, and a chain run in another thread
                    # would otherwise be stepping our SUMO (or we theirs)
                    conn = traci.connect(port=port, numRetries=1, label=f"live-{run_id}")
                    break
                except Exception as exc:                          # noqa: BLE001
                    last = exc
                    if proc.poll() is not None:
                        raise RuntimeError(f"SUMO exited early: {(proc.stderr.read() or '')[-800:]}")
                    time.sleep(0.2)
            if conn is None:
                raise RuntimeError(f"could not connect to SUMO on port {port}: {last}")
            applied = 0
            for eid, m in slow.items():
                try:
                    for i in range(conn.edge.getLaneNumber(eid)):
                        lid = f"{eid}_{i}"
                        conn.lane.setMaxSpeed(lid, max(conn.lane.getMaxSpeed(lid) / m, 0.5))
                    applied += 1
                except traci.TraCIException:
                    pass
            self._set(status="running", message="", edges_slowed=applied)
            note(f"SUMO pid {proc.pid} port {port}; loop starts")

            import hashlib
            sub = [tc.VAR_POSITION, tc.VAR_SPEED, tc.VAR_WAITING_TIME]
            arrived = teleports = reroutes = 0
            t = 0
            # --- continuous mode: replay the calibrated hour of demand every hour, and follow the
            # live road. SUMO loads (and scales) hour 0 itself; later hours are re-inserted through
            # TraCI with the same deterministic per-vehicle selection at the same scale.
            replay, route_ids, next_hour = [], {}, 1
            base_speed: dict[str, float] = {}
            live_applied_utc, live_mult = None, {}
            if cfg["continuous"]:
                for vid, dep, edges in lc.read_routes(routes):
                    if (int(hashlib.md5(vid.encode()).hexdigest()[:8], 16) % 10_000) < cfg["scale"] * 10_000:
                        replay.append((vid, float(dep), edges))
                replay.sort(key=lambda r: r[1])
                for eid in {e for edges in cmap.values() for e in (edges.get("edges") or [])}:
                    try:
                        for i in range(conn.edge.getLaneNumber(eid)):
                            base_speed[f"{eid}_{i}"] = conn.lane.getMaxSpeed(f"{eid}_{i}")
                    except traci.TraCIException:
                        pass
                # the slowdowns applied above were the as-of state; from here the live road rules
                for lid, v0 in base_speed.items():
                    conn.lane.setMaxSpeed(lid, v0)
                last_live = 0.0
                replay_i = 0

            def apply_live() -> None:
                """Corridor speeds from the live provider, on the corridor edges, right now."""
                nonlocal live_applied_utc, live_mult
                from live import service
                snap = service.corridors()
                mult = {}
                for c in snap.get("corridors", []):
                    d, st = c.get("duration_s"), c.get("static_duration_s")
                    if c.get("is_live") and d and st and st > 0:
                        mult[c["id"]] = max(1.0, float(d) / float(st))
                if not mult:
                    return
                edge_m: dict[str, float] = {}
                for cid, m in mult.items():
                    for eid in (cmap.get(cid) or {}).get("edges") or []:
                        edge_m[eid] = max(edge_m.get(eid, 1.0), m)
                for lid, v0 in base_speed.items():
                    m = edge_m.get(lid.rsplit("_", 1)[0], 1.0)
                    try:
                        conn.lane.setMaxSpeed(lid, max(v0 / m, 0.5))
                    except traci.TraCIException:
                        pass
                live_mult = {k: round(v, 3) for k, v in mult.items()}
                live_applied_utc = datetime.now(timezone.utc).isoformat()
                note(f"live state applied: {live_mult}")
            while not self._stop.is_set() and t < cfg["duration_s"] and conn.simulation.getMinExpectedNumber() > 0:
                if self._pause.is_set():
                    time.sleep(0.1); continue
                conn.simulationStep()
                t = int(conn.simulation.getTime())
                if cfg["continuous"]:
                    if time.time() - last_live >= LIVE_REFRESH_S:
                        last_live = time.time()
                        try:
                            apply_live()
                        except Exception as exc:              # noqa: BLE001 - the twin keeps running
                            note(f"live refresh failed: {type(exc).__name__}: {exc}")
                    # hourly demand replay: insert every selected vehicle whose (shifted) departure
                    # has come, cycling the hour's list; routes are registered once each
                    while True:
                        vid, dep, edges = replay[replay_i]
                        when = dep + next_hour * DEMAND_PERIOD_S
                        if when > t:
                            break
                        rid = route_ids.get(edges)
                        if rid is None:
                            rid = f"r{len(route_ids)}"
                            try:
                                conn.route.add(rid, edges.split()); route_ids[edges] = rid
                            except traci.TraCIException:
                                route_ids[edges] = rid = None
                        if rid:
                            try:
                                conn.vehicle.add(f"{vid}_h{next_hour}", rid)
                            except traci.TraCIException:
                                pass
                        replay_i += 1
                        if replay_i >= len(replay):
                            replay_i, next_hour = 0, next_hour + 1
                for vid in conn.simulation.getDepartedIDList():
                    conn.vehicle.subscribe(vid, sub)
                arrived += conn.simulation.getArrivedNumber()
                teleports += conn.simulation.getStartingTeleportNumber()
                if cfg["arm"] == "reactive":
                    for vid in conn.vehicle.getIDList():
                        if not pr.equipped(vid, cfg["compliance"]):
                            continue
                        if not ic.delivered(vid, deliver_p, cfg["v2x"], cfg["seed"]):
                            continue
                        if (int(hashlib.md5(vid.encode()).hexdigest()[8:12], 16) + t) % 60 == 0:
                            try:
                                conn.vehicle.rerouteTraveltime(vid, currentTravelTimes=True)
                                reroutes += 1
                            except traci.TraCIException:
                                pass
                res = conn.vehicle.getAllSubscriptionResults()
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
                    "progress": 0.0 if cfg["continuous"] else round(t / cfg["duration_s"], 3),
                    "hour": t // DEMAND_PERIOD_S + 1 if cfg["continuous"] else None,
                    "live_applied_utc": live_applied_utc, "live_multipliers": live_mult})
                if cfg["step_delay_ms"]:
                    time.sleep(cfg["step_delay_ms"] / 1000)
            note(f"loop ended t={t} stop={self._stop.is_set()} expected={conn.simulation.getMinExpectedNumber()}")
            conn.close()
            try:
                proc.wait(timeout=180)              # SUMO writes tripinfo/statistic on shutdown
            except subprocess.TimeoutExpired:
                proc.kill(); proc.wait()
            metrics = pr.parse_metrics(out, horizon=t if cfg["continuous"] else cfg["duration_s"])
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
            note(f"scored: arrived={metrics['arrived']} veh-h={metrics['total_vehicle_hours']:.2f}")
            self._set(status="stopped" if self._stop.is_set() else "done", result=rec, vehicles=[])
        except Exception as exc:                        # noqa: BLE001 - shown on the page, never lost
            import traceback
            note("EXCEPTION " + traceback.format_exc())
            try:
                conn.close()                            # noqa: F821 - only bound after connect
            except Exception:                           # noqa: BLE001
                pass
            try:
                proc.kill()                             # noqa: F821 - only bound after Popen
            except Exception:                           # noqa: BLE001
                pass
            self._set(status="failed", message=f"{type(exc).__name__}: {exc}", vehicles=[])


live_sim = LiveSim()
