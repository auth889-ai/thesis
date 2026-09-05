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
            "continuous": False, "network": "dhaka_r1", "gui": False}
# vehicle colours in sumo-gui (RGBA): what a viewer sees moving on the OSM network
COLOUR = {"normal": (255, 200, 0, 255),        # background vehicle (SUMO passenger)
          "reactive": (40, 120, 255, 255),     # rerouted by rerouteTraveltime on current travel times
          "advised": (40, 190, 60, 255),       # pre-departure route from the production optimizer (prediction-aware / oracle debug)
          "stopped": (220, 40, 40, 255),       # standing > 20 s (queue)
          "probe": (255, 0, 255, 255),         # the USER PROBE: the analysed trip
          "heavy": (150, 150, 150, 255)}       # bus / truck, where the demand has them
VISUAL_LEGEND = {"NORMAL BACKGROUND VEHICLE": "amber", "REACTIVE-REROUTED VEHICLE": "blue", "PREDICTION-AWARE-REROUTED VEHICLE": "green",
                 "USER PROBE VEHICLE": "magenta, 8 m long", "STOPPED / QUEUED VEHICLE (> 20 s)": "red", "BUS / TRUCK": "grey"}
TELEPORT_REASON = "SUMO teleports a vehicle that waited longer than --time-to-teleport (300 s) at a blocked position (jam / junction blocker); TraCI exposes the event, not the reason text"
_FILE_HASH: dict[str, str] = {}


def file_hash(path, n: int = 12) -> str | None:
    """sha256 prefix of a file, cached by path+mtime (network and demand hashes for provenance)."""
    import hashlib
    try:
        p = Path(path); key = f"{p}:{p.stat().st_mtime_ns}"
        if key not in _FILE_HASH:
            _FILE_HASH[key] = hashlib.sha256(p.read_bytes()).hexdigest()[:n]
        return _FILE_HASH[key]
    except OSError:
        return None


def sumo_version() -> str:
    import subprocess
    try:
        return subprocess.run(["sumo", "--version"], capture_output=True, text=True, timeout=20).stdout.splitlines()[0].strip()
    except Exception as exc:                            # noqa: BLE001
        return f"unknown ({exc})"


def scenario_label(netinfo: dict) -> dict:
    """Where the running scenario's road network and demand come from — always visible."""
    if netinfo.get("live_coupled"):
        return {"demand": "REAL / CALIBRATED DATA", "network": "REAL OSM ROAD NETWORK (Dhaka R1, frozen, calibrated demand)",
                "note": "calibrated hourly demand; live corridor state from the provider when continuous"}
    d = str(netinfo.get("demand") or "SYNTHETIC_WHAT_IF")
    return {"demand": "UPLOADED FLOW DATA" if d.startswith("UPLOADED") else "SYNTHETIC WHAT-IF DEMAND",
            "network": "REAL OSM ROAD NETWORK", "note": "randomTrips demand (osmWebWizard parameters) is NOT real traffic; it demonstrates mechanism only"}
DHAKA_CENTER = (90.395, 23.755)


def networks() -> list[dict]:
    """Every network the twin can run: the calibrated Dhaka R1, then any city generated from OSM."""
    from pipeline.city.registry import CITY_DIR
    out = [{"id": "dhaka_r1", "name": "Dhaka R1 (calibrated)", "demand": "CALIBRATED",
            "center": list(DHAKA_CENTER), "live_coupled": True,
            "note": "frozen OSM network, calibrated demand, live corridor state from Google"}]
    if CITY_DIR.exists():
        for d in sorted(CITY_DIR.iterdir()):
            m = d / "sumo" / "MANIFEST.json"
            if m.exists():
                try:
                    man = json.loads(m.read_text())
                except json.JSONDecodeError:
                    continue
                s_, w, n, e = man["bbox"]
                out.append({"id": man["city_id"], "name": man.get("display_name") or man["city_id"],
                            "demand": man["demand_reality"], "center": [(w + e) / 2, (s_ + n) / 2],
                            "bbox": man["bbox"], "edges": man["edges"], "traffic_lights": man["traffic_lights"],
                            "live_coupled": False, "generated_utc": man["generated_utc"],
                            "note": man["warning"]})
    return out


def resolve_network(network: str) -> dict:
    from pipeline.routing import predictive_routing as pr
    if network in ("dhaka_r1", "", None):
        return {"id": "dhaka_r1", "net": Path(pr.DEFAULT_NET), "routes": Path(pr.DEFAULT_ROUTES),
                "demand": "CALIBRATED", "center": DHAKA_CENTER, "live_coupled": True}
    from pipeline.city.sumo_scenario import scenario_dir
    m = scenario_dir(network) / "MANIFEST.json"
    if not m.exists():
        raise ValueError(f"no generated network for {network!r}; generate it first")
    man = json.loads(m.read_text())
    s_, w, n, e = man["bbox"]
    return {"id": network, "net": config.REPO / man["files"]["net"], "routes": config.REPO / man["files"]["routes"],
            "demand": man["demand_reality"], "center": ((w + e) / 2, (s_ + n) / 2), "live_coupled": False}
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
            from pipeline.core.network_file import ensure_net
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
        from pipeline.routing import integrated_chain as ic
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
            netinfo = resolve_network(cfg["network"])
            net = self._net_obj(netinfo["net"])
            a = argparse.Namespace(net=str(netinfo["net"]), routes=str(netinfo["routes"]),
                                   scale=cfg["scale"], horizon=cfg["duration_s"],
                                   compliance=cfg["compliance"], v2x=cfg["v2x"],
                                   horizon_min=cfg["horizon_min"])
            # 1. the observed congestion, made real on the corridor edges in every arm
            self._set(message="reading the observed congestion state")
            levels = {}
            if not netinfo["live_coupled"]:
                cfg["levels"] = ""                    # no observed corridors on a generated city
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
            advised_ids = set(cfg.get("advised_ids") or [])
            if cfg.get("routes_file"):                    # routes the production optimizer already decided (twin test)
                routes = Path(cfg["routes_file"]); changed = advised = len(advised_ids)
                forecast = cfg.get("forecast_label")
            elif cfg["arm"] == "prediction_aware" and not netinfo["live_coupled"]:
                raise RuntimeError("prediction_aware needs the observed corridors; a generated city "
                                   "has none yet — use baseline or reactive there")
            elif cfg["arm"] == "prediction_aware":
                self._set(message="running the forecast and pricing the edges")
                res = fetch_forecast("dhaka", cfg["horizon_min"], None, source="recorded", as_of="peak")
                table = build_table(res, cfg["horizon_min"], Path(a.net))
                weights = write_weights(table, out / "forecast_weights.xml", 0.0, float(cfg["duration_s"]))
                forecast = table["forecast"]
                routes, changed, advised = ic.predeparture_routes(a, cfg["seed"], weights, out, deliver_p)
            gui = bool(cfg.get("gui"))
            ns = argparse.Namespace(net=a.net, routes=str(routes), seed=cfg["seed"], scale=cfg["scale"],
                                    horizon=cfg["duration_s"], edgedata_period=300,
                                    time_to_teleport=300, sumo_binary="sumo-gui" if gui else "sumo")
            self._set(message="starting SUMO", edges_congested=len(slow), delivery_fraction=deliver_p,
                      forecast=forecast, advised=advised, routes_changed=changed)
            import subprocess
            port = pr.free_port()
            gui_args = []
            if gui:                                        # the real SUMO window: starts by itself, closes when the run ends
                gui_args = ["--start", "--quit-on-end", "--window-size", "1400,900", "--delay", str(max(20, int(cfg.get("step_delay_ms") or 50)))]
                view = Path(netinfo["net"]).parent / "osm.view.xml"
                if view.exists():
                    gui_args += ["--gui-settings-file", str(view)]
            proc = subprocess.Popen(pr.base_cmd(ns, out) + ["--remote-port", str(port)] + gui_args,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            self._proc, self._conn = proc, None
            n_edges = netinfo.get("edges") or next((n.get("edges") for n in networks() if n["id"] == netinfo["id"]), None)
            launch = {**self.state(with_vehicles=False).get("launch", {}), "sumo_pid": proc.pid, "sumo_version": sumo_version(), "sumo_binary": ns.sumo_binary,
                      "network_file": str(netinfo["net"]), "network_hash": file_hash(netinfo["net"]), "demand_file": str(routes), "demand_hash": file_hash(routes),
                      "scale": cfg["scale"], "duration_s": cfg["duration_s"], "compliance": cfg["compliance"], "port": port,
                      "probe_vehicle_id": (cfg.get("probe") or {}).get("id"), "origin_edge": (cfg.get("probe") or {}).get("from_edge"),
                      "destination_edge": (cfg.get("probe") or {}).get("to_edge")}
            self._set(pid=proc.pid, port=port, gui=gui, sumo_binary=ns.sumo_binary, network_edges=n_edges, launch=launch)
            (out / "launch.json").write_text(json.dumps(launch, indent=1, default=str))
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
            self._conn = conn
            rerouted: dict[str, str] = {}                   # vid -> "reactive" | "advised", for the colours
            probe = cfg.get("probe") or None                # the analysed trip: {id, from_edge, to_edge, depart_s, route_edges?}
            probe_state: dict = {}
            if probe:
                pid = probe["id"]
                if probe.get("route_edges"):                # the prediction-aware arm: duarouter on the forecast weights
                    edges = list(probe["route_edges"])
                else:                                       # baseline / reactive: SUMO's own findRoute on the current network
                    rr = conn.simulation.findRoute(probe["from_edge"], probe["to_edge"])
                    edges = list(rr.edges)
                    if not edges:
                        raise RuntimeError(f"SUMO_OD_MAPPING_FAILED: no route from {probe['from_edge']} to {probe['to_edge']}")
                conn.route.add(f"route_{pid}", edges)
                conn.vehicle.add(pid, f"route_{pid}", depart=str(float(probe.get("depart_s") or 0)), departLane="best", departSpeed="max")
                probe_state = {"vehicle_id": pid, "origin_edge": probe["from_edge"], "destination_edge": probe["to_edge"],
                               "initial_route": edges, "initial_route_source": probe.get("route_source") or ("production optimizer route" if probe.get("route_edges") else "traci.simulation.findRoute"),
                               "active_route": edges, "departed_s": None, "arrived_s": None, "rerouted_times": 0, "teleported": False,
                               "status": "WAITING TO DEPART", "current_edge": None, "speed_kmh": None, "elapsed_s": None, "route_progress": None}
                try:                                    # visibly distinct in sumo-gui: magenta and 8 m long
                    conn.vehicle.setColor(pid, COLOUR["probe"]); conn.vehicle.setLength(pid, 8.0); conn.vehicle.setWidth(pid, 2.6)
                except traci.TraCIException:
                    pass
                self._set(probe=probe_state)
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
            depart_t: dict[str, int] = {}                  # vehicle -> departure step, for the mean travel time so far
            tt_sum, tt_n = 0.0, 0
            heavy: set[str] = set()
            teleport_events: list[dict] = []
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
                    if netinfo["live_coupled"] and time.time() - last_live >= LIVE_REFRESH_S:
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
                    conn.vehicle.subscribe(vid, sub); depart_t[vid] = t
                    if gui:
                        try:
                            if conn.vehicle.getVehicleClass(vid) in ("bus", "truck", "trailer", "coach", "delivery"):
                                heavy.add(vid); conn.vehicle.setColor(vid, COLOUR["heavy"])
                        except traci.TraCIException:
                            pass
                for vid in conn.simulation.getArrivedIDList():
                    d0 = depart_t.pop(vid, None)
                    if d0 is not None:
                        tt_sum += t - d0; tt_n += 1
                arrived += conn.simulation.getArrivedNumber()
                tele_now = conn.simulation.getStartingTeleportIDList()
                teleports += len(tele_now)
                for vid in tele_now:                    # every teleport is recorded, never hidden
                    try:
                        edge = conn.vehicle.getRoadID(vid)
                    except traci.TraCIException:
                        edge = None
                    ev = {"vehicle_id": vid, "sim_time_s": t, "edge": edge, "arm": cfg["arm"], "reason": TELEPORT_REASON, "is_probe": bool(probe and vid == probe["id"])}
                    teleport_events.append(ev)
                    if probe and vid == probe["id"]:
                        probe_state.update(teleported=True, teleported_at_s=t, teleported_edge=edge, status="PROBE TELEPORTED")
                    note(f"TELEPORT {ev}")
                if probe and probe_state.get("departed_s") is None and probe["id"] in conn.vehicle.getIDList():
                    probe_state["departed_s"] = t; probe_state["status"] = "DRIVING"
                    if gui and not getattr(self, "_tracking", None):      # the window follows the user's car from its first metre
                        try:
                            conn.gui.trackVehicle("View #0", probe["id"]); conn.gui.setZoom("View #0", 10000); self._tracking = probe["id"]
                        except traci.TraCIException:
                            pass
                if probe and probe_state.get("departed_s") is not None and probe_state.get("arrived_s") is None:
                    if probe["id"] in conn.simulation.getArrivedIDList():
                        probe_state["arrived_s"] = t; probe_state["status"] = "ARRIVED"; probe_state["elapsed_s"] = t - probe_state["departed_s"]
                        probe_state.update(current_edge=probe["to_edge"], speed_kmh=0.0, route_progress=1.0)
                        if gui and getattr(self, "_tracking", None) == probe["id"]:     # the trip is over: stop tracking, show the network
                            try:
                                conn.gui.trackVehicle("View #0", ""); conn.gui.setZoom("View #0", 1500); self._tracking = None
                            except traci.TraCIException:
                                pass
                    elif probe["id"] in conn.vehicle.getIDList() and not probe_state.get("teleported"):
                        try:                                   # live probe telemetry, straight from SUMO every step
                            pid = probe["id"]
                            v = conn.vehicle.getSpeed(pid); w = conn.vehicle.getWaitingTime(pid)
                            cur_edge = conn.vehicle.getRoadID(pid)
                            probe_state.update(current_edge=cur_edge, speed_kmh=round(v * 3.6, 1), elapsed_s=t - probe_state["departed_s"],
                                               waiting_now_s=round(w, 1), status="QUEUED" if v < 0.1 and w > 5 else "DRIVING",
                                               route_progress=round(conn.vehicle.getRouteIndex(pid) / max(len(probe_state["active_route"]), 1), 3))
                            if t % 5 == 0:
                                cur = list(conn.vehicle.getRoute(pid))
                                if cur != probe_state["active_route"]:
                                    probe_state["rerouted_times"] += 1; probe_state["active_route"] = cur
                                    probe_state.setdefault("reroute_events", []).append({"sim_time_s": t, "edge": cur_edge, "route_edges": len(cur)})
                                if gui:
                                    conn.vehicle.setColor(pid, COLOUR["probe"])
                        except traci.TraCIException:
                            pass
                if cfg["arm"] == "reactive":
                    for vid in conn.vehicle.getIDList():
                        if not (pr.equipped(vid, cfg["compliance"]) or (probe and vid == probe["id"])):
                            continue
                        if not ic.delivered(vid, deliver_p, cfg["v2x"], cfg["seed"]) and not (probe and vid == probe["id"]):
                            continue
                        if (int(hashlib.md5(vid.encode()).hexdigest()[8:12], 16) + t) % 60 == 0:
                            try:
                                before = conn.vehicle.getRoute(vid)
                                conn.vehicle.rerouteTraveltime(vid, currentTravelTimes=True)
                                reroutes += 1
                                if gui and conn.vehicle.getRoute(vid) != before:
                                    rerouted[vid] = "reactive"; conn.vehicle.setColor(vid, COLOUR["reactive"])
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
                    if gui and t % 5 == 0 and not (probe and vid == probe["id"]):   # colour what the viewer sees: stopped red, otherwise its role
                        try:
                            if v < 0.1 and w > 20:
                                conn.vehicle.setColor(vid, COLOUR["stopped"])
                            elif vid in heavy:
                                conn.vehicle.setColor(vid, COLOUR["heavy"])
                            else:
                                role = rerouted.get(vid) or ("advised" if (vid in advised_ids or (cfg["arm"] == "prediction_aware" and not advised_ids and pr.equipped(vid, cfg["compliance"]))) else "normal")
                                conn.vehicle.setColor(vid, COLOUR[role])
                        except traci.TraCIException:
                            pass
                    if len(vehicles) < MAX_VEHICLES_SHOWN:
                        lon, lat = net.convertXY2LonLat(x, y)
                        vehicles.append([round(lon, 5), round(lat, 5), round(v * 3.6, 1),
                                         int(pr.equipped(vid, cfg["compliance"]))])
                n = len(res)
                if probe:
                    self._set(probe=dict(probe_state))
                self._set(sim_time_s=t, vehicles=vehicles, teleport_events=teleport_events[-200:], kpis={
                    "vehicles_on_road": n, "shown": len(vehicles), "mean_travel_time_so_far_s": round(tt_sum / tt_n, 1) if tt_n else None,
                    "trips_completed": tt_n, "teleport_events": len(teleport_events), "probe_status": probe_state.get("status") if probe else None,
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
            if probe:                                        # the probe's own trip from SUMO's tripinfo (the measured outcome)
                import xml.etree.ElementTree as ET
                try:
                    for el in ET.parse(out / "tripinfo.xml").getroot().iter("tripinfo"):
                        if el.get("id") == probe["id"]:
                            probe_state.update(travel_time_s=float(el.get("duration")), route_length_m=float(el.get("routeLength")),
                                               waiting_time_s=float(el.get("waitingTime")), time_loss_s=float(el.get("timeLoss")),
                                               finished=el.get("arrival") not in (None, "-1.00", "-1"))
                except Exception as exc:                          # noqa: BLE001
                    probe_state["tripinfo_error"] = str(exc)[:120]
                self._set(probe=probe_state)
            rec = {"run_id": run_id, "params": {k: v for k, v in cfg.items() if k != "advised_ids"}, "stopped_early": bool(self._stop.is_set()),
                   "launch": self.state(with_vehicles=False).get("launch"), "teleport_events": teleport_events, "probe": probe_state or None,
                   "scenario": scenario_label(netinfo),
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
