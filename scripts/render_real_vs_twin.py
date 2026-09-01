#!/usr/bin/env python3
"""REAL cars vs TWIN cars — side by side, same street, same minute.

Left: actual pNEUMA drone-measured vehicle positions (every dot = a real
vehicle, 25 Hz measurements). Right: the calibrated SUMO twin (fcd output).
Answers 'where are the real cars' with literally the real cars.
"""
from __future__ import annotations

import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
SP = Path("/private/tmp/claude-501/-Users-jannatulferdouseva-thesis/"
          "fdc3d95a-9e51-4b32-a390-6d1fbc06a61a/scratchpad/urban")
T0, T1 = 372.5, 462.5          # first 90 s of held-out B
OUT = SP / "real_vs_twin"


def main() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import sumolib
    from research.urban.pneuma_provider import parse
    from scripts.gate_urban_site import load_osm

    OUT.mkdir(exist_ok=True)
    net = sumolib.net.readNet(str(SP / "athens_d8.net.xml"))
    nodes, ways, signals, _ = load_osm()

    # twin side = VALIDATED REGIME: per-cycle initialization from the REAL
    # vehicle states at T0 (the calibration paper's protocol), then 90 s of
    # physics; arrivals during the window are the REAL entry events.
    fcd = SP / "twin_fcd_cycleinit.xml"
    if not fcd.exists():
        import libsumo as t
        tracks_all = list(parse(str(SP / "d8.csv"), hz=1.0))
        init, arrivals = [], []
        for tr in tracks_all:
            at0 = [x for x in tr.samples if abs(x.t - T0) <= 1.0]
            if at0:
                s0 = at0[0]
                init.append((tr.vid, s0))
            else:
                first = tr.samples[0]
                if T0 < first.t < T1 - 5:
                    arrivals.append((tr.vid, first))
        t.start(["sumo", "-n", str(SP / "athens_d8.net.xml"),
                 "--no-step-log", "--no-warnings", "--seed", "11",
                 "--time-to-teleport", "600",
                 "--fcd-output", str(fcd), "--fcd-output.geo"])
        t.vehicletype.copy("DEFAULT_VEHTYPE", "tw")
        stats = {"placed": 0, "no_edge": 0, "fail": 0}

        def place(vid, smp, depart_now):
            x, y = net.convertLonLat2XY(smp.lon, smp.lat)
            edges = net.getNeighboringEdges(x, y, r=30)
            if not edges:
                stats["no_edge"] += 1
                return
            e, _d = sorted(edges, key=lambda p: p[1])[0]
            seq = [e.getID()]
            cur = e
            for _ in range(14):
                outs = cur.getOutgoing()
                if not outs:
                    break
                cur = max(outs, key=lambda o: o.getLaneNumber())
                seq.append(cur.getID())
            rid = f"r{vid}"
            try:
                t.route.add(rid, seq)
                lane = e.getLanes()[0]
                lpos, _ = lane.getClosestLanePosAndDist((x, y))
                t.vehicle.add(f"v{vid}", rid, typeID="tw",
                              departPos=str(max(min(lpos, e.getLength()-2), 1)),
                              departSpeed=str(min(smp.speed_kmh/3.6, 13)),
                              departLane="free")
                stats["placed"] += 1
            except Exception:
                stats["fail"] += 1
        for vid, s0 in init:
            place(vid, s0, 0.0)
        arrivals.sort(key=lambda p: p[1].t)
        ai = 0
        while t.simulation.getTime() < T1 - T0:
            t.simulationStep()
            now = t.simulation.getTime()
            while ai < len(arrivals) and arrivals[ai][1].t - T0 <= now:
                place(*arrivals[ai], now)
                ai += 1
        t.close()
        print("twin placement:", stats)
    twin = {}                    # int second -> [(lon,lat,speed)]
    for _, el in ET.iterparse(str(fcd)):
        if el.tag == "timestep":
            ts = float(el.get("time"))
            if 0 <= ts <= (T1 - T0) and abs(ts - round(ts)) < 0.01:
                twin[int(round(ts)) + int(T0)] = [
                    (float(v.get("x")), float(v.get("y")),
                     float(v.get("speed"))) for v in el]
            el.clear()

    real = {}
    for tr in parse(str(SP / "d8.csv"), hz=1.0):
        for s in tr.samples:
            if T0 <= s.t <= T1:
                real.setdefault(int(round(s.t)), []).append(
                    (s.lon, s.lat, s.speed_kmh / 3.6))

    def draw(ax, pts, title, n):
        for _, nds, _tags in ways:
            xs = [nodes[nd][1] for nd in nds]
            ys = [nodes[nd][0] for nd in nds]
            ax.plot(xs, ys, color="#cfcfcf", lw=0.7, zorder=1)
        if pts:
            xs, ys, sp = zip(*pts)
            ax.scatter(xs, ys, c=[min(v, 14) for v in sp], cmap="RdYlGn",
                       vmin=0, vmax=14, s=14, zorder=3)
        ax.set_title(f"{title}  ·  vehicles: {n}", fontsize=11)
        ax.set_xlim(23.7295, 23.7370)
        ax.set_ylim(37.9893, 37.9930)
        ax.set_aspect(1.27)
        ax.axis("off")

    import math
    frames = 0
    for i, ts in enumerate(range(int(T0) + 1, int(T1))):
        rp = real.get(ts, [])
        tp = twin.get(ts, [])
        fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5.4))
        draw(a1, rp, "REAL vehicles (drone-measured, pNEUMA)", len(rp))
        draw(a2, tp, "CALIBRATED TWIN (SUMO)", len(tp))
        fig.suptitle(f"Athens d8 · held-out minute · t={ts-int(T0)}s · "
                     "red=stopped green=moving — every left dot is a REAL car",
                     fontsize=12)
        plt.tight_layout()
        plt.savefig(OUT / f"f{i:04d}.png", dpi=110)
        plt.close(fig)
        frames += 1
    print("frames:", frames)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "8",
                    "-i", str(OUT / "f%04d.png"),
                    "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                    "-pix_fmt", "yuv420p",
                    str(REPO / "docs/media/real_vs_twin_athens.mp4")],
                   check=True)
    print("MOVIE:", REPO / "docs/media/real_vs_twin_athens.mp4")


if __name__ == "__main__":
    main()
