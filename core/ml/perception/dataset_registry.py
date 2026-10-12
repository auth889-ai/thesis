"""Pre-registered dataset candidate registry for the PERCEPTION research gate.

RESEARCH module (not runtime): dataset discovery, scoring and selection. The
class taxonomy it feeds is runtime and lives in `dhakaflow/perception/taxonomy.py`.

FROZEN BEFORE MEASUREMENT. This module is the perception-gate analogue of Lab 02's
`regions.py`: the candidate set and every claimed fact are written down *before*
any scoring runs, so selection cannot be retrofitted to whichever dataset turned
out easiest to download.

Every field carries an evidence tag:

* ``PUBLISHED`` — stated by the primary source (paper, official repo, official
  dataset page) and verified by us at the recorded URL.
* ``INFERRED``  — derived by us from a published artifact (e.g. class *order*
  read out of the authors' own tooling).
* ``ASSUMED``   — not established; must be resolved by fetch/audit before the
  dataset may be classified USED.

Facts recorded here are claims by the source. They are NOT evidence. Only
`src/audit/` output measured from real files is evidence, and where the two
disagree the audit wins and the disagreement is reported.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Sequence

# Research date for every URL verification in this module.
RESEARCH_DATE = "2026-08-14"


class Role(str, Enum):
    """The seven dataset roles Lab 03 must fill (user mandate §C)."""

    PRIMARY_DETECTION = "PRIMARY_DETECTION_DATASET"
    EXTERNAL_DETECTION_VALIDATION = "EXTERNAL_DETECTION_VALIDATION_DATASET"
    TRACKING_VIDEO = "TRACKING_VIDEO_DATASET"
    TRAFFIC_SENSOR = "TRAFFIC_SENSOR_DATA"
    CALIBRATION = "CALIBRATION_DATA"
    PEDESTRIAN = "OPTIONAL_PEDESTRIAN_DATA"
    INCIDENT = "OPTIONAL_INCIDENT_DATA"


class Status(str, Enum):
    """Resource classification (permanent traceability policy)."""

    USED = "USED"                              # fetched AND audited AND used
    VERIFIED_NOT_USED = "VERIFIED_NOT_USED"    # fetched/checked, deliberately not used
    OPTIONAL = "OPTIONAL"
    FUTURE = "FUTURE"
    REJECTED = "REJECTED"
    PENDING_FETCH = "PENDING_FETCH"            # in-flight; may never appear in a PASS report


class Evidence(str, Enum):
    PUBLISHED = "PUBLISHED"
    INFERRED = "INFERRED"
    ASSUMED = "ASSUMED"


@dataclass(frozen=True)
class Fact:
    """A single claim plus how we know it."""

    value: object
    evidence: Evidence
    source: str = ""

    def __post_init__(self) -> None:
        if self.evidence is not Evidence.ASSUMED and not self.source:
            raise ValueError("PUBLISHED/INFERRED facts require a source URL or path")


@dataclass(frozen=True)
class Candidate:
    """One candidate dataset, pre-registered before scoring."""

    key: str
    title: str
    primary_paper: str                  # DOI or arXiv URL; "" if none exists
    official_page: str                  # dataset landing page
    download_url: str                   # direct/authenticated download entry point
    license_name: str                   # verbatim; "UNSPECIFIED" is a legitimate answer
    license_verified: bool
    roles_claimed: Sequence[Role]
    modality: str                       # image | video | image_from_video | tabular
    facts: Mapping[str, Fact] = field(default_factory=dict)
    source_classes: Sequence[str] = ()
    annotation_format: str = "UNKNOWN"
    notes: str = ""
    blocking_requirement: str = ""      # what stops us fetching it right now

    def claim(self, name: str) -> object:
        """Claimed value of a field, or None when not claimed."""
        fact = self.facts.get(name)
        return None if fact is None else fact.value

    @property
    def is_fetchable_without_credentials(self) -> bool:
        return not self.blocking_requirement


# ---------------------------------------------------------------------------
# The frozen candidate set.
# ---------------------------------------------------------------------------

# BNVD class order is INFERRED from the authors' own tooling
# (upstream/BNVD/Tools/annotation_counter.py @ b4e74d1), which enumerates
# class_list in YOLO index order. The README lists the same 17 names in the same
# order. We never guess label indices from a README alone.
BNVD_CLASSES: tuple[str, ...] = (
    "Bicycle", "Bus", "Bhotbhoti", "Car", "CNG", "Easybike", "Leguna",
    "Motorbike", "MPV", "Pedestrian", "Pickup", "PowerTiller", "Rickshaw",
    "ShoppingVan", "Truck", "Van", "Wheelbarrow",
)

PORIBOHON_BD_CLASSES: tuple[str, ...] = (
    "bicycle", "boat", "bus", "car", "cng", "easy-bike", "horse-cart", "launch",
    "leguna", "motorbike", "rickshaw", "tractor", "truck", "van", "wheelbarrow",
)

BADODD_CLASSES: tuple[str, ...] = (
    "auto-rickshaw", "bicycle", "bus", "car", "cart-vehicle",
    "construction-vehicle", "motorbike", "person", "priority-vehicle",
    "three-wheeler", "train", "truck", "wheelchair",
)


CANDIDATES: tuple[Candidate, ...] = (
    Candidate(
        key="BNVD",
        title="Bangladeshi Native Vehicle Dataset (BNVD)",
        primary_paper="https://arxiv.org/abs/2405.12150",
        official_page="https://github.com/bipin-saha/BNVD",
        download_url="https://www.kaggle.com/datasets/sahabipin/bangladeshi-native-vehicle-dataset",
        license_name="UNSPECIFIED",
        license_verified=False,
        roles_claimed=(Role.PRIMARY_DETECTION, Role.PEDESTRIAN),
        modality="image",
        source_classes=BNVD_CLASSES,
        annotation_format="YOLO_TXT",
        facts={
            "n_images": Fact(17326, Evidence.PUBLISHED, "https://arxiv.org/abs/2405.12150"),
            "n_instances": Fact(81542, Evidence.PUBLISHED, "https://arxiv.org/abs/2405.12150"),
            "n_classes": Fact(17, Evidence.PUBLISHED, "https://arxiv.org/abs/2405.12150"),
            "min_image_width_px": Fact(1280, Evidence.PUBLISHED, "https://arxiv.org/abs/2405.12150"),
            "mean_bbox_per_image": Fact(4.7036, Evidence.PUBLISHED, "https://arxiv.org/abs/2405.12150"),
            "class_index_order": Fact(
                BNVD_CLASSES, Evidence.INFERRED,
                "upstream/BNVD/Tools/annotation_counter.py @ b4e74d1"),
            "upstream_sha": Fact(
                "b4e74d17dc089af5ffe81c9a29c6b4dbdf59ff6f", Evidence.PUBLISHED,
                "git rev-parse HEAD, cloned 2026-08-14"),
            "benchmark_map50": Fact(0.848, Evidence.PUBLISHED, "README.md YOLOv8 row"),
            "viewpoint": Fact("street-level / roadside, mixed", Evidence.ASSUMED),
            "size_bytes": Fact(None, Evidence.ASSUMED),
        },
        blocking_requirement="Kaggle API token (~/.kaggle/kaggle.json); Kaggle blocks scripted access",
        notes=(
            "Largest verified BD-native detection set. README's License section is "
            "EMPTY — license must be read off the Kaggle page before any use. "
            "Authors pin the exact upstream commits they benchmarked "
            "(versions.txt: yolov5 b599ae4, yolov6 e86a483, yolov7 a207844, "
            "ultralytics 8.2.2)."
        ),
    ),
    Candidate(
        key="PORIBOHON_BD",
        title="Poribohon-BD: Bangladeshi local vehicle image dataset",
        primary_paper="https://doi.org/10.1016/j.dib.2020.106470",
        official_page="https://data.mendeley.com/datasets/pwyyg8zmk5/2",
        download_url="https://data.mendeley.com/datasets/pwyyg8zmk5/2",
        license_name="CC BY 4.0",
        license_verified=True,
        roles_claimed=(Role.EXTERNAL_DETECTION_VALIDATION,),
        modality="image",
        source_classes=PORIBOHON_BD_CLASSES,
        annotation_format="PASCAL_VOC_XML",
        facts={
            "n_images": Fact(9058, Evidence.PUBLISHED, "https://data.mendeley.com/datasets/pwyyg8zmk5/2"),
            "n_classes": Fact(15, Evidence.PUBLISHED, "https://data.mendeley.com/datasets/pwyyg8zmk5/2"),
            "doi": Fact("10.17632/pwyyg8zmk5.2", Evidence.PUBLISHED,
                        "https://data.mendeley.com/datasets/pwyyg8zmk5/2"),
            "version": Fact("2 (2020-10-01)", Evidence.PUBLISHED,
                            "https://data.mendeley.com/datasets/pwyyg8zmk5/2"),
            "collection_method": Fact("smartphone camera + social media", Evidence.PUBLISHED,
                                      "https://data.mendeley.com/datasets/pwyyg8zmk5/2"),
            "faces_blurred": Fact(True, Evidence.PUBLISHED,
                                  "https://data.mendeley.com/datasets/pwyyg8zmk5/2"),
            "size_bytes": Fact(None, Evidence.ASSUMED),
        },
        notes=(
            "Distribution deliberately unlike BNVD (social-media + phone photos, "
            "often single-vehicle framing), which is exactly what makes it a fair "
            "EXTERNAL validation set rather than a second training set. Contains "
            "non-road classes (boat, launch) that map to UNSUPPORTED for DhakaFlow."
        ),
    ),
    Candidate(
        key="TFP_BD",
        title="TFP-BD: Traffic Flow and Pedestrian movement, Bangladeshi urban roads",
        primary_paper="https://doi.org/10.1016/j.dib.2025.111403",
        official_page="https://pmc.ncbi.nlm.nih.gov/articles/PMC11919376/",
        download_url="https://data.mendeley.com/datasets/h8bfgtdp2r",
        license_name="UNVERIFIED",
        license_verified=False,
        roles_claimed=(Role.TRACKING_VIDEO, Role.TRAFFIC_SENSOR, Role.PEDESTRIAN),
        modality="image_from_video",
        source_classes=("bike", "rickshaw", "car", "bus", "cycle", "mini-truck",
                        "truck", "cng", "pedestrian"),
        annotation_format="ROBOFLOW_EXPORT",
        facts={
            "n_images": Fact(23678, Evidence.PUBLISHED, "https://pmc.ncbi.nlm.nih.gov/articles/PMC11919376/"),
            "locations": Fact(("Shapla Chattar", "Arambag", "Bashabo", "Abul Hotel"),
                              Evidence.PUBLISHED, "https://pmc.ncbi.nlm.nih.gov/articles/PMC11919376/"),
            "viewpoint": Fact("elevated — recorded from foot-over-bridges", Evidence.PUBLISHED,
                              "https://pmc.ncbi.nlm.nih.gov/articles/PMC11919376/"),
            "fps": Fact(60, Evidence.PUBLISHED, "https://pmc.ncbi.nlm.nih.gov/articles/PMC11919376/"),
            "time_slots": Fact(("07:00-08:00", "08:30-09:30", "12:00-13:00",
                                "18:30-19:30", "20:00-21:00"), Evidence.PUBLISHED,
                               "https://pmc.ncbi.nlm.nih.gov/articles/PMC11919376/"),
            "source_videos_released": Fact(None, Evidence.ASSUMED),
            "track_ids_present": Fact(None, Evidence.ASSUMED),
        },
        notes=(
            "The ONLY candidate whose viewpoint matches fixed traffic cameras: "
            "elevated, static, video-derived, Dhaka, multi-time-of-day. Decisive "
            "open question the audit must settle — are the SOURCE VIDEOS released, "
            "or only extracted frames? ByteTrack needs consecutive frames with "
            "temporal continuity; a shuffled image dump cannot fill TRACKING_VIDEO."
        ),
    ),
    Candidate(
        key="BADODD",
        title="BadODD: Bangladeshi Autonomous Driving Object Detection Dataset",
        primary_paper="https://arxiv.org/abs/2401.10659",
        official_page="https://arxiv.org/abs/2401.10659",
        download_url="",
        license_name="UNSPECIFIED",
        license_verified=False,
        roles_claimed=(Role.EXTERNAL_DETECTION_VALIDATION,),
        modality="image",
        source_classes=BADODD_CLASSES,
        annotation_format="UNKNOWN",
        facts={
            "n_images": Fact(9825, Evidence.PUBLISHED, "https://arxiv.org/abs/2401.10659"),
            "n_classes": Fact(13, Evidence.PUBLISHED, "https://arxiv.org/abs/2401.10659"),
            "districts": Fact(9, Evidence.PUBLISHED, "https://arxiv.org/abs/2401.10659"),
            "day_and_night": Fact(True, Evidence.PUBLISHED, "https://arxiv.org/abs/2401.10659"),
            "viewpoint": Fact("dashcam / in-vehicle smartphone", Evidence.PUBLISHED,
                              "https://arxiv.org/abs/2401.10659"),
            "download_url_exists": Fact(False, Evidence.ASSUMED),
        },
        blocking_requirement="No dataset download link found on the arXiv landing page",
        notes=(
            "Classes are defined by characteristic, not local vehicle name "
            "(e.g. 'three-wheeler' rather than 'CNG'), so mapping into the "
            "DhakaFlow taxonomy is lossy in the CNG/auto-rickshaw region. "
            "Nationwide (9 districts) rather than Dhaka-specific."
        ),
    ),
    Candidate(
        key="DHAKA_AI_2020",
        title="DhakaAI 2020 traffic detection challenge dataset",
        primary_paper="",
        official_page="",
        download_url="",
        license_name="UNSPECIFIED",
        license_verified=False,
        roles_claimed=(Role.EXTERNAL_DETECTION_VALIDATION,),
        modality="image",
        annotation_format="UNKNOWN",
        facts={
            "n_images": Fact(3000, Evidence.ASSUMED),
            "n_classes": Fact(21, Evidence.ASSUMED),
            "official_landing_page": Fact(None, Evidence.ASSUMED),
        },
        blocking_requirement="No official landing page located; only third-party competitor repos",
        notes=(
            "Historically important (first big Dhaka detection challenge) and used "
            "as a comparison row in the BNVD paper, but we found no authoritative "
            "distribution point. Third-party competitor repos are not a provenance "
            "chain. Do not treat as CORE without an official source."
        ),
    ),
    Candidate(
        key="BD_ACCIDENT_2007_2024",
        title="Bangladesh Road Traffic Accident Dataset (2007–2024), multi-source",
        primary_paper="",
        official_page=(
            "https://figshare.com/articles/dataset/"
            "Bangladesh_Road_Traffic_Accident_Dataset_2007_2024_Multi-Source_Integration_/30631292"
        ),
        download_url=(
            "https://figshare.com/articles/dataset/"
            "Bangladesh_Road_Traffic_Accident_Dataset_2007_2024_Multi-Source_Integration_/30631292"
        ),
        license_name="UNVERIFIED",
        license_verified=False,
        roles_claimed=(Role.INCIDENT,),
        modality="tabular",
        annotation_format="TABULAR",
        facts={
            "n_records": Fact(49566, Evidence.PUBLISHED, "figshare landing page"),
            "years": Fact("2007-2024", Evidence.PUBLISHED, "figshare landing page"),
            "sources": Fact(("ARI/BUET", "BRTA", "Dhaka Metropolitan Police", "Military Police"),
                            Evidence.PUBLISHED, "figshare landing page"),
            "anonymised": Fact(True, Evidence.PUBLISHED, "figshare landing page"),
        },
        notes=(
            "Tabular crash records, not perception data. Useful to Lab 24 (incident "
            "NLP) and as a safety prior; contributes NOTHING to detection or "
            "tracking and must not be counted toward those roles."
        ),
    ),
    Candidate(
        key="UBER_MOVEMENT_DHAKA",
        title="Uber Movement — Dhaka travel times / speeds",
        primary_paper="",
        official_page="https://movement.uber.com/",
        download_url="",
        license_name="N/A",
        license_verified=False,
        roles_claimed=(Role.CALIBRATION,),
        modality="tabular",
        facts={
            "service_status": Fact("DISCONTINUED", Evidence.PUBLISHED,
                                   "https://data.transportationops.org/uber-movement"),
        },
        blocking_requirement="Service discontinued by Uber; no current public distribution",
        notes=(
            "Recorded so the calibration gap is explicit rather than silently "
            "unfilled. REJECTED — cannot be fetched at any price. Calibration speed "
            "reference must come from the live-API track (Google Routes) or from "
            "TFP-BD-derived speeds, not from this."
        ),
    ),
)


def by_key(key: str) -> Candidate:
    for c in CANDIDATES:
        if c.key == key:
            return c
    raise KeyError(f"unknown candidate {key!r}; known: {[c.key for c in CANDIDATES]}")


def candidates_for(role: Role) -> tuple[Candidate, ...]:
    return tuple(c for c in CANDIDATES if role in c.roles_claimed)


def registry_digest() -> str:
    """Stable digest of the frozen registry, so post-hoc edits are detectable."""
    import hashlib

    payload = "\n".join(
        f"{c.key}|{c.title}|{c.license_name}|{','.join(r.value for r in c.roles_claimed)}"
        f"|{','.join(c.source_classes)}"
        for c in CANDIDATES
    )
    return hashlib.sha256(payload.encode()).hexdigest()
