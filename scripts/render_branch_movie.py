#!/usr/bin/env python3
"""Render the SAME frozen t0 as two visible SUMO futures, side by side.

    python scripts/render_branch_movie.py --state artifacts/planner/planner_onset_s111213/state_t0.xml \
        --routes artifacts/gates/routes_repeat_1h.rou.xml.gz --scale 0.584 --seed 11

Left  = A0 do nothing.   Right = accepted candidate (Varaiya max-pressure).
Real cars, real positions, one frame per simulated second, zoomed on the
most-queued junction. Output: docs/media/onset_before_after.mp4
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
NET = str(REPO / "paper_labs/02_dhaka_osm/outputs/lab02_v2/network/dhaka_r1.net.xml")
HORIZON = 600
VIEW = "View #0"


def render(branch: str, state: str, routes: str, scale: float, seed: int,
           outdir: Path) -> tuple[Path, str]:
    import traci
    from research.control.signal_baselines import MaxPressureController
    frames = outdir / f"frames_{branch}"
    frames.mkdir(parents=True, exist_ok=True)
    traci.start(["sumo-gui", "-n", NET, "-r", routes, "--seed", str(seed),
                 "--scale", str(scale), "--no-step-log", "--no-warnings",
                 "--time-to-teleport", "600", "--start", "--quit-on-end",
                 "--window-size", "760,760", "--delay", "0",
                 "--gui-settings-file",
                 str(REPO / "configs/sumo_gui_demo.settings.xml")])
    traci.simulation.loadState(state)
    t0 = traci.simulation.getTime()
    ranked = []
    for tls in traci.trafficlight.getIDList():
        lanes = sorted({lk[0][0] for lk in
                        traci.trafficlight.getControlledLinks(tls) if lk})
        q = sum(traci.lane.getLastStepHaltingNumber(l) for l in lanes)
        ranked.append((q, tls, lanes))
    ranked.sort(reverse=True)
    _, target, tls_lanes = ranked[0]
    x, y = traci.junction.getPosition(target)
    traci.gui.setOffset(VIEW, x, y)
    traci.gui.setZoom(VIEW, 1500)
    try:
        traci.gui.setSchema(VIEW, "real world")
    except Exception:                              # noqa: BLE001
        pass
    import traci.constants as tc
    ctrl = None
    if branch == "control":
        ctrl = MaxPressureController(traci, [target])
        ctrl.tls[target]["since"] = t0
    qseries, last_col = [], {}
    RED, ORA, GRN = (230, 60, 40, 255), (235, 160, 40, 255), (90, 200, 90, 255)
    for v in traci.vehicle.getIDList():          # batch speed reads
        traci.vehicle.subscribe(v, [tc.VAR_SPEED])
    while traci.simulation.getTime() < t0 + HORIZON and \
            traci.simulation.getMinExpectedNumber() > 0:
        traci.simulationStep()
        now = traci.simulation.getTime()
        if ctrl:
            ctrl.step(now)
        i = int(now - t0)
        for v in traci.simulation.getDepartedIDList():
            traci.vehicle.subscribe(v, [tc.VAR_SPEED])
        subs = traci.vehicle.getAllSubscriptionResults()
        n_stop = 0
        # visible truth: standing = red, crawling = orange, moving = green
        for v, d in subs.items():
            sp = d.get(tc.VAR_SPEED, 10.0)
            if sp < 0.5:
                n_stop += 1
            col = RED if sp < 0.5 else (ORA if sp < 3.0 else GRN)
            if last_col.get(v) != col:
                traci.vehicle.setColor(v, col)
                last_col[v] = col
        qseries.append(n_stop)
        traci.gui.screenshot(VIEW, str(frames / f"f{i:04d}.png"))
    traci.close()
    return frames, target, qseries


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True)
    ap.add_argument("--routes", required=True)
    ap.add_argument("--scale", type=float, default=0.584)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--out", default=str(REPO / "docs/media/onset_before_after.mp4"))
    a = ap.parse_args()
    outdir = REPO / "artifacts" / "branch_movie"
    fa, tls, qa = render("no_action", a.state, a.routes, a.scale, a.seed, outdir)
    fb, _, qb = render("control", a.state, a.routes, a.scale, a.seed, outdir)
    print(f"target TLS {tls} · final queue no-action {qa[-1]} vs control {qb[-1]}")
    (outdir / "queues.txt").write_text(
        f"no_action={qa}\ncontrol={qb}\n")
    from PIL import Image, ImageDraw, ImageFont
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 26)
        fbig = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 40)
    except Exception:                              # noqa: BLE001
        font = fbig = ImageFont.load_default()
    for d, lab, col, series in ((fa, "DO NOTHING", (224, 113, 90), qa),
                                (fb, "DHAKAFLOW ACTS", (79, 174, 127), qb)):
        for f in sorted(d.glob("f*.png")):
            i = int(f.stem[1:]) - 1
            im = Image.open(f).convert("RGB")
            dr = ImageDraw.Draw(im)
            dr.rectangle([0, 0, im.width, 92], fill=(14, 20, 23))
            dr.text((14, 6), lab, fill=col, font=font)
            n = series[min(i, len(series) - 1)]
            dr.text((14, 40), f"STOPPED VEHICLES: {n}", fill=col, font=fbig)
            dr.text((im.width - 130, 10), f"+{i//60}:{i%60:02d} min",
                    fill=(200, 200, 200), font=font)
            im.save(f)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "12",
                        "-start_number", "1", "-i", str(d / "f%04d.png"),
                        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                        "-pix_fmt", "yuv420p", str(d) + ".mp4"], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                    "-i", str(fa) + ".mp4", "-i", str(fb) + ".mp4",
                    "-filter_complex", "hstack", "-pix_fmt", "yuv420p",
                    a.out], check=True)
    print("MOVIE:", a.out)


if __name__ == "__main__":
    main()
