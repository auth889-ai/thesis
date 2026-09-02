"""The Dhaka corridors the live system monitors.

Ten major arteries, each an origin/destination pair of real coordinates on the Dhaka road network.
They were chosen to cover the corridors that actually carry the city's peak load rather than to
make a tidy map: the Airport Road spine north to Uttara, the Mirpur and Gulshan approaches, the
Motijheel/Gulistan commercial core, and the Farmgate-Shahbagh axis the rest of this project's SUMO
work already models.

The first six are the pairs the long-running recorder has been sampling since the start of the
project, kept identical (same ids, same coordinates) so live readings and recorded history line up.
The four added here extend coverage north and east.

`sumo_mapped` marks the corridors that exist in the frozen Dhaka R1 SUMO network, and therefore the
ones a counterfactual simulation can actually be run on. The others are live-only: the interface
must not offer a simulation it cannot honestly run.
"""
from __future__ import annotations

# lat, lng
PLACES = {
    "farmgate":      (23.7573, 90.3854),
    "shahbagh":      (23.7389, 90.3958),
    "karwanbazar":   (23.7508, 90.3928),
    "banglamotor":   (23.7457, 90.3941),
    "mohakhali":     (23.7806, 90.4054),
    "gulshan1":      (23.7805, 90.4148),
    "banani":        (23.7936, 90.4066),
    "airport":       (23.8433, 90.3978),
    "uttara":        (23.8687, 90.3993),
    "mirpur10":      (23.8069, 90.3687),
    "agargaon":      (23.7780, 90.3792),
    "motijheel":     (23.7330, 90.4172),
    "gulistan":      (23.7261, 90.4103),
    "jatrabari":     (23.7104, 90.4348),
    "science_lab":   (23.7385, 90.3840),
    "dhanmondi27":   (23.7540, 90.3730),
}

CORRIDORS: tuple[dict, ...] = (
    # --- the six the recorder has been sampling all along (ids and coordinates unchanged) ---
    {"id": "farmgate_to_shahbagh", "name": "Farmgate → Shahbagh",
     "road": "Kazi Nazrul Islam Ave", "origin": "farmgate", "dest": "shahbagh", "sumo_mapped": True},
    {"id": "shahbagh_to_farmgate", "name": "Shahbagh → Farmgate",
     "road": "Kazi Nazrul Islam Ave", "origin": "shahbagh", "dest": "farmgate", "sumo_mapped": True},
    {"id": "karwanbazar_to_banglamotor", "name": "Karwan Bazar → Banglamotor",
     "road": "Kazi Nazrul Islam Ave", "origin": "karwanbazar", "dest": "banglamotor", "sumo_mapped": True},
    {"id": "banglamotor_to_karwanbazar", "name": "Banglamotor → Karwan Bazar",
     "road": "Kazi Nazrul Islam Ave", "origin": "banglamotor", "dest": "karwanbazar", "sumo_mapped": True},
    {"id": "farmgate_to_banglamotor", "name": "Farmgate → Banglamotor",
     "road": "Kazi Nazrul Islam Ave", "origin": "farmgate", "dest": "banglamotor", "sumo_mapped": True},
    {"id": "karwanbazar_to_shahbagh", "name": "Karwan Bazar → Shahbagh",
     "road": "Kazi Nazrul Islam Ave", "origin": "karwanbazar", "dest": "shahbagh", "sumo_mapped": True},
    # --- extended coverage: the northern spine, the Gulshan approach, the commercial core ---
    {"id": "mohakhali_to_gulshan1", "name": "Mohakhali → Gulshan 1",
     "road": "Gulshan Link Rd", "origin": "mohakhali", "dest": "gulshan1", "sumo_mapped": False},
    {"id": "airport_to_uttara", "name": "Airport → Uttara",
     "road": "Airport Rd (N1)", "origin": "airport", "dest": "uttara", "sumo_mapped": False},
    {"id": "mirpur10_to_agargaon", "name": "Mirpur 10 → Agargaon",
     "road": "Rokeya Sarani", "origin": "mirpur10", "dest": "agargaon", "sumo_mapped": False},
    {"id": "motijheel_to_gulistan", "name": "Motijheel → Gulistan",
     "road": "Toyenbee Circular Rd", "origin": "motijheel", "dest": "gulistan", "sumo_mapped": False},
    {"id": "banani_to_mohakhali", "name": "Banani → Mohakhali",
     "road": "Airport Rd (N1)", "origin": "banani", "dest": "mohakhali", "sumo_mapped": False},
    {"id": "gulistan_to_jatrabari", "name": "Gulistan → Jatrabari",
     "road": "Dhaka-Chattogram Hwy", "origin": "gulistan", "dest": "jatrabari", "sumo_mapped": False},
)

BY_ID = {c["id"]: c for c in CORRIDORS}


def coords(corridor: dict) -> tuple[tuple[float, float], tuple[float, float]]:
    return PLACES[corridor["origin"]], PLACES[corridor["dest"]]


def describe(corridor: dict) -> dict:
    o, d = coords(corridor)
    return {"id": corridor["id"], "name": corridor["name"], "road": corridor["road"],
            "origin": {"lat": o[0], "lng": o[1], "place": corridor["origin"]},
            "destination": {"lat": d[0], "lng": d[1], "place": corridor["dest"]},
            "sumo_mapped": corridor["sumo_mapped"]}
