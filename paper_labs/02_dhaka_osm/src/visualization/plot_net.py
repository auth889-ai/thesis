"""Network figures from sumolib shapes (matplotlib; no GUI needed)."""
from __future__ import annotations

from pathlib import Path

CLASS_STYLE = {
    "highway.trunk": ("#c1121f", 1.8),
    "highway.primary": ("#d95f02", 1.5),
    "highway.secondary": ("#1b6ca8", 1.1),
    "highway.tertiary": ("#2a9d8f", 0.9),
    "highway.residential": ("#999999", 0.4),
}
DEFAULT_STYLE = ("#cccccc", 0.35)


def plot_network(net_file: Path, out_png: Path, title: str,
                 zoom_tls: int = 2) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import sumolib

    net = sumolib.net.readNet(str(net_file), withPrograms=True)
    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    figs = []

    fig, ax = plt.subplots(figsize=(11, 12))
    for e in net.getEdges():
        color, lw = CLASS_STYLE.get(e.getType(), DEFAULT_STYLE)
        xs, ys = zip(*e.getShape())
        ax.plot(xs, ys, color=color, lw=lw, solid_capstyle="round", zorder=1)
    tls_nodes = [n for n in net.getNodes() if n.getType() == "traffic_light"]
    if tls_nodes:
        tx, ty = zip(*[n.getCoord() for n in tls_nodes])
        ax.scatter(tx, ty, s=26, color="#e9c46a", edgecolor="black",
                   linewidth=0.5, zorder=3, label=f"signalized junctions ({len(tls_nodes)})")
        ax.legend(loc="lower right")
    ax.set(title=title, xlabel="x (m, UTM-projected)", ylabel="y (m)")
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(out_png, dpi=160)
    plt.close(fig)
    figs.append(str(out_png))

    for i, node in enumerate(tls_nodes[:zoom_tls]):
        x, y = node.getCoord()
        fig, ax = plt.subplots(figsize=(7, 7))
        for e in net.getEdges():
            xs, ys = zip(*e.getShape())
            if min(xs) > x + 400 or max(xs) < x - 400 or min(ys) > y + 400 or max(ys) < y - 400:
                continue
            color, lw = CLASS_STYLE.get(e.getType(), DEFAULT_STYLE)
            ax.plot(xs, ys, color=color, lw=lw * 2)
        ax.scatter([x], [y], s=120, color="#e9c46a", edgecolor="black", zorder=3)
        ax.set(title=f"Signalized junction zoom: {node.getID()} — {title}",
               xlim=(x - 350, x + 350), ylim=(y - 350, y + 350))
        ax.set_aspect("equal")
        p = out_png.parent / f"junction_zoom_{i}_{node.getID().replace('/', '_')[:40]}.png"
        fig.tight_layout()
        fig.savefig(p, dpi=160)
        plt.close(fig)
        figs.append(str(p))
    return figs
