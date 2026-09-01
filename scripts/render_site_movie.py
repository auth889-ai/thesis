#!/usr/bin/env python3
"""Site X movie: A0 vs metering from the validated t0 — honest two counters."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
NET = str(REPO / "artifacts/site_i70/i70_pena.net.xml")
STATE = str(REPO / "artifacts/site_i70/twin/state_t0_site.xml")
HORIZON = 300
VIEW = "View #0"


def render(branch, cam, vsp, period, outdir):
    import traci
    sm = cam["site_model"]
    entry, eb, exit_e = sm["edge_entry"], sm["edge_camera"], sm["edge_exit"]
    frames = outdir / f"frames_{branch}"
    frames.mkdir(parents=True, exist_ok=True)
    traci.start(["sumo-gui", "-n", NET, "--seed", "11", "--no-step-log",
                 "--no-warnings", "--start", "--quit-on-end",
                 "--window-size", "760,560", "--delay", "0",
                 "--gui-settings-file",
                 str(REPO / "configs/sumo_gui_demo.settings.xml")])
    traci.simulation.loadState(STATE)
    t0 = traci.simulation.getTime()
    if vsp and vsp < 12.0:
        traci.edge.setMaxSpeed(exit_e, max(vsp, 2.0))
    # camera viewpoint: middle of the camera edge
    shape = traci.lane.getShape(f"{eb}_0")
    xm, ym = shape[len(shape)//2]
    traci.gui.setOffset(VIEW, xm, ym)
    traci.gui.setZoom(VIEW, 2600)
    gate = branch == "metering"
    sched = [t0 + i * period for i in range(int(HORIZON / period) + 2)]
    rel, prev = [], t0 - period
    for st_i in sched:
        hw = (period * 2.0 if gate and (st_i - t0) < 120.0
              else (period * 0.7 if gate else period))
        r = max(st_i, prev + hw)
        rel.append(r); prev = r
    qi, nid = 0, 90000
    delay = hold = 0.0
    series = []
    RED, ORA, GRN = (230,60,40,255), (235,160,40,255), (90,200,90,255)
    last_col = {}
    while traci.simulation.getTime() < t0 + HORIZON:
        traci.simulationStep()
        now = traci.simulation.getTime()
        while qi < len(rel) and rel[qi] <= now:
            try:
                traci.vehicle.add(f"c{nid}", "eb", typeID="site_veh",
                                  departSpeed="max", departLane="free")
                nid += 1
            except Exception:
                pass
            hold += max(0.0, now - sched[qi])
            qi += 1
        for v in traci.vehicle.getIDList():
            sp = traci.vehicle.getSpeed(v)
            col = RED if sp < 3 else (ORA if sp < 8 else GRN)
            if last_col.get(v) != col:
                traci.vehicle.setColor(v, col); last_col[v] = col
        for v in traci.edge.getLastStepVehicleIDs(eb):
            if traci.vehicle.getLanePosition(v) <= 150:
                delay += max(0.0, 1 - traci.vehicle.getSpeed(v)/25.0)
        i = int(now - t0)
        series.append((round(delay), round(hold)))
        traci.gui.screenshot(VIEW, str(frames / f"f{i:04d}.png"))
    traci.close()
    return frames, series


def main():
    cam = json.loads((REPO / "configs/cameras/registry.json").read_text()
                     )["cameras"]["070E28355CAM1RP2"]
    twin = json.loads((REPO / "artifacts/gates/REAL_SITE_TWIN_PASS.json").read_text())
    st = json.loads((REPO / "artifacts/site_i70/perception/traffic_state.json").read_text())
    vsp = twin["observed_A"]["speed_m_s"]
    period = len(st["windows"]) * 5.0 / max(len(st["events"]["discharge"]), 1)
    out = REPO / "artifacts/site_i70/movie"
    fa, sa = render("nothing", cam, vsp, period, out)
    fb, sb = render("metering", cam, vsp, period, out)
    from PIL import Image, ImageDraw, ImageFont
    try:
        f24 = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
        f30 = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 32)
    except Exception:
        f24 = f30 = ImageFont.load_default()
    for d, lab, col, ser in ((fa, "DO NOTHING", (224,113,90), sa),
                             (fb, "UPSTREAM METERING (rejected by guard)",
                              (217,162,58), sb)):
        for f in sorted(d.glob("f*.png")):
            i = min(int(f.stem[1:]), len(ser)-1)
            im = Image.open(f).convert("RGB"); dr = ImageDraw.Draw(im)
            dr.rectangle([0,0,im.width,96], fill=(14,20,23))
            dr.text((12,4), lab, fill=col, font=f24)
            dr.text((12,34), f"DELAY IN VIEW: {ser[i][0]} veh-s",
                    fill=(232,237,235), font=f30)
            dr.text((12,66), f"HELD UPSTREAM: {ser[i][1]} veh-s",
                    fill=(224,113,90) if ser[i][1] else (139,151,157), font=f24)
            im.save(f)
        subprocess.run(["ffmpeg","-y","-loglevel","error","-framerate","12",
                        "-start_number","0","-i",str(d/"f%04d.png"),
                        "-vf","scale=trunc(iw/2)*2:trunc(ih/2)*2",
                        "-pix_fmt","yuv420p",str(d)+".mp4"], check=True)
    subprocess.run(["ffmpeg","-y","-loglevel","error",
                    "-i",str(fa)+".mp4","-i",str(fb)+".mp4",
                    "-filter_complex","hstack","-pix_fmt","yuv420p",
                    str(REPO/"docs/media/site_before_after.mp4")], check=True)
    print("MOVIE:", REPO/"docs/media/site_before_after.mp4")


if __name__ == "__main__":
    main()
