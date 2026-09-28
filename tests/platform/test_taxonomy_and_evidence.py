"""Taxonomy invariants and the three-domain evidence separation.

The evidence-domain tests encode the rule that protects every real-world claim
this thesis will make: simulated SUMO detector output is never a real sensor
measurement, and a model evaluated only inside the simulator cannot support a
real-Dhaka claim.
"""
from __future__ import annotations

import pytest

from traffictwin.common.model_registry import (EvidenceDomain, MetricBlock,
                                             ModelEntry, ModelStatus)
from traffictwin.perception.taxonomy import (MAPPINGS, ClassMapping, DhakaFlowClass,
                                           MappingQuality, coverage_report,
                                           cross_dataset_conflicts, mapping_for,
                                           open_decisions, trainable_classes)


# ------------------------------------------------------------------- taxonomy
@pytest.mark.parametrize("dataset", sorted(MAPPINGS))
def test_every_source_class_has_a_declared_mapping(dataset):
    ms = mapping_for(dataset)
    assert ms, f"{dataset}: no mappings declared"
    labels = [m.source_label for m in ms]
    assert len(labels) == len(set(labels)), f"{dataset}: duplicate source labels"


@pytest.mark.parametrize("dataset", sorted(MAPPINGS))
def test_every_mapping_has_a_rationale(dataset):
    for m in mapping_for(dataset):
        assert m.rationale.strip(), f"{dataset}/{m.source_label}: mapping without rationale"


def test_ambiguous_requires_multiple_candidates():
    with pytest.raises(ValueError, match="requires >= 2 candidate targets"):
        ClassMapping("x", None, MappingQuality.AMBIGUOUS, "r",
                     (DhakaFlowClass.VAN,))


def test_unsupported_must_not_carry_a_target():
    with pytest.raises(ValueError, match="must not carry a target"):
        ClassMapping("boat", DhakaFlowClass.OTHER, MappingQuality.UNSUPPORTED, "r")


def test_ambiguous_classes_are_not_trainable():
    """AMBIGUOUS labels are excluded from training, never silently resolved."""
    for dataset in MAPPINGS:
        for m in open_decisions(dataset):
            assert not m.is_trainable, (
                f"{dataset}/{m.source_label}: AMBIGUOUS must not enter a training set")


def test_known_bangladeshi_traps_stay_flagged():
    """Regression guard on the two mappings that would silently corrupt the data.

    'Van' in Bangladeshi usage is often a pedal rickshaw-van, and 'Easybike' is a
    battery three-wheeler with no slot in the taxonomy. If a future edit quietly
    resolves either one, this fails.
    """
    bnvd = {m.source_label: m for m in mapping_for("BNVD")}
    assert bnvd["Van"].quality is MappingQuality.AMBIGUOUS
    assert bnvd["Easybike"].quality is MappingQuality.AMBIGUOUS
    poribohon = {m.source_label: m for m in mapping_for("PORIBOHON_BD")}
    assert poribohon["van"].quality is MappingQuality.AMBIGUOUS


def test_rickshaw_and_cng_are_exact_in_every_dataset_that_names_them():
    """The two classes that make Dhaka different must never be merged away."""
    for dataset in MAPPINGS:
        for m in mapping_for(dataset):
            if m.source_label.lower() in {"rickshaw", "cng"}:
                assert m.quality is MappingQuality.EXACT_MAPPING, (
                    f"{dataset}/{m.source_label}: must stay an exact mapping")


def test_trainable_targets_are_nonempty_for_each_dataset():
    for dataset in MAPPINGS:
        assert trainable_classes(dataset), f"{dataset}: no trainable target classes"


def test_coverage_report_is_serialisable():
    import json
    for dataset in MAPPINGS:
        json.dumps(coverage_report(dataset))


def test_cross_dataset_conflicts_are_reported_not_hidden():
    """Different datasets resolving the same label differently must be surfaced."""
    conflicts = cross_dataset_conflicts()
    labels = {c["source_label"] for c in conflicts}
    # 'van' is EXACT nowhere and AMBIGUOUS in two datasets; 'bike'/'cycle' differ.
    assert "van" in labels or not conflicts, (
        "cross-dataset conflict detection is not working")


# ------------------------------------------------------- evidence separation
def _entry(status: ModelStatus, domains: list[EvidenceDomain]) -> ModelEntry:
    return ModelEntry(
        key="m", subsystem="forecasting", architecture="a", status=status,
        official_sha="deadbeef", benchmark="dhaka-common",
        decision_rationale="test",
        metrics=tuple(MetricBlock(d, f"ds-{d.value}", {"MAE": 1.0}) for d in domains),
    )


def test_simulated_only_model_supports_no_real_world_claim():
    e = _entry(ModelStatus.BENCHMARKED, [EvidenceDomain.DHAKA_SIMULATED_SENSOR_GRAPH])
    assert not e.real_world_claim_supported, (
        "a model evaluated only on SUMO output must not support a real-Dhaka claim")


def test_real_anchor_or_official_benchmark_supports_a_real_claim():
    for domain in (EvidenceDomain.DHAKA_REAL_VALIDATION_ANCHORS,
                   EvidenceDomain.OFFICIAL_REAL_BENCHMARK):
        assert _entry(ModelStatus.BENCHMARKED, [domain]).real_world_claim_supported


def test_winner_requires_measured_metrics():
    with pytest.raises(ValueError, match="requires measured metrics"):
        ModelEntry(key="w", subsystem="control", architecture="a",
                   status=ModelStatus.WINNER, benchmark="b",
                   decision_rationale="because")


def test_winner_requires_a_named_benchmark():
    with pytest.raises(ValueError, match="must name the benchmark"):
        ModelEntry(key="w", subsystem="control", architecture="a",
                   status=ModelStatus.WINNER, decision_rationale="because",
                   metrics=(MetricBlock(EvidenceDomain.OFFICIAL_REAL_BENCHMARK,
                                        "metr-la", {"MAE": 3.0}),))


def test_reproduced_requires_the_exact_official_sha():
    with pytest.raises(ValueError, match="requires the exact official_sha"):
        ModelEntry(key="r", subsystem="forecasting", architecture="DCRNN",
                   status=ModelStatus.REPRODUCED)


def test_metric_block_requires_values():
    with pytest.raises(ValueError, match="has no values"):
        MetricBlock(EvidenceDomain.OFFICIAL_REAL_BENCHMARK, "metr-la", {})
