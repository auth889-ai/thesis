"""DhakaFlow class taxonomy and the source→target mapping layer.

RUNTIME module: the detector's class contract lives here, so every consumer
(sensing, twin vehicle types, control features) reads one definition. The
research-side dataset comparison that produced these mappings lives in
`research/perception/dataset_registry.py`.

Design rule: **source labels are never destroyed.** A mapping is a declared,
inspectable object with a quality tag, not a `rename` in a preprocessing script.
Anything that cannot be mapped honestly is tagged `AMBIGUOUS` or `UNSUPPORTED`
and is *excluded from training* rather than quietly folded into `other`.

Why this matters concretely for Dhaka: several Bangladeshi vehicle names have no
faithful counterpart in the generic COCO-style taxonomy that pretrained
detectors inherit, and two of them are genuine traps:

* **"Van"** in Bangladeshi usage very often means a *pedal-powered flatbed
  rickshaw-van*, not a motor van. Mapping it to a Western `van` would put a
  human-powered vehicle into the light-commercial-vehicle class.
* **"Easybike"** (battery three-wheeler) is a different vehicle from both the
  pedal `rickshaw` and the `CNG` auto-rickshaw, yet the user's candidate
  taxonomy has no slot for it. We flag it rather than pick one.

Unresolved `AMBIGUOUS` entries are a finding for the user, not a defect to paper
over.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class DhakaFlowClass(str, Enum):
    """Candidate DhakaFlow classes (user mandate §G)."""

    CAR = "car"
    MOTORCYCLE = "motorcycle"
    BUS = "bus"
    TRUCK = "truck"
    BICYCLE = "bicycle"
    RICKSHAW = "rickshaw"
    CNG_AUTORICKSHAW = "cng_autorickshaw"
    MICROBUS = "microbus"
    VAN = "van"
    PEDESTRIAN = "pedestrian"
    OTHER = "other"


class MappingQuality(str, Enum):
    EXACT_MAPPING = "EXACT_MAPPING"        # same real-world object, 1:1
    MERGED_MAPPING = "MERGED_MAPPING"      # several source classes → one target; lossy but defensible
    AMBIGUOUS = "AMBIGUOUS"                # the source label does not determine the target
    UNSUPPORTED = "UNSUPPORTED"            # not a road vehicle in our operating domain


@dataclass(frozen=True)
class ClassMapping:
    source_label: str
    target: DhakaFlowClass | None          # None iff UNSUPPORTED or unresolved AMBIGUOUS
    quality: MappingQuality
    rationale: str
    candidate_targets: tuple[DhakaFlowClass, ...] = ()   # only for AMBIGUOUS

    def __post_init__(self) -> None:
        if self.quality is MappingQuality.AMBIGUOUS and len(self.candidate_targets) < 2:
            raise ValueError(
                f"{self.source_label!r}: AMBIGUOUS requires >= 2 candidate targets — "
                "if only one target is plausible it is not ambiguous")
        if self.quality is MappingQuality.UNSUPPORTED and self.target is not None:
            raise ValueError(f"{self.source_label!r}: UNSUPPORTED must not carry a target")
        if self.quality in (MappingQuality.EXACT_MAPPING, MappingQuality.MERGED_MAPPING) \
                and self.target is None:
            raise ValueError(f"{self.source_label!r}: {self.quality.value} requires a target")
        if not self.rationale:
            raise ValueError(f"{self.source_label!r}: every mapping needs a written rationale")

    @property
    def is_trainable(self) -> bool:
        """Only unambiguous, supported mappings may enter a training label set."""
        return self.quality in (MappingQuality.EXACT_MAPPING, MappingQuality.MERGED_MAPPING)


def _m(src: str, target: DhakaFlowClass | None, quality: MappingQuality,
       rationale: str, candidates: tuple[DhakaFlowClass, ...] = ()) -> ClassMapping:
    return ClassMapping(src, target, quality, rationale, candidates)


C = DhakaFlowClass
Q = MappingQuality

# ---------------------------------------------------------------------------
# BNVD (17 classes, YOLO index order from the authors' annotation_counter.py)
# ---------------------------------------------------------------------------
BNVD_MAPPING: tuple[ClassMapping, ...] = (
    _m("Bicycle", C.BICYCLE, Q.EXACT_MAPPING, "Same object."),
    _m("Bus", C.BUS, Q.EXACT_MAPPING, "Same object."),
    _m("Bhotbhoti", None, Q.UNSUPPORTED,
       "Locally-fabricated diesel-engine vehicle (also Nosimon/Karimon), "
       "predominantly rural highway use; not expected in the Lab 02 R1 urban "
       "region. Excluded rather than dumped into `other`, which would pollute a "
       "class we intend to keep meaningful."),
    _m("Car", C.CAR, Q.EXACT_MAPPING, "Same object."),
    _m("CNG", C.CNG_AUTORICKSHAW, Q.EXACT_MAPPING,
       "'CNG' is the standard Bangladeshi name for the green CNG-fuelled "
       "auto-rickshaw; exact match for our CNG_AUTORICKSHAW."),
    _m("Easybike", None, Q.AMBIGUOUS,
       "Battery-electric three-wheeler (Tomtom). Physically distinct from both "
       "the pedal rickshaw and the CNG auto-rickshaw, and heavily present in "
       "Dhaka. The candidate taxonomy has no slot for it. RECOMMENDATION: add an "
       "explicit `easybike` class rather than merge.",
       (C.CNG_AUTORICKSHAW, C.RICKSHAW, C.OTHER)),
    _m("Leguna", None, Q.AMBIGUOUS,
       "Small locally-built share vehicle (human hauler) on a light chassis. "
       "Closer to a microbus in function, closer to a three-wheeler in size.",
       (C.MICROBUS, C.OTHER)),
    _m("Motorbike", C.MOTORCYCLE, Q.EXACT_MAPPING, "Same object."),
    _m("MPV", C.MICROBUS, Q.MERGED_MAPPING,
       "Multi-purpose vehicle / minivan folded into MICROBUS. Lossy: an MPV is a "
       "private people-carrier while a Dhaka microbus is usually a shared "
       "service vehicle. Recorded as MERGED so the loss is auditable."),
    _m("Pedestrian", C.PEDESTRIAN, Q.EXACT_MAPPING, "Same object."),
    _m("Pickup", C.TRUCK, Q.MERGED_MAPPING,
       "Light goods vehicle merged into TRUCK. Lossy in size/PCU terms — "
       "flagged for Lab 06, where PCU conversion depends on vehicle class."),
    _m("PowerTiller", None, Q.UNSUPPORTED,
       "Agricultural machine used as rural road transport; outside the urban "
       "operating domain of the Lab 02 network."),
    _m("Rickshaw", C.RICKSHAW, Q.EXACT_MAPPING,
       "Pedal three-wheeler; the defining Dhaka vehicle class."),
    _m("ShoppingVan", None, Q.AMBIGUOUS,
       "Non-standard label with no established Bangladeshi referent. Must be "
       "resolved by looking at real annotated crops during the audit, not by "
       "guessing from the name.",
       (C.VAN, C.MICROBUS, C.OTHER)),
    _m("Truck", C.TRUCK, Q.EXACT_MAPPING, "Same object."),
    _m("Van", None, Q.AMBIGUOUS,
       "TRAP: in Bangladeshi usage 'van' commonly denotes a pedal-powered "
       "flatbed rickshaw-van, not a motorised panel van. Mapping it to VAN "
       "without visual confirmation would classify a human-powered vehicle as a "
       "light commercial vehicle and corrupt both PCU and speed priors.",
       (C.VAN, C.RICKSHAW, C.OTHER)),
    _m("Wheelbarrow", None, Q.UNSUPPORTED,
       "Hand cart; not a traffic-stream vehicle for signal control purposes."),
)

# ---------------------------------------------------------------------------
# Poribohon-BD (15 classes)
# ---------------------------------------------------------------------------
PORIBOHON_BD_MAPPING: tuple[ClassMapping, ...] = (
    _m("bicycle", C.BICYCLE, Q.EXACT_MAPPING, "Same object."),
    _m("boat", None, Q.UNSUPPORTED, "Waterborne; not road traffic."),
    _m("bus", C.BUS, Q.EXACT_MAPPING, "Same object."),
    _m("car", C.CAR, Q.EXACT_MAPPING, "Same object."),
    _m("cng", C.CNG_AUTORICKSHAW, Q.EXACT_MAPPING, "Same object as BNVD 'CNG'."),
    _m("easy-bike", None, Q.AMBIGUOUS,
       "Same unresolved case as BNVD 'Easybike'; kept consistent across datasets "
       "so the two sets can be compared class-by-class.",
       (C.CNG_AUTORICKSHAW, C.RICKSHAW, C.OTHER)),
    _m("horse-cart", C.OTHER, Q.MERGED_MAPPING,
       "Animal-drawn road vehicle: genuinely on the road, but too rare in the R1 "
       "region to warrant its own class."),
    _m("launch", None, Q.UNSUPPORTED, "Waterborne passenger vessel; not road traffic."),
    _m("leguna", None, Q.AMBIGUOUS, "Same unresolved case as BNVD 'Leguna'.",
       (C.MICROBUS, C.OTHER)),
    _m("motorbike", C.MOTORCYCLE, Q.EXACT_MAPPING, "Same object."),
    _m("rickshaw", C.RICKSHAW, Q.EXACT_MAPPING, "Same object."),
    _m("tractor", None, Q.UNSUPPORTED, "Agricultural; outside the urban domain."),
    _m("truck", C.TRUCK, Q.EXACT_MAPPING, "Same object."),
    _m("van", None, Q.AMBIGUOUS,
       "Same 'van' trap as BNVD — resolve visually, never by name.",
       (C.VAN, C.RICKSHAW, C.OTHER)),
    _m("wheelbarrow", None, Q.UNSUPPORTED, "Hand cart."),
)

# ---------------------------------------------------------------------------
# BadODD (13 classes, characteristic-based names)
# ---------------------------------------------------------------------------
BADODD_MAPPING: tuple[ClassMapping, ...] = (
    _m("auto-rickshaw", None, Q.AMBIGUOUS,
       "BadODD carries BOTH 'auto-rickshaw' and 'three-wheeler', so the two "
       "cannot both be CNG. Their split rule is not recoverable from the paper "
       "abstract; resolve from real annotated crops.",
       (C.CNG_AUTORICKSHAW, C.OTHER)),
    _m("bicycle", C.BICYCLE, Q.EXACT_MAPPING, "Same object."),
    _m("bus", C.BUS, Q.EXACT_MAPPING, "Same object."),
    _m("car", C.CAR, Q.EXACT_MAPPING, "Same object."),
    _m("cart-vehicle", C.OTHER, Q.MERGED_MAPPING, "Cart-type road vehicles pooled."),
    _m("construction-vehicle", C.OTHER, Q.MERGED_MAPPING,
       "Heavy plant; kept out of TRUCK because its speed/PCU behaviour differs."),
    _m("motorbike", C.MOTORCYCLE, Q.EXACT_MAPPING, "Same object."),
    _m("person", C.PEDESTRIAN, Q.EXACT_MAPPING,
       "BadODD names the class by characteristic ('person'); referent is the "
       "same as our PEDESTRIAN."),
    _m("priority-vehicle", C.OTHER, Q.MERGED_MAPPING,
       "Ambulance/police/fire. Mapped to OTHER for detection, but RETAINED as a "
       "source label because Lab 23 (emergency priority) needs exactly this "
       "signal — a case where the source label outlives the mapping."),
    _m("three-wheeler", None, Q.AMBIGUOUS,
       "Could be easybike, leguna, or a non-CNG auto depending on their rule.",
       (C.CNG_AUTORICKSHAW, C.RICKSHAW, C.OTHER)),
    _m("train", None, Q.UNSUPPORTED, "Rail; not road traffic."),
    _m("truck", C.TRUCK, Q.EXACT_MAPPING, "Same object."),
    _m("wheelchair", None, Q.AMBIGUOUS,
       "A wheelchair user is a vulnerable road user; whether they count as "
       "PEDESTRIAN affects safety metrics and must be a deliberate decision.",
       (C.PEDESTRIAN, C.OTHER)),
)

# ---------------------------------------------------------------------------
# TFP-BD (9 classes)
# ---------------------------------------------------------------------------
TFP_BD_MAPPING: tuple[ClassMapping, ...] = (
    _m("bike", C.MOTORCYCLE, Q.MERGED_MAPPING,
       "Resolved by context: TFP-BD lists 'cycle' separately, so 'bike' denotes "
       "the motorised two-wheeler. Recorded as MERGED, not EXACT, because the "
       "resolution comes from the class list rather than from documentation."),
    _m("rickshaw", C.RICKSHAW, Q.EXACT_MAPPING, "Same object."),
    _m("car", C.CAR, Q.EXACT_MAPPING, "Same object."),
    _m("bus", C.BUS, Q.EXACT_MAPPING, "Same object."),
    _m("cycle", C.BICYCLE, Q.EXACT_MAPPING, "Pedal two-wheeler."),
    _m("mini-truck", C.TRUCK, Q.MERGED_MAPPING, "Light goods vehicle merged into TRUCK."),
    _m("truck", C.TRUCK, Q.EXACT_MAPPING, "Same object."),
    _m("cng", C.CNG_AUTORICKSHAW, Q.EXACT_MAPPING, "Same object."),
    _m("pedestrian", C.PEDESTRIAN, Q.EXACT_MAPPING, "Same object."),
)

MAPPINGS: Mapping[str, tuple[ClassMapping, ...]] = {
    "BNVD": BNVD_MAPPING,
    "PORIBOHON_BD": PORIBOHON_BD_MAPPING,
    "BADODD": BADODD_MAPPING,
    "TFP_BD": TFP_BD_MAPPING,
}


def mapping_for(dataset_key: str) -> tuple[ClassMapping, ...]:
    try:
        return MAPPINGS[dataset_key]
    except KeyError as exc:
        raise KeyError(
            f"no class mapping declared for {dataset_key!r}. Declare one "
            "explicitly — datasets must not be trained on with an implicit "
            "identity mapping.") from exc


def trainable_classes(dataset_key: str) -> tuple[DhakaFlowClass, ...]:
    """Target classes reachable from this dataset without an unresolved decision."""
    seen: list[DhakaFlowClass] = []
    for m in mapping_for(dataset_key):
        if m.is_trainable and m.target is not None and m.target not in seen:
            seen.append(m.target)
    return tuple(seen)


def open_decisions(dataset_key: str) -> tuple[ClassMapping, ...]:
    """AMBIGUOUS mappings awaiting a human decision backed by real crops."""
    return tuple(m for m in mapping_for(dataset_key) if m.quality is Q.AMBIGUOUS)


def coverage_report(dataset_key: str) -> dict:
    """Machine-readable summary used by the figures and the manifest."""
    ms = mapping_for(dataset_key)
    counts: dict[str, int] = {}
    for m in ms:
        counts[m.quality.value] = counts.get(m.quality.value, 0) + 1
    return {
        "dataset": dataset_key,
        "n_source_classes": len(ms),
        "quality_counts": counts,
        "trainable_targets": [c.value for c in trainable_classes(dataset_key)],
        "open_decisions": [
            {"source_label": m.source_label,
             "candidate_targets": [c.value for c in m.candidate_targets],
             "rationale": m.rationale}
            for m in open_decisions(dataset_key)
        ],
    }


def cross_dataset_conflicts() -> list[dict]:
    """Source labels that different datasets resolve differently.

    A label mapped EXACT in one dataset and AMBIGUOUS in another is a real
    inconsistency in our own taxonomy work and must be surfaced, not averaged.
    """
    by_label: dict[str, list[tuple[str, ClassMapping]]] = {}
    for key, ms in MAPPINGS.items():
        for m in ms:
            by_label.setdefault(m.source_label.lower(), []).append((key, m))

    conflicts: list[dict] = []
    for label, entries in sorted(by_label.items()):
        if len(entries) < 2:
            continue
        targets = {(m.target.value if m.target else None) for _, m in entries}
        qualities = {m.quality.value for _, m in entries}
        if len(targets) > 1 or len(qualities) > 1:
            conflicts.append({
                "source_label": label,
                "resolutions": [
                    {"dataset": k,
                     "target": m.target.value if m.target else None,
                     "quality": m.quality.value}
                    for k, m in entries
                ],
            })
    return conflicts
