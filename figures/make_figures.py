"""Data figures for the forecast-routing talk and report, read only from saved runs and files.

    python figures/make_figures.py            # fig01, fig04, fig05, fig11, fig12
    python figures/make_figures.py fig05      # one figure

Every number drawn is read from the file named in figures/README.md; the script stops if a number
differs from the value the owner listed (fig04, fig11).
"""
from __future__ import annotations

import csv
import io
import json
import math
import sys
import urllib.request
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "figures"
sys.path.insert(0, str(REPO))

FONT = "DejaVu Sans"
plt.rcParams.update({"font.family": FONT, "font.size": 20, "axes.titlesize": 24, "axes.labelsize": 21,
                     "xtick.labelsize": 18, "ytick.labelsize": 18, "legend.fontsize": 18,
                     "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white"})
W, H, DPI = 16, 9, 100          # 1600 x 900 px

BLUE, ORANGE, GREY, GREEN, RED = "#1f77b4", "#ff7f0e", "#8c8c8c", "#2ca02c", "#d62728"

VERIFY = REPO / "results/forecasting/verify_GWNet_METR-LA_207.json"
MAPPING = REPO / "results/routing/coverage_rescue/la_c4_central_wide/sensor_to_edge_207.json"
LOCATIONS = Path.home() / ".dhakaflow/upstream/DCRNN/data/sensor_graph/graph_sensor_locations.csv"
RUN20 = REPO / "evidence/veins_forecast_routing/20261012T142239Z"
RUN60 = REPO / "evidence/veins_forecast_routing/20261012T143208Z"


def save(fig, name):
    fig.savefig(OUT / name, dpi=DPI)
    plt.close(fig)
    print("wrote", OUT / name)


def check(label, got, expected, nd):
    if round(got, nd) != expected:
        raise SystemExit(f"STOP: {label} is {got} in the file, the owner listed {expected}")


# ---------------------------------------------------------------- fig01: sensors on the map
def _tiles(lat0, lat1, lon0, lon1, z):
    """OpenStreetMap standard tiles for the box, as one image plus its lon/lat extent."""
    from PIL import Image

    def xy(lat, lon):
        n = 2 ** z
        x = (lon + 180) / 360 * n
        y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
        return x, y

    def lonlat(x, y):
        n = 2 ** z
        return x / n * 360 - 180, math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))

    x0, y0 = xy(lat1, lon0); x1, y1 = xy(lat0, lon1)
    tx0, ty0, tx1, ty1 = int(x0), int(y0), int(x1), int(y1)
    img = Image.new("RGB", ((tx1 - tx0 + 1) * 256, (ty1 - ty0 + 1) * 256))
    for tx in range(tx0, tx1 + 1):
        for ty in range(ty0, ty1 + 1):
            url = f"https://tile.openstreetmap.org/{z}/{tx}/{ty}.png"
            req = urllib.request.Request(url, headers={"User-Agent": "DhakaFlow-thesis-figure/1.0 (IUT undergraduate thesis figure)"})
            img.paste(Image.open(io.BytesIO(urllib.request.urlopen(req, timeout=30).read())).convert("RGB"),
                      ((tx - tx0) * 256, (ty - ty0) * 256))
    w_lon, n_lat = lonlat(tx0, ty0); e_lon, s_lat = lonlat(tx1 + 1, ty1 + 1)
    return img, (w_lon, e_lon, s_lat, n_lat)


def fig01():
    rows = list(csv.DictReader(open(LOCATIONS)))
    mp = json.loads(MAPPING.read_text())
    good = {r["sensor_id"] for r in mp["records"] if r["quality"] == "GOOD"}
    check("sensors in the location file", len(rows), 207, 0)
    check("sensors mapped to SUMO roads", len(good), 83, 0)
    lat = np.array([float(r["latitude"]) for r in rows]); lon = np.array([float(r["longitude"]) for r in rows])
    ok = np.array([r["sensor_id"] in good for r in rows])
    pad = 0.02
    lat0, lat1, lon0, lon1 = lat.min() - pad, lat.max() + pad, lon.min() - pad, lon.max() + pad
    img, ext = _tiles(lat0, lat1, lon0, lon1, 12)
    fig, ax = plt.subplots(figsize=(W, H), dpi=DPI)
    from PIL import ImageEnhance
    img = ImageEnhance.Color(img).enhance(0.35)          # muted map so the sensors stand out
    ax.imshow(img, extent=ext, aspect=1 / math.cos(math.radians(lat.mean())), interpolation="lanczos")
    s0, w0, s1, w1 = mp["bbox"]
    ax.add_patch(plt.Rectangle((w0, s0), w1 - w0, s1 - s0, fill=False, lw=3, ls="--", color="black"))
    ax.text(w0, s1 + 0.004, "simulated SUMO area", fontsize=18, va="bottom")
    ax.scatter(lon[~ok], lat[~ok], s=70, c=GREY, edgecolors="white", linewidths=0.8, label=f"other sensors ({(~ok).sum()})", zorder=3)
    ax.scatter(lon[ok], lat[ok], s=110, c=RED, edgecolors="white", linewidths=1.0, label=f"mapped to a SUMO road ({ok.sum()})", zorder=4)
    ax.set_xlim(lon0, lon1); ax.set_ylim(lat0, lat1)
    ax.set_xlabel("longitude"); ax.set_ylabel("latitude")
    ax.set_title(f"METR-LA: {len(rows)} road sensors in Los Angeles; {ok.sum()} lie on roads of the simulated map")
    ax.legend(loc="lower left", framealpha=0.95)
    ax.text(1.0, -0.085, "Map: © OpenStreetMap contributors", transform=ax.transAxes, ha="right", fontsize=13, color="#555")
    fig.tight_layout()
    save(fig, "fig01_sensors_map.png")


# ---------------------------------------------------------------- fig04: MAE per horizon
def fig04():
    v = json.loads(VERIFY.read_text())
    hz = ["+15", "+30", "+60"]
    ours = [v["held_out"][h]["MAE"] for h in hz]
    pers = [v["held_out"][h]["persistence_MAE"] for h in hz]
    paper = [v["published_GWNet_METR-LA"][h] for h in hz]
    for h, a, b, c, ea, eb, ec in zip(hz, ours, pers, paper, (2.71, 3.10, 3.56), (4.02, 5.10, 6.80), (2.69, 3.07, 3.53)):
        check(f"my model MAE {h}", a, ea, 2); check(f"no-change MAE {h}", b, eb, 2); check(f"paper MAE {h}", c, ec, 2)
    fig, ax = plt.subplots(figsize=(W, H), dpi=DPI)
    x = np.arange(3); w = 0.26
    for i, (vals, lab, col) in enumerate([(pers, "no change (last reading holds)", GREY),
                                          (ours, "my Graph WaveNet", BLUE),
                                          (paper, "Graph WaveNet paper (Wu et al. 2019)", ORANGE)]):
        bars = ax.bar(x + (i - 1) * w, vals, w, label=lab, color=col)
        for b, val in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, val + 0.08, f"{val:.2f}", ha="center", va="bottom", fontsize=19)
    ax.set_xticks(x, ["15 min", "30 min", "60 min"]); ax.set_xlabel("forecast horizon")
    ax.set_ylabel("mean absolute error (mph)"); ax.set_ylim(0, max(pers) * 1.18)
    ax.set_title("Forecast error on the held-out METR-LA test set (lower is better)")
    ax.legend(loc="upper left", frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    save(fig, "fig04_mae_bar.png")


# ---------------------------------------------------------------- fig05: forecast vs real, 3 sensors
FIG05_SENSORS = ["717458", "717468", "717461"]      # the three sensors of the report's run figure (Figure 6.1)


def fig05():
    from core.ml.forecasting import ForecastService
    from core.ml.forecasting.training import train_eval as te
    from core.ml.forecasting.routing_forecast import moment_for
    svc = ForecastService.metr_la_gwnet()
    vals = svc.values; T = vals.shape[0]; lo = te.splits(T)["test"][0]
    as_of = moment_for("peak", 0, T, lo)            # first weekday 17:30 inside the held-out split
    out = svc.predict(as_of)
    pred = np.asarray(out["prediction"])             # (12, 207) mph, steps +5 .. +60 min
    ids = [r["sensor_id"] for r in csv.DictReader(open(LOCATIONS))]
    from datetime import datetime, timedelta
    when = datetime(2012, 3, 1) + timedelta(minutes=5 * as_of)
    fig, axes = plt.subplots(1, 3, figsize=(W, H), dpi=DPI, sharey=True)
    past_t = np.arange(-55, 1, 5); fut_t = np.arange(5, 61, 5)
    for ax, sid in zip(axes, FIG05_SENSORS):
        j = ids.index(sid)
        past = vals[as_of - 12:as_of, j]; fut = vals[as_of:as_of + 12, j]
        m = lambda a: np.where(a > 0, a, np.nan)     # 0 = missing reading in METR-LA
        ax.plot(past_t, m(past), color="black", lw=3, marker="o", ms=6, label="real speed, last hour")
        ax.plot(fut_t, m(fut), color=GREEN, lw=3, marker="o", ms=6, label="real speed, next hour")
        ax.plot(fut_t, pred[:, j], color=BLUE, lw=3, ls="--", marker="s", ms=6, label="my forecast")
        ok = fut > 0
        mae = float(np.mean(np.abs(pred[ok, j] - fut[ok]))) if ok.any() else float("nan")
        ax.axvline(0, color=GREY, lw=1.5)
        ax.set_title(f"sensor {sid}\nerror over the hour {mae:.1f} mph", fontsize=20)
        ax.set_xlabel("minutes from now"); ax.grid(alpha=0.3)
        ax.set_xticks([-60, -30, 0, 30, 60])
    axes[0].set_ylabel("speed (mph)")
    axes[0].set_ylim(0, max(75, float(np.nanmax(vals[as_of - 12:as_of + 12, [ids.index(s) for s in FIG05_SENSORS]])) + 5))
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=3, frameon=False)
    fig.suptitle(f"Held-out test data, {when:%a %d %b %Y %H:%M} (METR-LA index {as_of}): forecast against what the sensors recorded", fontsize=18)
    fig.tight_layout(rect=(0, 0.08, 1, 0.97))
    save(fig, "fig05_forecast_vs_real.png")
    print(f"fig05 as_of={as_of} checkpoint={svc.card.get('checkpoint_sha256', '') if isinstance(svc.card, dict) else ''}")


# ---------------------------------------------------------------- fig11: advice funnel
def fig11():
    keys = [("advice_decided", "decided by\nthe server"), ("handed_to_rsu", "handed to a\nroadside unit"),
            ("received_by_car", "received by\nthe car"), ("applied", "route\nchanged")]
    data = {}
    for name, run, expect in [("20 RSUs", RUN20, (123, 14, 7, 6)), ("60 RSUs", RUN60, (183, 23, 19, 15))]:
        s = json.loads((run / "summary.json").read_text())
        check(f"{name} roadside units", len(s["rsus"]), int(name.split()[0]), 0)
        d = s["arms"]["predictive_corrected_v2x"]["network"]["downlink"]
        data[name] = [d[k] for k, _ in keys]
        for (k, _), got, e in zip(keys, data[name], expect):
            check(f"{name} {k}", got, e, 0)
    fig, ax = plt.subplots(figsize=(W, H), dpi=DPI)
    x = np.arange(len(keys)); w = 0.38
    for i, (name, col) in enumerate([("20 RSUs", BLUE), ("60 RSUs", ORANGE)]):
        bars = ax.bar(x + (i - 0.5) * w, data[name], w, label=f"{name.split()[0]} roadside units", color=col)
        for b, val in zip(bars, data[name]):
            ax.text(b.get_x() + b.get_width() / 2, val + 2, str(val), ha="center", va="bottom", fontsize=21)
    ax.set_xticks(x, [k[1] for k in keys]); ax.set_ylabel("advice messages")
    ax.set_ylim(0, max(data["60 RSUs"]) * 1.15)
    ax.set_title("What happens to route advice over IEEE 802.11p (Veins, seed 201, 15 min)")
    ax.legend(frameon=False); ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    save(fig, "fig11_funnel.png")


# ---------------------------------------------------------------- fig12: vehicle-hours
def fig12():
    from core.simulation.twin.runtime import parse_metrics
    rows = []
    for name, run in [("20 RSUs", RUN20), ("60 RSUs", RUN60)]:
        s = json.loads((run / "summary.json").read_text())
        horizon = s["warm_up_s"] + 60 * s["minutes_after_warm_up"]
        vh = {}
        for arm in ("baseline", "predictive_corrected_v2x"):
            got = parse_metrics(run / "s201" / arm, horizon)["total_vehicle_hours"]      # from tripinfo.xml
            saved = s["arms"][arm]["metrics"]["total_vehicle_hours"]
            if abs(got - saved) > 1e-6:
                raise SystemExit(f"STOP: {name} {arm}: tripinfo gives {got}, summary.json says {saved}")
            vh[arm] = got
        rows.append((name, vh["baseline"], vh["predictive_corrected_v2x"]))
    fig, ax = plt.subplots(figsize=(W, H), dpi=DPI)
    x = np.arange(len(rows)); w = 0.36
    for i, (lab, col, idx) in enumerate([("baseline: nobody reroutes", GREY, 1), ("forecast routing", BLUE, 2)]):
        vals = [r[idx] for r in rows]
        bars = ax.bar(x + (i - 0.5) * w, vals, w, label=lab, color=col)
        for b, val in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, val + 15, f"{val:.1f}", ha="center", va="bottom", fontsize=21)
    ax.set_xticks(x, [f"Veins 802.11p, {r[0].split()[0]} roadside units" for r in rows])
    ax.set_ylabel("total vehicle-hours (all vehicles)"); ax.set_ylim(0, max(r[2] for r in rows) * 1.25)
    ax.set_title("Total travel time of the city, same seed and cars\n(seed 201, 1 200 s warm-up + 15 min)", fontsize=22)
    ax.legend(loc="upper center", ncol=2, frameon=False); ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    save(fig, "fig12_vehh.png")


# ---------------------------------------------------------------- fig06 / fig08 / fig09: the seed-6593 demo run
DEMO = REPO / "evidence/veins_forecast_routing/20261014T113750Z"
CAP = DEMO / "figure_capture"


def _shot(src: Path, name: str):
    """A window capture of the real run, scaled to at most 1600 px wide; pixels are not edited."""
    from PIL import Image
    im = Image.open(src).convert("RGB")
    if im.width > 1600:
        im = im.resize((1600, round(im.height * 1600 / im.width)), Image.LANCZOS)
    im.save(OUT / name, optimize=True)
    print("wrote", OUT / name)


def fig06():
    _shot(CAP / "sumo_t222_car_enters.png", "fig06_sumo_window.png")


def fig08():
    _shot(CAP / "sumo_t242_route_changed.png", "fig08_car_reroute.png")


def fig09():
    import re
    import textwrap
    log = (CAP / "terminal.log") if (CAP / "terminal.log").exists() else (CAP / "terminal_partial.log")
    txt = log.read_text(errors="ignore")
    events = re.findall(r"\[(\d+) \| ([^\]]+)\] (t=\d+s)\s+(.*?)(?=\s+\(Enter = next step\)|\n|$)", txt)
    events = [e for e in events if int(e[0]) <= 11]          # the car's story up to the route change
    if not events:
        raise SystemExit(f"STOP: no explain lines in {log}")
    lines = []
    for n, where, t, what in events:
        lines.append((f"[{n}] {t}  {where}", "src"))
        for w in textwrap.wrap(what, 118):
            lines.append(("     " + w, "txt"))
    h = 0.29 * len(lines) + 1.4
    fig = plt.figure(figsize=(W, h), dpi=DPI)
    fig.text(0.01, 1 - 0.45 / h, "make veins-forecast-routing SEED=6593 ARGS=\"--minutes 8 --arms predictive_corrected_v2x --demo-early --explain veh0_444 --step-through\"",
             family="DejaVu Sans Mono", fontsize=12.5, color="#555", va="top")
    y = 1 - 0.95 / h
    for s, kind in lines:
        fig.text(0.01, y, s, family="DejaVu Sans Mono", fontsize=12.5, va="top",
                 color=BLUE if kind == "src" else "black", weight="bold" if kind == "src" else "normal")
        y -= 0.29 / h
    fig.savefig(OUT / "fig09_explain_terminal.png", dpi=DPI)
    plt.close(fig)
    print("wrote", OUT / "fig09_explain_terminal.png", f"({len(events)} events from {log.relative_to(REPO)})")


def fig07():
    _shot(CAP / "qtenv_t236_after_rsu7_decode.png", "fig07_omnet_window.png")


# ---------------------------------------------------------------- fig02: the paper's own architecture figure
GWNET_REPO = Path.home() / ".dhakaflow/upstream/Graph-WaveNet"     # nnzhan/Graph-WaveNet @ 6b162e80, MIT


def fig02():
    """fig/model.png from the authors' repository, placed unchanged on a white 16:9 canvas with its source."""
    from PIL import Image
    im = Image.open(GWNET_REPO / "fig/model.png").convert("RGB")
    fig = plt.figure(figsize=(im.width / DPI, im.height / DPI + 1.0), dpi=DPI)
    ax = fig.add_axes((0, 1.0 / (im.height / DPI + 1.0), 1, im.height / DPI / (im.height / DPI + 1.0))); ax.imshow(im); ax.axis("off")
    fig.text(0.5, 0.45 / (im.height / DPI + 1.0), "Source: Wu et al., IJCAI 2019\nfigure from github.com/nnzhan/Graph-WaveNet (MIT)",
             ha="center", va="center", fontsize=20)
    save(fig, "fig02_gwnet_architecture.png")


# ---------------------------------------------------------------- fig03: how METR-LA is split (no training log exists)
def fig03():
    from datetime import datetime, timedelta
    from core.ml.forecasting import ForecastService
    from core.ml.forecasting.training import train_eval as te
    T = ForecastService.metr_la_gwnet().values.shape[0]
    check("METR-LA time steps", T, 34272, 0)
    sp = te.splits(T)
    day = lambda i: datetime(2012, 3, 1) + timedelta(minutes=5 * i)
    fig, ax = plt.subplots(figsize=(W, 6), dpi=DPI)
    for (name, (lo, hi)), c in zip(sp.items(), [BLUE, ORANGE, GREEN]):
        ax.barh(0, hi - lo, left=lo, color=c, height=0.6)
        ax.text((lo + hi) / 2, 0, f"{name}\n{hi - lo:,}\nsteps\n{day(lo):%d %b} –\n{day(hi - 1):%d %b}",
                ha="center", va="center", color="white", fontsize=17, fontweight="bold")
    ax.set_xlim(0, T); ax.set_yticks([])
    ax.set_xlabel("5-minute time step (METR-LA, 1 Mar – 27 Jun 2012)")
    ax.set_title(f"METR-LA split in time order, 70 / 10 / 20 ({T:,} steps, 207 sensors): the test part is never seen in training")
    ax.title.set_fontsize(19)
    ax.spines[["top", "right", "left"]].set_visible(False)
    fig.tight_layout()
    save(fig, "fig03_data_split.png")
    print("fig03 splits", sp)


FIGS = {"fig01": fig01, "fig02": fig02, "fig03": fig03, "fig07": fig07, "fig04": fig04, "fig05": fig05, "fig06": fig06, "fig08": fig08, "fig09": fig09, "fig11": fig11, "fig12": fig12}

if __name__ == "__main__":
    for k in (sys.argv[1:] or FIGS):
        FIGS[k]()
