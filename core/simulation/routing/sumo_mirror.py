"""A working SUMO window for the Veins runs (2026-10-14): a SUMO 1.27 sumo-gui that mirrors the running SUMO 1.21 simulation car by car.

Why: Veins 5.3.1 speaks TraCI API <= 21, so the shared simulation must be SUMO 1.21; the 1.21 sumo-gui build draws a blank canvas on this
Mac (its OpenGL context fails under XQuartz, GLXBadContext, with any GL library tried). SUMO 1.27's window draws. So the Python client,
which already reads the 1.21 simulation every second, also opens a 1.27 sumo-gui on the SAME network and places every vehicle there at
the position the 1.21 simulation gives it (traci.vehicle.moveToXY), adds new ones, removes departed ones, and colours them:
yellow = has a Veins radio, blue = changed route on an advice it really received, white = no radio. The road-side units are red points
of interest. The mirror computes nothing; the simulation, the radio and the decisions stay in SUMO 1.21 + Veins + the server.
"""
from __future__ import annotations

import socket
import subprocess
import time
from pathlib import Path

YELLOW, BLUE, WHITE = (255, 210, 0, 255), (30, 90, 255, 255), (235, 235, 235, 255)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); return s.getsockname()[1]


class SumoMirror:
    def __init__(self, net: Path, rsus: list[dict], out: Path, focus_xy: tuple[float, float] | None = None, zoom: float = 1200.0, every_s: int = 1, label: str = ""):
        import sumo as _sumo27                                   # the main environment's eclipse-sumo 1.27 (its GUI draws here)
        gui = Path(_sumo27.SUMO_HOME) / "bin" / "sumo-gui"
        if not gui.exists():                                       # veins_env() has pointed `sumo` at 1.21: find the 1.27 install next to the main Python
            import sys
            gui = Path(sys.executable).parent.parent / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages" / "sumo" / "bin" / "sumo-gui"
        self.every, self.last, self.known, self.routes = every_s, -10**9, set(), set()
        self.port = _free_port()
        vs = out / "mirror_view.xml"
        fx, fy = focus_xy or rsus[0]["sumo_xy"]
        vs.write_text(f'<viewsettings>\n  <scheme name="mirror">\n    <background backgroundColor="white"/>\n    <edges laneEdgeMode="0" scaleMode="0" laneShowBorders="1">\n      <colorScheme name="uniform"><entry color="190,190,190"/></colorScheme>\n    </edges>\n    <vehicles vehicleMode="0" vehicleQuality="2" vehicle_minSize="1" vehicle_exaggeration="6" vehicle_constantSize="0">\n      <colorScheme name="given vehicle/type/route color"><entry color="yellow"/></colorScheme>\n    </vehicles>\n    <pois poi_exaggeration="3" poi_minSize="1" poiName_show="1" poiName_size="60" poiName_color="red"/>\n  </scheme>\n  <viewport zoom="{zoom:.0f}" x="{fx:.1f}" y="{fy:.1f}"/>\n  <delay value="0"/>\n</viewsettings>\n')
        self.proc = subprocess.Popen([str(gui), "-n", str(net), "--remote-port", str(self.port), "--start", "--step-length", "1", "--gui-settings-file", str(vs),
                                      "--window-size", "1100,850", "--window-pos", "0,30", "--no-step-log", "--no-warnings", "--collision.action", "none",
                                      "--time-to-teleport", "-1", "--ignore-route-errors"], stdout=open(out / "mirror.log", "w"), stderr=subprocess.STDOUT)
        import traci
        for _ in range(120):
            try:
                self.c = traci.connect(port=self.port, numRetries=0, label=f"mirror{self.port}"); break
            except Exception:                                      # noqa: BLE001
                time.sleep(0.5)
        else:
            raise RuntimeError("the SUMO 1.27 mirror window did not start")
        for i, r in enumerate(rsus):
            self.c.poi.add(f"RSU {i}", r["sumo_xy"][0], r["sumo_xy"][1], (220, 30, 30, 255), poiType="road-side unit", layer=20, width=25, height=25)
        try:                                                       # cars drawn 4x larger, coloured by what this mirror sets (yellow radio / blue rerouted / white)
            c = self.c
            c.gui.setSchema("View #0", "mirror")
        except Exception:                                          # noqa: BLE001
            pass
        if label:
            self.c.poi.add(label, fx, fy + 400, (0, 0, 0, 0), layer=0)
        self.rerouted: set[str] = set()

    def update(self, t: int, src, connected: set[str]) -> None:
        if t - self.last < self.every:
            return
        self.last = t
        c = self.c
        try:
            ids = src.vehicle.getIDList()
            now = set(ids)
            for vid in self.known - now:
                try:
                    c.vehicle.remove(vid)
                except Exception:                                  # noqa: BLE001
                    pass
            self.known &= now
            for vid in ids:
                x, y = src.vehicle.getPosition(vid); ang = src.vehicle.getAngle(vid)
                if vid not in self.known:
                    road = src.vehicle.getRoadID(vid)
                    rid = f"r:{road}"
                    if road.startswith(":"):
                        continue                                   # added when it is on a normal edge
                    if rid not in self.routes:
                        try:
                            c.route.add(rid, [road])
                        except Exception:                          # noqa: BLE001
                            pass
                        self.routes.add(rid)
                    try:
                        c.vehicle.add(vid, rid, departPos="0")
                        c.vehicle.setSpeedMode(vid, 0); c.vehicle.setLaneChangeMode(vid, 0)
                        self.known.add(vid)
                    except Exception:                              # noqa: BLE001
                        continue
                col = BLUE if vid in self.rerouted else YELLOW if vid in connected else WHITE
                try:
                    c.vehicle.moveToXY(vid, "", -1, x, y, ang, keepRoute=2)
                    c.vehicle.setColor(vid, col)
                except Exception:                                  # noqa: BLE001
                    pass
            c.simulationStep()
        except Exception:                                          # noqa: BLE001 - the mirror must never stop the run
            pass

    def close(self) -> None:
        try:
            self.c.close()
        except Exception:                                          # noqa: BLE001
            pass
        try:
            self.proc.terminate()
        except Exception:                                          # noqa: BLE001
            pass
