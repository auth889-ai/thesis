"""Preparing and launching one live run: the observed congestion on the corridor edges, the forecast
and routes for the arm that uses them, the SUMO process, and the TraCI connection to it."""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from app import evidence_paths as config

from .networks import file_hash, sumo_version


def prepare(cfg: dict, netinfo: dict, out: Path, set_msg) -> dict:
    """Levels -> slowed edges, delivery fraction, and the routes/forecast for the arm. Same code path as the batch chain."""
    from app.protocols.chains import integrated_chain as ic, live_chain as lc
    from app.routing.forecast_costs import build_table, fetch_forecast, recorded_city_data, write_weights
    a = argparse.Namespace(net=str(netinfo["net"]), routes=str(netinfo["routes"]), scale=cfg["scale"], horizon=cfg["duration_s"],
                           compliance=cfg["compliance"], v2x=cfg["v2x"], horizon_min=cfg["horizon_min"])
    set_msg("reading the observed congestion state")
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
    deliver_p, _ = ic.delivery_fraction(cfg["v2x"])
    routes, changed, advised, forecast = Path(a.routes), 0, 0, None
    advised_ids = set(cfg.get("advised_ids") or [])
    if cfg.get("routes_file"):                    # routes the production optimizer already decided (twin test)
        routes = Path(cfg["routes_file"]); changed = advised = len(advised_ids)
        forecast = cfg.get("forecast_label")
    elif cfg["arm"] == "prediction_aware" and not netinfo["live_coupled"]:
        raise RuntimeError("prediction_aware needs the observed corridors; a generated city has none yet — use baseline or reactive there")
    elif cfg["arm"] == "prediction_aware":
        set_msg("running the forecast and pricing the edges")
        res = fetch_forecast("dhaka", cfg["horizon_min"], None, source="recorded", as_of="peak")
        table = build_table(res, cfg["horizon_min"], Path(a.net))
        weights = write_weights(table, out / "forecast_weights.xml", 0.0, float(cfg["duration_s"]))
        forecast = table["forecast"]
        routes, changed, advised = ic.predeparture_routes(a, cfg["seed"], weights, out, deliver_p)
    return {"a": a, "cmap": cmap, "slow": slow, "deliver_p": deliver_p, "routes": routes, "changed": changed,
            "advised": advised, "advised_ids": advised_ids, "forecast": forecast}


def launch_sumo(cfg: dict, netinfo: dict, prep: dict, out: Path) -> tuple[subprocess.Popen, int, argparse.Namespace]:
    """Start sumo / sumo-gui listening on a free port. Returns (process, port, the chain's namespace)."""
    from app.twin import runtime as pr
    gui = bool(cfg.get("gui"))
    ns = argparse.Namespace(net=prep["a"].net, routes=str(prep["routes"]), seed=cfg["seed"], scale=cfg["scale"],
                            horizon=cfg["duration_s"], edgedata_period=300, time_to_teleport=300, sumo_binary="sumo-gui" if gui else "sumo")
    port = pr.free_port()
    gui_args = []
    if gui:                                        # the real SUMO window: starts by itself, closes when the run ends
        gui_args = ["--start", "--quit-on-end", "--window-size", "1400,900", "--delay", str(max(20, int(cfg.get("step_delay_ms") or 50)))]
        view = Path(netinfo["net"]).parent / "osm.view.xml"
        if view.exists():
            gui_args += ["--gui-settings-file", str(view)]
    proc = subprocess.Popen(pr.base_cmd(ns, out) + ["--remote-port", str(port)] + gui_args,
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    return proc, port, ns


def launch_record(cfg: dict, netinfo: dict, prep: dict, ns, proc, port: int, previous: dict) -> dict:
    """The provenance of this launch: binaries, files and their hashes, the probe."""
    probe = cfg.get("probe") or {}
    return {**previous, "sumo_pid": proc.pid, "sumo_version": sumo_version(), "sumo_binary": ns.sumo_binary,
            "network_file": str(netinfo["net"]), "network_hash": file_hash(netinfo["net"]), "demand_file": str(prep["routes"]), "demand_hash": file_hash(prep["routes"]),
            "scale": cfg["scale"], "duration_s": cfg["duration_s"], "compliance": cfg["compliance"], "port": port,
            "probe_vehicle_id": probe.get("id"), "origin_edge": probe.get("from_edge"), "destination_edge": probe.get("to_edge")}


def connect(port: int, proc: subprocess.Popen, run_id: str):
    """A TraCI Connection OBJECT, not the module: the module-level traci keeps one "current"
    connection per process, and a chain run in another thread would otherwise be stepping our
    SUMO (or we theirs)."""
    import traci
    last = None
    for _ in range(50):                                  # SUMO needs a moment to listen
        try:
            return traci.connect(port=port, numRetries=1, label=f"live-{run_id}")
        except Exception as exc:                          # noqa: BLE001
            last = exc
            if proc.poll() is not None:
                raise RuntimeError(f"SUMO exited early: {(proc.stderr.read() or '')[-800:]}")
            time.sleep(0.2)
    raise RuntimeError(f"could not connect to SUMO on port {port}: {last}")


def apply_slowdowns(conn, slow: dict) -> int:
    """The observed congestion, made real on the corridor edges in every arm. Returns the edges touched."""
    import traci
    applied = 0
    for eid, m in slow.items():
        try:
            for i in range(conn.edge.getLaneNumber(eid)):
                lid = f"{eid}_{i}"
                conn.lane.setMaxSpeed(lid, max(conn.lane.getMaxSpeed(lid) / m, 0.5))
            applied += 1
        except traci.TraCIException:
            pass
    return applied
