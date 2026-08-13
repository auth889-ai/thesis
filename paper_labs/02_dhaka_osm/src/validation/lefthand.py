"""Left-hand traffic verification — Bangladesh drives on the LEFT.

Two independent checks, because a build flag alone is not evidence:

1. DECLARED   — the `lefthand` attribute netconvert writes into <net>.
2. GEOMETRIC  — measured from the built network, flag-independent:

   For a two-way street SUMO stores two opposite edges. Standing on one
   carriageway and looking along its travel direction, the *opposing*
   carriageway lies on your LEFT in right-hand traffic and on your RIGHT in
   left-hand traffic. With x east and y north, the sign of the 2-D cross
   product direction × offset is positive when the offset points left.

   left-hand traffic  <=>  cross < 0 for the majority of opposite edge pairs.

Both must agree, otherwise the network is rejected: a mirrored network produces
wrong turn connections and wrong right-of-way, which would silently invalidate
every later control experiment.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path


def declared_lefthand(net_file: Path) -> bool | None:
    """Read the `lefthand` attribute from the <net> root element."""
    root = ET.parse(net_file).getroot()
    value = root.get("lefthand")
    if value is None:
        return None
    return value.lower() in ("true", "1", "yes")


def _midpoint(shape):
    xs = [p[0] for p in shape]
    ys = [p[1] for p in shape]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def geometric_lefthand(net_file: Path, max_pairs: int = 400) -> dict:
    """Measure driving side from carriageway geometry alone."""
    import sumolib

    net = sumolib.net.readNet(str(net_file))
    left_votes = right_votes = skipped = 0
    examples: list[dict] = []

    for edge in net.getEdges():
        if len(examples) >= max_pairs and (left_votes + right_votes) >= max_pairs:
            break
        from_node, to_node = edge.getFromNode(), edge.getToNode()
        # find the opposite edge of the same street (to -> from)
        opposite = None
        for cand in to_node.getOutgoing():
            if cand.getToNode().getID() == from_node.getID():
                opposite = cand
                break
        if opposite is None:
            skipped += 1
            continue

        (ux, uy), (vx, vy) = from_node.getCoord(), to_node.getCoord()
        dx, dy = vx - ux, vy - uy
        norm = (dx * dx + dy * dy) ** 0.5
        if norm < 1.0:                       # ignore sub-metre stubs
            skipped += 1
            continue
        dx, dy = dx / norm, dy / norm

        ax, ay = _midpoint(edge.getShape())
        bx, by = _midpoint(opposite.getShape())
        ox, oy = bx - ax, by - ay
        if (ox * ox + oy * oy) ** 0.5 < 0.5:  # carriageways coincide -> no signal
            skipped += 1
            continue

        cross = dx * oy - dy * ox            # >0 : opposite carriageway on the LEFT
        if cross > 0:
            right_votes += 1                 # opposing traffic on my left => RHT
            side = "right_hand"
        else:
            left_votes += 1                  # opposing traffic on my right => LHT
            side = "left_hand"
        if len(examples) < 5:
            examples.append({"edge": edge.getID(), "opposite": opposite.getID(),
                             "cross": round(cross, 3), "implies": side})

    total = left_votes + right_votes
    return {
        "pairs_evaluated": total,
        "left_hand_votes": left_votes,
        "right_hand_votes": right_votes,
        "skipped": skipped,
        "left_hand_fraction": round(left_votes / total, 4) if total else None,
        "verdict": ("left_hand" if total and left_votes / total > 0.5
                    else "right_hand" if total else "undetermined"),
        "examples": examples,
    }


def verify_lefthand(net_file: Path, out_dir: Path, expected: str = "left_hand") -> dict:
    """Run both checks, require agreement, write the evidence."""
    declared = declared_lefthand(net_file)
    geometric = geometric_lefthand(net_file)
    declared_side = ("left_hand" if declared else
                     "right_hand" if declared is False else "not_declared")
    agree = declared_side == geometric["verdict"]
    report = {
        "expected": expected,
        "declared_attribute": declared,
        "declared_side": declared_side,
        "geometric": geometric,
        "checks_agree": agree,
        "passed": bool(agree and geometric["verdict"] == expected),
        "note": ("Bangladesh drives on the left; netconvert must be run with "
                 "--lefthand. The geometric test is independent of that flag."),
    }
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "lefthand_verification.json").write_text(json.dumps(report, indent=2))
    return report
