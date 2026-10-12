"""City profile — the platform is city-agnostic; Dhaka is one instance of it.

Nothing downstream may hardcode "Dhaka". A city is: a verified network file, the
side of the road its traffic drives on, a fleet composition, and provenance. Any
city with an OSM extract can be onboarded by adding a profile — the perception,
forecasting, control and routing stacks are unchanged.

Dhaka R1 is the *reference* profile because it is the one we froze and verified
(Lab 02), not because the code is specific to it.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Mapping, Sequence

from core.common.types import VehicleClass


class TrafficSide(str, Enum):
    LEFT = "left_hand"      # Bangladesh, UK, India, Japan …
    RIGHT = "right_hand"    # USA, most of Europe …


@dataclass(frozen=True)
class CityProfile:
    """Everything city-specific, in one place.

    `network_sha256` is not decoration: every result this platform reports names
    the exact network it was produced on. A silently swapped network is the
    easiest way to make an unreproducible claim.
    """

    city_id: str
    display_name: str
    country: str
    network_path: Path
    traffic_side: TrafficSide
    network_sha256: str = ""
    timezone: str = "UTC"
    fleet_classes: Sequence[VehicleClass] = ()
    signal_timing_provenance: str = "UNKNOWN"
    demand_provenance: str = "UNKNOWN"
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.city_id:
            raise ValueError("city_id is required")
        if self.signal_timing_provenance == "UNKNOWN":
            raise ValueError(
                f"{self.city_id}: signal_timing_provenance must be stated explicitly "
                "(e.g. IMPORTED_HEURISTIC, FIELD_OBSERVED, AUTHORITY_SUPPLIED) — "
                "an unlabelled timing source becomes a false realism claim")

    def verify_network(self) -> tuple[bool, str]:
        """Check the network file against its recorded checksum.

        Returns (ok, actual_sha256). No checksum recorded ⇒ (False, actual), so
        the caller must decide consciously rather than silently trusting a file.
        """
        if not self.network_path.exists():
            return False, ""
        h = hashlib.sha256()
        with open(self.network_path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        actual = h.hexdigest()
        return (actual == self.network_sha256 and bool(self.network_sha256)), actual

    @property
    def is_left_hand(self) -> bool:
        return self.traffic_side is TrafficSide.LEFT


# ---------------------------------------------------------------------------
# Reference profile: the frozen Lab 02 Dhaka R1 network.
# ---------------------------------------------------------------------------

from core.common.paths import REPO as _REPO_ROOT

DHAKA_R1 = CityProfile(
    city_id="dhaka_r1",
    display_name="Dhaka — Farmgate · Karwan Bazar · Bangla Motor · Shahbagh",
    country="Bangladesh",
    network_path=(_REPO_ROOT / "paper_labs" / "02_dhaka_osm" / "outputs"
                  / "lab02_v2" / "network" / "dhaka_r1.net.xml"),
    traffic_side=TrafficSide.LEFT,     # MEASURED: 98.9% of 5250 carriageway pairs
    network_sha256="06194df039740fa2ceb0bcb2c438444efd755f26e0f863327f0e1d6524775dcb",
    timezone="Asia/Dhaka",
    fleet_classes=(
        VehicleClass.CAR, VehicleClass.BUS, VehicleClass.TRUCK,
        VehicleClass.MOTORCYCLE, VehicleClass.CNG_AUTORICKSHAW,
        VehicleClass.RICKSHAW, VehicleClass.BICYCLE, VehicleClass.PEDESTRIAN,
    ),
    signal_timing_provenance="IMPORTED_HEURISTIC",   # netconvert-synthesised, NOT real DMP plans
    demand_provenance="SYNTHETIC_VALIDATION_DEMAND",
    metadata={
        "frozen_lab": "02_dhaka_osm",
        "freeze_commits": "6936ea9,c852e64",
        "edges": "6527", "lanes": "7865", "junctions": "2956", "tls_programs": "17",
    },
)

REGISTRY: dict[str, CityProfile] = {DHAKA_R1.city_id: DHAKA_R1}


def get_city(city_id: str) -> CityProfile:
    try:
        return REGISTRY[city_id]
    except KeyError as exc:
        raise KeyError(
            f"unknown city {city_id!r}; registered: {sorted(REGISTRY)}. "
            "Add a CityProfile — no downstream module needs changing.") from exc


def register_city(profile: CityProfile) -> None:
    REGISTRY[profile.city_id] = profile
