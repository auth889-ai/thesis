"""The five pre-registered candidate Dhaka regions (REGION_SELECTION.md).

Frozen before measurement; changing a bbox after seeing results would break the
measure-then-select rule.
"""
from __future__ import annotations

CANDIDATES: dict[str, dict] = {
    "R1": {
        "name": "Farmgate–Karwan Bazar–Bangla Motor–Shahbagh",
        "bbox": {"south": 23.723, "west": 90.372, "north": 23.762, "east": 90.408},
        "rationale": "CBD arterial spine (Kazi Nazrul Islam Ave); canonical "
                     "signalised junctions; Dhaka Medical/DU corridor; dense bus corridor",
    },
    "R2": {
        "name": "Gulshan 1–Gulshan 2–Banani",
        "bbox": {"south": 23.780, "west": 90.405, "north": 23.800, "east": 90.425},
        "rationale": "well-mapped grid, signalised circles, high route choice",
    },
    "R3": {
        "name": "Dhanmondi–Science Lab–New Market",
        "bbox": {"south": 23.730, "west": 90.375, "north": 23.752, "east": 90.392},
        "rationale": "dense intersection spacing on Mirpur Rd; retail/institutional demand",
    },
    "R4": {
        "name": "Mohakhali–Airport Road",
        "bbox": {"south": 23.775, "west": 90.395, "north": 23.830, "east": 90.425},
        "rationale": "high-speed arterial with BRT/expressway interaction",
    },
    "R5": {
        "name": "Motijheel–Gulistan",
        "bbox": {"south": 23.715, "west": 90.405, "north": 23.735, "east": 90.425},
        "rationale": "old CBD, extreme heterogeneity, bus terminals",
    },
}
