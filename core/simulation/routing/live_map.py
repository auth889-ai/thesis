"""A live map of the Veins forecast-routing run, drawn by the Python client from the running simulation (2026-10-14).

Why: the SUMO 1.21 window that Veins needs draws a blank canvas on this Mac (its OpenGL fails under XQuartz: GLXBadContext), so the
run shows its own map. Everything drawn is read from the simulation at that second, nothing is replayed:
  * grey: the road network (the SUMO .net.xml);
  * red triangles + faint circles: the road-side units and the 600 m in which the server hands them advice;
  * yellow dots: connected cars (they have a Veins radio); small grey dots: the other cars;
  * green lines: a status frame that a unit REALLY decoded in the last seconds (Veins's PHY decided it), car -> unit;
  * blue lines: an advice handed to a unit for a car; blue dots: cars whose route changed on a received advice;
  * the right panel: the server's forecast, round by round (Graph WaveNet on the real METR-LA bins) and the counts.
"""
from __future__ import annotations

from pathlib import Path


class LiveMap:
    def __init__(self, net_path: Path, rsus: list[dict], title: str, every_s: int = 10, reach_m: float = 600.0):
        import matplotlib
        try:
            matplotlib.use("MacOSX")
        except Exception:                                          # noqa: BLE001
            pass
        import matplotlib.pyplot as plt
        from matplotlib.collections import LineCollection
        import sumolib
        self.plt, self.every, self.rsus = plt, every_s, rsus
        net = sumolib.net.readNet(str(net_path))
        segs = []
        for e in net.getEdges():
            if e.getFunction() == "internal":
                continue
            shp = e.getShape()
            segs += [(shp[j], shp[j + 1]) for j in range(len(shp) - 1)]
        plt.ion()
        self.fig = plt.figure(figsize=(15, 9))
        self.fig.canvas.manager.set_window_title("Veins forecast routing: live map (SUMO + Veins + server)")
        self.ax = self.fig.add_axes([0.02, 0.04, 0.62, 0.9])
        self.tx = self.fig.add_axes([0.66, 0.04, 0.33, 0.9]); self.tx.axis("off")
        self.ax.add_collection(LineCollection(segs, colors="#c8c8c8", linewidths=0.4, zorder=1))
        xs, ys = zip(*[r["sumo_xy"] for r in rsus])
        self.ax.scatter(xs, ys, marker="^", s=90, c="#d62728", zorder=5, label="road-side unit (RSU)")
        for x, y in zip(xs, ys):
            self.ax.add_patch(plt.Circle((x, y), reach_m, color="#d62728", fill=False, alpha=0.15, lw=0.6))
        x0, y0, x1, y1 = net.getBoundary()
        self.ax.set_xlim(x0, x1); self.ax.set_ylim(y0, y1); self.ax.set_aspect("equal"); self.ax.set_xticks([]); self.ax.set_yticks([])
        self.title = title
        self.others = self.ax.scatter([], [], s=2, c="#9a9a9a", zorder=2)
        self.conn = self.ax.scatter([], [], s=9, c="#f2c200", zorder=3, label="connected car (radio)")
        self.rer = self.ax.scatter([], [], s=28, c="#1f5bd6", zorder=6, label="rerouted on a received advice")
        self.up = LineCollection([], colors="#2ca02c", linewidths=0.8, alpha=0.8, zorder=4, label="status frame decoded by an RSU")
        self.down = LineCollection([], colors="#1f5bd6", linewidths=1.6, alpha=0.9, zorder=4, label="advice frame RSU -> car")
        self.ax.add_collection(self.up); self.ax.add_collection(self.down)
        self.ax.legend(loc="lower left", fontsize=8, framealpha=0.9)
        self.uplinks: list = []; self.downlinks: list = []; self.rounds: list[str] = []; self.rerouted: set[str] = set()
        self.last = -1
        plt.show(block=False); plt.pause(0.05)

    def frame_up(self, car_xy, rsu: int) -> None:
        if car_xy and len(self.uplinks) < 400:
            self.uplinks.append((car_xy, tuple(self.rsus[rsu]["sumo_xy"])))

    def frame_down(self, car_xy, rsu: int) -> None:
        if car_xy:
            self.downlinks.append((tuple(self.rsus[rsu]["sumo_xy"]), car_xy))

    def round_line(self, s: str) -> None:
        self.rounds.append(s); self.rounds = self.rounds[-6:]

    def update(self, t: int, c, conn: set[str], counts: dict) -> None:
        if t - self.last < self.every:
            return
        self.last = t
        try:
            ids = c.vehicle.getIDList()
            pos = {v: c.vehicle.getPosition(v) for v in ids}
        except Exception:                                          # noqa: BLE001
            return
        import numpy as np
        oth = [p for v, p in pos.items() if v not in conn]
        con = [p for v, p in pos.items() if v in conn and v not in self.rerouted]
        rer = [p for v, p in pos.items() if v in self.rerouted]
        self.others.set_offsets(np.array(oth) if oth else np.empty((0, 2)))
        self.conn.set_offsets(np.array(con) if con else np.empty((0, 2)))
        self.rer.set_offsets(np.array(rer) if rer else np.empty((0, 2)))
        self.up.set_segments(self.uplinks); self.down.set_segments(self.downlinks)
        self.uplinks, self.downlinks = [], self.downlinks[-30:]
        self.ax.set_title(f"{self.title}   t = {t} s   cars {len(ids)}   connected {len(con) + len(rer)}", fontsize=10)
        self.tx.clear(); self.tx.axis("off")
        lines = ["WHAT IS HAPPENING (all read from the running simulation)", "",
                 f"SUMO 1.21: moves {len(ids)} cars on the real Los Angeles map",
                 f"Veins/OMNeT++: every status frame through PHY+MAC;",
                 f"  RSUs decoded {counts['rx']} frames so far",
                 f"  distinct statuses reaching the server: {counts['unique']}",
                 "", f"Server (this Python process):",
                 "  every 300 s from 1500 s: Graph WaveNet on the real",
                 "  METR-LA history up to that moment, corrected by the",
                 "  statuses the RSUs decoded, then 5 alternatives/car,",
                 "  reroute only if it saves >= 60 s and 5 %", ""]
        lines += [("  " + r) for r in self.rounds] or ["  (first forecast at t = 1500 s; nothing before the warm-up)"]
        lines += ["", f"Advice: handed to an RSU {counts['handed']}, applied by a car that",
                  f"  really decoded it {counts['applied']}, expired out of RSU reach {counts['expired']}"]
        self.tx.text(0, 1, "\n".join(lines), va="top", family="monospace", fontsize=8.5)
        self.fig.canvas.draw_idle(); self.plt.pause(0.001)

    def close(self, final: str) -> None:
        try:
            self.ax.set_title(final, fontsize=10); self.fig.canvas.draw_idle(); self.plt.pause(0.5)
        except Exception:                                          # noqa: BLE001
            pass
