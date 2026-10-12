"""make gui-ambulance-loop (Part E, 2026-10-12): the ML + V2X ambulance loop (core/simulation/ambulance/rl_v2x_loop.py, UNCHANGED) in sumo-gui.

    PYTHONPATH=.:backend ~/.dhakaflow/venvs/sumo-rl-np1/bin/python scripts/live/gui_ambulance_loop.py [--seed 11] [--arm rl_v2i] [--tech its_g5] [--delay 60] [--no-gui]

Display only, added from outside the loop: the loop module's LoopRun is replaced by a subclass that paints after each step and prints each
V2X event to a junction; sumo-rl's own use_gui path is switched on from outside (its init connection stays headless) and the loop's SUMO options get the window options. No decision,
message, or signal action changes: the run is rl_v2x_loop.run(seed, arm, tech).
  * the ambulance red; a car that received the alert turns yellow and stays yellow while it is making way; cars out of range or whose
    message was lost stay white (they never received anything);
  * at each route junction a label with the controller in charge: "Q-learning" (or "fixed time"), then "V2X override (msg delivered t=…)"
    while the copied emergency override holds it, then "Q-learning (released)";
  * terminal: one line per V2X message to a junction (sent -> delivered / lost / out of range, per junction), and a final summary with the
    ambulance's travel time and everyone else's vehicle-hours, read from the run's metrics.
Output: evidence/live_runs/gui_ambulance_loop/<stamp>/ (the run's metrics.json under runs/, and last_run.json with the printed events).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / "backend")]

OUT = REPO / "evidence/live_runs/gui_ambulance_loop"
RED, YELLOW, WHITE = (230, 30, 30, 255), (255, 220, 0, 255), (255, 255, 255, 255)
VIEW = """<viewsettings>
  <scheme name="live">
    <background backgroundColor="white" showGrid="0"/>
    <edges laneEdgeMode="0" laneShowBorders="1" showLinkDecals="1" showRails="1" hideConnectors="0"/>
    <vehicles vehicleMode="0" vehicleQuality="2" vehicle_minSize="1" vehicle_exaggeration="5" showBlinker="1" vehicleColor="255,255,255"/>
    <pois poi_minSize="0" poi_exaggeration="1" poiName_show="0" poiText_show="1" poiTextParam="label" poiText_size="120" poiText_color="20,20,20"/>
  </scheme>
</viewsettings>
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--arm", default="rl_v2i", choices=["rl_v2i", "fixed_v2i", "rl", "fixed"])
    ap.add_argument("--tech", default="its_g5", choices=["its_g5", "c_v2x", "cellular_4g"])
    ap.add_argument("--share", type=float, default=1.0)
    ap.add_argument("--delay", type=float, default=60.0, help="sumo-gui delay per step, ms (the ambulance departs at 900 s; the window runs at full speed before it)")
    ap.add_argument("--no-gui", action="store_true")
    a = ap.parse_args(argv)
    spec = importlib.util.spec_from_file_location("rl_v2x_loop", REPO / "core/simulation/ambulance/rl_v2x_loop.py")
    loop = importlib.util.module_from_spec(spec); spec.loader.exec_module(loop)
    from core.simulation.ambulance import rl_signals, service
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = OUT / stamp; root.mkdir(parents=True, exist_ok=True)
    view = root / "view.xml"; view.write_text(VIEW)
    events: list[dict] = []; rl = a.arm.startswith("rl")
    cfg = service.settings()
    print(f"LIVE RUN (ambulance loop, Dhaka corridor, SIMULATION): seed {a.seed}, arm {a.arm} ({'sumo-rl Q-learning on the 3 corridor signals' if rl else 'SUMO fixed-time programmes'}"
          f"{', V2X alert over ' + a.tech + ' to cars and junctions, pre-emption only on a delivered message' if a.arm.endswith('_v2i') else ', no alert'}), {int(a.share * 100)} % equipped;"
          f" the ambulance departs at {cfg['ambulance']['depart_s']} s. The loop is core/simulation/ambulance/rl_v2x_loop.py (unchanged); this script only colours, labels and prints.", flush=True)

    class GuiLoopRun(loop.LoopRun):
        """The loop's LoopRun, painting after each step. Nothing of the alert or override is touched."""
        def __init__(self, conn, scen, arm, technology, share, seed, cfg=None):
            super().__init__(conn, scen, arm, technology, share, seed, cfg)
            self.painted: dict[str, tuple] = {}; self.hud = False; self.labels: dict[str, str] = {}
            self.gui = not a.no_gui
            if self.gui:
                for s in self.all_signals:
                    try:
                        conn.poi.add(f"lbl_{s['tls']}", s["x"], s["y"] + 60, (0, 0, 0, 0))
                        self._label(s["tls"], "Q-learning" if rl else "fixed time")
                    except Exception:                          # noqa: BLE001 - display only
                        pass

        def _label(self, tls: str, text: str) -> None:
            if self.labels.get(tls) != text:
                self.labels[tls] = text
                if self.gui:
                    try:
                        self.conn.poi.setParameter(f"lbl_{tls}", "label", text)
                    except Exception:                          # noqa: BLE001
                        pass

        def _send(self, sender, receiver, t):
            before = dict(self.msgs)
            ok = super()._send(sender, receiver, t)
            if receiver.id in self.per_junction:
                why = next((k for k in ("delivered", "lost", "out_of_range") if self.msgs[k] != before[k]), "?")
                ev = {"t": t, "junction": receiver.id, "result": why}
                events.append(ev)
                if why != "out_of_range" or self.per_junction[receiver.id]["out_of_range"] in (1, 10, 100, 1000):   # every delivery/loss; out-of-range at 1, 10, 100, 1000
                    print(f"  t={t:.0f}s  V2X to junction {receiver.id[:28]}: sent -> {why.upper()}  (this junction so far: {self.per_junction[receiver.id]})", flush=True)
            return ok

        def step(self, t):
            super().step(t)
            if not self.gui:
                return
            v = self.conn.vehicle
            ids = set(v.getIDList())
            if loop.service.AMBULANCE in ids and self.painted.get(loop.service.AMBULANCE) != RED:
                v.setColor(loop.service.AMBULANCE, RED); self.painted[loop.service.AMBULANCE] = RED
                self.conn.gui.trackVehicle("View #0", loop.service.AMBULANCE); self.conn.gui.setZoom("View #0", 500)
            making = set(self.makeway.before) if hasattr(self, "makeway") else set()
            for vid in ids:
                if vid == loop.service.AMBULANCE:
                    continue
                want = YELLOW if (vid in self.alerted and vid in making) else WHITE
                if self.painted.get(vid) != want:
                    v.setColor(vid, want); self.painted[vid] = want
            for e in self.events:
                if e["what"] == "takeover" or e["what"] == "informed":
                    self._label(e["tls"], f"V2X override (msg delivered t={e['t']:.0f} s)")
            for e in self.events:
                if e["what"] == "released":
                    self._label(e["tls"], ("Q-learning" if rl else "fixed time") + " (released)")
            if self.state == "driving" and a.delay:
                time.sleep(a.delay / 1000.0)

    loop.LoopRun = GuiLoopRun
    loop.sumo_env()                                            # SUMO_HOME for sumo-rl, as the loop sets it at run time
    sumo_rl = rl_signals._sumo_rl()[0]
    if not a.no_gui:                                           # sumo-rl's OWN GUI path (use_gui=True adds --start --quit-on-end and the schema; its init connection stays headless),
        orig_init, orig_extra = sumo_rl.SumoEnvironment.__init__, rl_signals._extra      # plus the window options on the loop's SUMO command

        def gui_init(self, *args, **kwargs):
            kwargs["use_gui"] = True
            orig_init(self, *args, **kwargs)
        sumo_rl.SumoEnvironment.__init__ = gui_init
        rl_signals._extra = lambda out, scale, horizon, cfg_: orig_extra(out, scale, horizon, cfg_) + f" --window-size 1600,1000 --gui-settings-file {view}"
    t0 = time.time()
    try:
        m = loop.run(a.seed, a.arm, a.tech, a.share, None, root / "runs")
    finally:
        if not a.no_gui:
            sumo_rl.SumoEnvironment.__init__, rl_signals._extra = orig_init, orig_extra
    amb, oth = m.get("ambulance") or {}, m.get("others") or {}
    print("", f"RESULT (seed {a.seed}, arm {a.arm}, {a.tech}): ambulance travel time {amb.get('travel_time_s')} s, arrived {amb.get('arrived')}; everyone else {oth.get('total_vehicle_hours')} vehicle-hours,"
          f" teleports {m.get('teleports')}; messages {m.get('messages')}; cars alerted {m.get('vehicles_alerted')}"
          + (f"; SUMO CRASHED: {m.get('crash')}" if m.get("state") == "sumo_crashed" else ""), sep="\n", flush=True)
    for tls, c in (m.get("messages_per_junction") or {}).items():
        ev = {e["what"]: e["t"] for e in m.get("preemption_events", []) if e["tls"] == tls}
        print(f"  junction {tls[:40]}: sent {c['sent']} delivered {c['delivered']} lost {c['lost']} out of range {c['out_of_range']}; informed {ev.get('informed')} s, override from {ev.get('takeover')} s to {ev.get('released')} s", flush=True)
    (root / "last_run.json").write_text(json.dumps({"args": vars(a), "events_to_junctions": events, "metrics": {k: m.get(k) for k in ("state", "ambulance", "others", "teleports", "messages", "messages_per_junction", "preemption_events", "wall_s")},
                                                   "wall_s": round(time.time() - t0)}, indent=1, default=str))
    return 0 if m.get("state") != "sumo_crashed" else 3


if __name__ == "__main__":
    sys.exit(main())
