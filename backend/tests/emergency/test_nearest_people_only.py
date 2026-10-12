"""QA 2026-10-07 rank 8: "Vet-RX", an animal hospital tagged amenity=hospital in OpenStreetMap, was offered as the third nearest
hospital from Mohakhali. The nearest list now leaves animal hospitals out, even when the road server ranks one first."""
from core.safety import hospitals, reach


def test_the_saved_dhaka_file_has_exactly_these_animal_hospitals():
    people, animal = hospitals.for_people(hospitals.load("dhaka")["hospitals"])
    assert sorted(h["name"] for h in animal) == ["National Veterinary Hospital, Bangabazar Chakkar, Dhaka", "Vet-RX"]
    assert len(people) == 475


def test_tag_or_name_marks_an_animal_hospital():
    hs = [{"osm_id": "n/1", "name": "Pet Care", "speciality": "veterinary"}, {"osm_id": "n/2", "name": "Vet-RX"},
          {"osm_id": "n/3", "name": "Dhaka Medical College Hospital"}, {"osm_id": "n/4", "name": "Shuvetara Clinic"}]
    people, animal = hospitals.for_people(hs)
    assert [h["osm_id"] for h in animal] == ["n/1", "n/2"] and [h["osm_id"] for h in people] == ["n/3", "n/4"]


def test_nearest_never_returns_an_animal_hospital(monkeypatch):
    file = {"hospitals": [{"osm_id": "n/1", "name": "Vet-RX", "lat": 23.738, "lon": 90.391, "emergency": None},
                          {"osm_id": "n/2", "name": "General Hospital", "lat": 23.74, "lon": 90.39, "emergency": None}]}
    monkeypatch.setattr(reach.hosp, "load", lambda city: file)
    def matrix(city, sources, targets, profile):                     # the server would put whatever it is given first
        return {"available": True, "times_s": [[60 * (i + 1) for i in range(len(targets))]], "distances_m": [[500 * (i + 1) for i in range(len(targets))]]}
    monkeypatch.setattr(reach.valhalla, "matrix", matrix)
    got = reach.nearest("dhaka", 23.78, 90.40)
    assert [h["name"] for h in got["nearest"]] == ["General Hospital"]
    assert got["animal_hospitals_left_out"] == ["Vet-RX"]


def test_one_hospital_entered_twice_is_listed_once():
    """QA 2026-10-08: "General Medical Hospital" is two OpenStreetMap points 35 m apart and filled two of the three nearest."""
    hs = hospitals.load("dhaka")["hospitals"]
    once = hospitals.one_each(hs)
    assert [h["name"] for h in once].count("General Medical Hospital") == 1
    assert [h["name"] for h in once].count("Monowara Hospital") == 2          # two branches 1.9 km apart stay
    # 10 entered twice with the same name (one of them three times); since 2026-10-09 also 11 whose second entry differs only in
    # letter case or an appended address ("Padma General Hospital, Sonargaon Road, Dhaka", "IBN SINA HOSPITAL"), all within 109 m
    assert len(hs) - len(once) == 21
