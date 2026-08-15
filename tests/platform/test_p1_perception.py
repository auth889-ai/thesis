"""P1 tests: VOC→YOLO conversion integrity and the benchmark schema rules."""
from __future__ import annotations

import pytest

from research.perception.benchmark_schema import (BenchmarkRow, MANDATED_METRICS,
                                                  assert_fair_common_budget,
                                                  select_winner)
from research.perception.voc_to_yolo import (PORIBOHON_CLASSES, convert_dataset,
                                             round_trip_error, voc_box_to_yolo,
                                             yolo_box_to_voc)

VOC_XML = """<annotation>
  <size><width>640</width><height>480</height></size>
  <object><name>rickshaw</name>
    <bndbox><xmin>100</xmin><ymin>50</ymin><xmax>300</xmax><ymax>250</ymax></bndbox>
  </object>
  <object><name>cng</name>
    <bndbox><xmin>0</xmin><ymin>0</ymin><xmax>642</xmax><ymax>480</ymax></bndbox>
  </object>
  <object><name>spaceship</name>
    <bndbox><xmin>1</xmin><ymin>1</ymin><xmax>10</xmax><ymax>10</ymax></bndbox>
  </object>
  <object><name>bus</name>
    <bndbox><xmin>500</xmin><ymin>400</ymin><xmax>500</xmax><ymax>400</ymax></bndbox>
  </object>
</annotation>"""


# ------------------------------------------------------------- conversion
def test_voc_to_yolo_center_format():
    cx, cy, w, h = voc_box_to_yolo(100, 50, 300, 250, 640, 480)
    assert cx == pytest.approx(200 / 640)
    assert cy == pytest.approx(150 / 480)
    assert w == pytest.approx(200 / 640)
    assert h == pytest.approx(200 / 480)


def test_round_trip_is_lossless():
    assert round_trip_error(100, 50, 300, 250, 640, 480) < 1e-9
    # out-of-bounds coordinates round-trip to their clamped values
    assert round_trip_error(-3, 0, 642, 480, 640, 480) < 1e-9


def test_degenerate_box_rejected():
    with pytest.raises(ValueError, match="degenerate"):
        voc_box_to_yolo(500, 400, 500, 400, 640, 480)


def test_nan_coordinates_rejected():
    with pytest.raises(ValueError, match="non-finite"):
        voc_box_to_yolo(float("nan"), 0, 10, 10, 640, 480)


def test_convert_dataset_counts_every_rejection(tmp_path):
    (tmp_path / "a.xml").write_text(VOC_XML)
    out = tmp_path / "labels"
    rep = convert_dataset(tmp_path, out)

    assert rep.n_xml_files == 1 and rep.n_converted == 1
    assert rep.n_boxes == 2                       # rickshaw + clamped cng
    assert rep.n_unknown_labels == 1              # spaceship — counted, not silent
    assert rep.unknown_labels == {"spaceship": 1}
    assert rep.n_boxes_rejected == 1              # degenerate bus box
    assert any("degenerate" in r for r in rep.rejections)

    lines = (out / "a.txt").read_text().strip().splitlines()
    assert len(lines) == 2
    # class indices come from the explicit list, not first-appearance order
    assert lines[0].startswith(str(PORIBOHON_CLASSES.index("rickshaw")))
    assert lines[1].startswith(str(PORIBOHON_CLASSES.index("cng")))


def test_class_index_is_explicit_and_stable():
    assert PORIBOHON_CLASSES.index("rickshaw") == 10
    assert PORIBOHON_CLASSES.index("cng") == 4
    assert len(PORIBOHON_CLASSES) == 15


# ------------------------------------------------------------- schema rules
def _metrics(**over):
    m = {k: 0.5 for k in MANDATED_METRICS}
    m.update(over)
    return m


FAIR_TRAINING = dict(image_size=640, batch_size=16, epochs=60,
                     optimizer="AdamW (official default)", learning_rate="1e-4",
                     augmentation="official_default", inference_precision="FP16",
                     fps_protocol="batch=1 640px FP16 200iter/50warmup")


def _row(**over):
    kw = dict(architecture="dfine", recipe="native", dataset_track="PORIBOHON_BD",
              split_id="s1", checkpoint_origin="official", official_repo_sha="abc123",
              gpu="T4", training=dict(FAIR_TRAINING), metrics=_metrics())
    kw.update(over)
    return BenchmarkRow(**kw)


def test_deim_cannot_be_passed_as_an_architecture():
    """The user's correction, enforced mechanically."""
    with pytest.raises(ValueError, match="DEIM is a recipe"):
        _row(architecture="deim")


def test_deim_is_a_valid_recipe():
    assert _row(recipe="deim").label == "dfine+deim@PORIBOHON_BD"


def test_missing_mandated_metric_rejected():
    m = _metrics()
    del m["ap_rickshaw"]
    with pytest.raises(ValueError, match="ap_rickshaw"):
        _row(metrics=m)


def test_not_measured_requires_reason_not_zero():
    m = _metrics()
    del m["training_time_h"]
    row = _row(metrics=m,
               not_measured={"training_time_h": "resumed from checkpoint; wall time unrecorded"})
    assert "training_time_h" not in row.metrics


def test_result_without_sha_rejected():
    with pytest.raises(ValueError, match="no SHA, no result"):
        _row(official_repo_sha="")


def test_domain_shift_reported_not_forced():
    a = _row(architecture="dfine", dataset_track="BNVD",
             metrics=_metrics(ap_rickshaw=0.9, ap_cng=0.9))
    b = _row(architecture="rtdetr_v2", dataset_track="PORIBOHON_BD",
             metrics=_metrics(ap_rickshaw=0.9, ap_cng=0.9))
    c = _row(architecture="rtdetr_v2", dataset_track="BNVD")
    d = _row(architecture="dfine", dataset_track="PORIBOHON_BD")
    verdict = select_winner([a, b, c, d])
    assert verdict["domain_shift"] is True
    assert "DOMAIN_SHIFT" in verdict["verdict"]


def test_single_winner_when_tracks_agree():
    a = _row(architecture="dfine", dataset_track="BNVD",
             metrics=_metrics(ap_rickshaw=0.9))
    b = _row(architecture="dfine", dataset_track="PORIBOHON_BD",
             metrics=_metrics(ap_rickshaw=0.9))
    c = _row(architecture="rtdetr_v2", dataset_track="BNVD")
    verdict = select_winner([a, b, c])
    assert verdict["domain_shift"] is False
    assert verdict["verdict"] == "dfine+native"


# ---------------------------------------------------- fair-budget policy
def test_missing_training_provenance_rejected():
    t = dict(FAIR_TRAINING); del t["epochs"]
    with pytest.raises(ValueError, match="training provenance missing"):
        _row(training=t)


def test_unfair_epoch_budget_rejected():
    """One candidate silently given more epochs -> the comparison refuses to run."""
    a = _row(architecture="dfine")
    t = dict(FAIR_TRAINING, epochs=120)          # double budget, same class
    b = _row(architecture="rtdetr_v2", training=t)
    with pytest.raises(ValueError, match="UNFAIR BUDGET"):
        assert_fair_common_budget([a, b])


def test_official_reproduction_budget_may_differ():
    """Author schedules legitimately differ; reproduction rows are exempt."""
    a = _row(architecture="dfine", budget_class="OFFICIAL_REPRODUCTION_BUDGET",
             training=dict(FAIR_TRAINING, epochs=72))
    b = _row(architecture="rtdetr_v2", budget_class="OFFICIAL_REPRODUCTION_BUDGET",
             training=dict(FAIR_TRAINING, epochs=120))
    assert_fair_common_budget([a, b])            # no raise


def test_winner_selection_ignores_tuned_and_reproduction_rows():
    tuned = _row(architecture="rtdetr_v2", budget_class="TUNED_BUDGET",
                 metrics=_metrics(ap_rickshaw=0.99))
    common = _row(architecture="dfine")
    verdict = select_winner([tuned, common])
    assert verdict["verdict"] == "dfine+native"  # tuned row never selects


def test_incomplete_benchmark_declares_no_winner():
    rows = [_row(architecture="dfine")]
    verdict = select_winner(rows, expected_candidates=[("dfine", "native"),
                                                       ("rtdetr_v2", "native")])
    assert verdict["verdict"] == "INCOMPLETE"
    assert ("rtdetr_v2", "native") in verdict["missing"]["PORIBOHON_BD"]


def test_gpu_required():
    with pytest.raises(ValueError, match="gpu is required"):
        _row(gpu="")
