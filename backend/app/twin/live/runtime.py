"""The digital twin, live: SUMO stepping in a thread, every vehicle on the map, every second.

    sim = LiveSim()
    sim.start({"scale": 0.25, "duration_s": 900, "seed": 11, "arm": "reactive"})
    sim.state()          # KPIs + vehicle positions for the map, refreshed every step
    sim.pause() / sim.resume() / sim.stop()

This is the SAME twin the experiments run — the frozen Dhaka R1 OSM network, its configured
demand, the observed congestion applied to the corridor edges, and the three routing arms — but
stepped under a viewer's eye instead of to completion. Finished runs are scored with the chain's
own `parse_metrics`, so a live run and a batch run report the same numbers.

The parts: settings (constants), networks (what can run, provenance facts), launch (prepare the
arm, start SUMO, connect), probe (the analysed trip as one vehicle), demand (continuous replay and
the live road), loop (the stepping loop). This module holds the lifecycle and the run record.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app import evidence_paths as config

from .demand import ContinuousDemand
from .launch import apply_slowdowns, connect, launch_record, launch_sumo, prepare
from .loop import StepLoop
from .networks import dhaka_validation, file_hash, networks, resolve_network, scenario_label, sumo_version  # noqa: F401 - import surface
from .probe import add_probe, probe_tripinfo
from .settings import ARMS, COLOUR, DEFAULTS, DHAKA_CENTER, HISTORY, OUT_ROOT, TELEPORT_REASON, VISUAL_LEGEND  # noqa: F401 - import surface


class LiveSim:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._pause = threading.Event()
        self._net = None
        self._snapshot: dict = {"status": "idle"}
        self._history: list[dict] = self._load_history()
        self.owner: str | None = None          # a job (e.g. a comparison) that holds the twin

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _load_history() -> list[dict]:
        try:
            return json.loads(HISTORY.read_text()) if HISTORY.exists() else []
        except json.JSONDecodeError:
            return []

    def _net_obj(self, path: Path):
        if not isinstance(self._net, dict):
            self._net = {}
        key = str(path)
        if key not in self._net:
            import sumolib
            from app.twin.network_file import ensure_net
            self._net[key] = sumolib.net.readNet(str(ensure_net(Path(path))))
        return self._net[key]

    def _set(self, **kw) -> None:
        with self._lock:
            self._snapshot.update(kw)

    # ------------------------------------------------------------------ lifecycle
    def start(self, params: dict | None = None, owner: str | None = None) -> dict:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return {"started": False, "reason": "a live simulation is already running",
                        "run_id": self._snapshot.get("run_id")}
            if self.owner and owner != self.owner:
                return {"started": False, "reason": f"the twin is held by {self.owner} (a comparison "
                                                    f"in progress); wait for it to finish"}
        cfg = {**DEFAULTS, **{k: v for k, v in (params or {}).items() if v is not None}}
        if cfg["arm"] not in ARMS:
            return {"started": False, "reason": f"arm must be one of {ARMS}"}
        try:
            netinfo = resolve_network(cfg["network"])
        except ValueError as exc:
            return {"started": False, "reason": str(exc)}
        cfg["network"] = netinfo["id"]; cfg["demand_reality"] = netinfo["demand"]
        cfg["center"] = list(netinfo["center"])
        if cfg["scale"] is None:
            sc = config.REPO / "results/routing/SCALE_CHOICE.json"
            cfg["scale"] = json.loads(sc.read_text()).get("scale", 0.25) if sc.exists() else 0.25
        cfg["scale"] = float(cfg["scale"]); cfg["duration_s"] = int(cfg["duration_s"])
        cfg["seed"] = int(cfg["seed"]); cfg["compliance"] = float(cfg["compliance"])
        cfg["continuous"] = bool(cfg["continuous"]) or int(cfg["duration_s"]) == 0
        if cfg["continuous"]:
            cfg["duration_s"] = 10 ** 8        # runs until stopped; demand is replayed every hour
        if cfg["arm"] == "prediction_aware" and not netinfo["live_coupled"] and not cfg.get("routes_file"):
            return {"started": False, "reason": "prediction_aware on a generated city needs the optimizer's route file (the twin test's oracle debug arm provides it)"}
        run_id = datetime.now(timezone.utc).strftime("live_%Y%m%dT%H%M%SZ_") + uuid.uuid4().hex[:6]
        self._stop.clear(); self._pause.clear(); self._tracking = None
        with self._lock:
            self._snapshot = {"status": "starting", "run_id": run_id, "params": cfg,
                              "started_utc": datetime.now(timezone.utc).isoformat(),
                              "kpis": {}, "vehicles": [], "sim_time_s": 0, "message": "preparing",
                              "scenario": scenario_label(netinfo), "legend": VISUAL_LEGEND, "teleport_events": [], "probe": {},
                              "launch": {"simulation_run_id": cfg.get("simulation_run_id"), "analysis_run_id": cfg.get("analysis_run_id"),
                                         "routing_run_id": cfg.get("routing_run_id"), "arm": cfg["arm"], "seed": cfg["seed"], "gui": bool(cfg.get("gui")),
                                         "network": netinfo["id"], "launch_utc": datetime.now(timezone.utc).isoformat()}}
        self._thread = threading.Thread(target=self._run, args=(run_id, cfg), daemon=True, name=f"live-sim-{run_id}")
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

    def screenshot(self, path: str | None = None) -> dict:
        """Ask sumo-gui to write its current view to a PNG (TraCI gui.screenshot) — the real window,
        not a browser drawing."""
        conn = getattr(self, "_conn", None)
        st = self.state(with_vehicles=False)
        if not conn or not st.get("gui") or st.get("status") not in ("running", "paused"):
            return {"ok": False, "reason": "no sumo-gui run is active"}
        out = Path(path) if path else (config.REPO / "results/live/sim/screenshots" / f"{st.get('run_id', 'run')}_{int(st.get('sim_time_s', 0))}s.png")
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            if path is None and st.get("kpis", {}).get("vehicles_on_road"):   # frame the busiest spot before shooting
                ids = conn.vehicle.getIDList()
                if ids and not getattr(self, "_tracking", False):
                    v = max(ids, key=lambda i: conn.vehicle.getWaitingTime(i))
                    x, y = conn.vehicle.getPosition(v); conn.gui.setOffset("View #0", x, y); conn.gui.setZoom("View #0", 9000)
            conn.gui.screenshot("View #0", str(out))
        except Exception as exc:                            # noqa: BLE001
            return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}
        return {"ok": True, "path": str(out), "sim_time_s": st.get("sim_time_s"), "run_id": st.get("run_id"), "pid": st.get("pid")}

    def follow(self, vehicle_id: str | None = None) -> dict:
        """Track one vehicle in the sumo-gui view (TraCI gui.trackVehicle); the busiest one when none is named."""
        conn = getattr(self, "_conn", None)
        st = self.state(with_vehicles=False)
        if not conn or not st.get("gui") or st.get("status") not in ("running", "paused"):
            return {"ok": False, "reason": "no sumo-gui run is active"}
        try:
            ids = conn.vehicle.getIDList()
            vid = vehicle_id or (max(ids, key=lambda v: conn.vehicle.getWaitingTime(v)) if ids else None)
            if not vid:
                return {"ok": False, "reason": "no vehicle on the road yet"}
            conn.gui.trackVehicle("View #0", vid); conn.gui.setZoom("View #0", 10000); self._tracking = vid
        except Exception as exc:                            # noqa: BLE001
            return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}
        return {"ok": True, "vehicle": vid}

    def state(self, with_vehicles: bool = True) -> dict:
        with self._lock:
            s = dict(self._snapshot)
            s["owner"] = self.owner
        if not with_vehicles:
            s.pop("vehicles", None)
        return s

    def history(self) -> list[dict]:
        with self._lock:
            return list(self._history)

    # ------------------------------------------------------------------ the run
    def _run(self, run_id: str, cfg: dict) -> None:
        import subprocess
        from app.twin import runtime as pr
        out = OUT_ROOT / run_id
        out.mkdir(parents=True, exist_ok=True)
        t_wall = time.time()
        log = (out / "run.log").open("a")

        def note(msg: str) -> None:
            log.write(f"{time.strftime('%H:%M:%S')} +{time.time() - t_wall:6.1f}s {msg}\n"); log.flush()
        note(f"thread {threading.current_thread().name} cfg={cfg}")
        proc = conn = None
        try:
            netinfo = resolve_network(cfg["network"])
            net = self._net_obj(netinfo["net"])
            prep = prepare(cfg, netinfo, out, lambda m: self._set(message=m))
            self._set(message="starting SUMO", edges_congested=len(prep["slow"]), delivery_fraction=prep["deliver_p"],
                      forecast=prep["forecast"], advised=prep["advised"], routes_changed=prep["changed"])
            proc, port, ns = launch_sumo(cfg, netinfo, prep, out)
            self._proc, self._conn = proc, None
            n_edges = netinfo.get("edges") or next((n.get("edges") for n in networks() if n["id"] == netinfo["id"]), None)
            launch = launch_record(cfg, netinfo, prep, ns, proc, port, self.state(with_vehicles=False).get("launch", {}))
            self._set(pid=proc.pid, port=port, gui=bool(cfg.get("gui")), sumo_binary=ns.sumo_binary, network_edges=n_edges, launch=launch)
            (out / "launch.json").write_text(json.dumps(launch, indent=1, default=str))
            conn = self._conn = connect(port, proc, run_id)
            probe = cfg.get("probe") or None                # the analysed trip: {id, from_edge, to_edge, depart_s, route_edges?}
            probe_state = add_probe(conn, probe) if probe else {}
            if probe:
                self._set(probe=probe_state)
            applied = apply_slowdowns(conn, prep["slow"])
            self._set(status="running", message="", edges_slowed=applied)
            note(f"SUMO pid {proc.pid} port {port}; loop starts")
            demand = ContinuousDemand(conn, cfg, prep["routes"], prep["cmap"], note) if cfg["continuous"] else None
            loop = StepLoop(self, conn, net, cfg, prep, probe, probe_state, demand, netinfo["live_coupled"], t_wall, note)
            t = loop.run()
            note(f"loop ended t={t} stop={self._stop.is_set()} expected={conn.simulation.getMinExpectedNumber()}")
            conn.close()
            try:
                proc.wait(timeout=180)              # SUMO writes tripinfo/statistic on shutdown
            except subprocess.TimeoutExpired:
                proc.kill(); proc.wait()
            metrics = pr.parse_metrics(out, horizon=t if cfg["continuous"] else cfg["duration_s"])
            if probe:
                probe_tripinfo(out, probe, probe_state)
                self._set(probe=probe_state)
            rec = {"run_id": run_id, "params": {k: v for k, v in cfg.items() if k != "advised_ids"}, "stopped_early": bool(self._stop.is_set()),
                   "launch": self.state(with_vehicles=False).get("launch"), "teleport_events": loop.teleport_events, "probe": probe_state or None,
                   "scenario": scenario_label(netinfo),
                   "sim_time_s": t, "reroutes": loop.reroutes, "advised": prep["advised"], "routes_changed": prep["changed"],
                   "edges_slowed": applied, "delivery_fraction": prep["deliver_p"],
                   "forecast": prep["forecast"], "metrics": metrics, "out_dir": str(out.relative_to(config.REPO)),
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
            for closer in ((lambda: conn.close()) if conn else None, (lambda: proc.kill()) if proc else None):
                try:
                    if closer:
                        closer()
                except Exception:                       # noqa: BLE001
                    pass
            self._set(status="failed", message=f"{type(exc).__name__}: {exc}", vehicles=[])


live_sim = LiveSim()
