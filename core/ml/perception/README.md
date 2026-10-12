# core/ml/perception — vehicles from camera video

Camera video → detections (RT-DETR fine-tuned on Dhaka classes) → tracks (official ByteTrack) → a traffic state
(counts, speeds, density). This is earlier groundwork. **None of RQ1–RQ6 uses its output.** The recorded Dhaka speeds
the research uses come from DhaTraX, whose authors ran their own tracking pipeline.

## Papers and official repositories
**Not recorded in third_party/SOURCES.md.** The pins are in `upstream/UPSTREAM_PINS.yaml`; the module docstrings name:
- **RT-DETR:** the official repository's `tools/infer.py` loading pattern, followed verbatim (`rtdetr_dhaka.py`);
- **ByteTrack:** FoundationVision, commit `d1bf019` (`bytetrack_adapter.py`);
- **Poribohon-BD:** a Bangladeshi vehicle dataset with Pascal-VOC annotations (`voc_to_yolo.py`).

Licences are not recorded in third_party/SOURCES.md.

## Which file implements which part
| File | Part |
|---|---|
| `rtdetr_dhaka.py` | Dhaka-fine-tuned RT-DETR inference, the authors' loading pattern (EMA weights, `deploy()`); maps training labels back to Poribohon class names. |
| `rtdetr_bridge.py` | A line-protocol server exposing the detector to other Python environments (the authors' pinned environment differs from ours). |
| `bytetrack_adapter.py` | Detections in, tracks out: the published association algorithm, unmodified. The file only converts formats. |
| `pipeline.py` | Video → RT-DETR → ByteTrack → `TrafficState`. |
| `state_estimator.py` | Physical traffic state from tracked vehicles. |
| `taxonomy.py` | Our class taxonomy and the declared source → target mapping. A label that cannot be mapped honestly is tagged AMBIGUOUS or UNSUPPORTED and excluded from training. |
| `voc_to_yolo.py`, `yolo_to_coco.py` | Format converters with box validation and a round-trip error check. |
| `dataset_registry.py`, `dataset_audit.py`, `benchmark_schema.py` | Pre-registered dataset candidates, measured audits (from files, not quoted from papers), and one result schema for every candidate. |

## Substitutions and why
- **Environment shims, not algorithm changes:** NumPy ≥ 1.24 removed aliases ByteTrack's 2021 code uses, and RT-DETR runs in its own conda environment with the authors' exact pins.
- **The demo overlay** uses a minimal IoU track-carrier for IDs only. Tracking claims come from official ByteTrack.

## Tests
| File | What it checks |
|---|---|
| `tests/platform/test_p1_perception.py` | VOC → YOLO conversion integrity and the benchmark schema rules. |
| `tests/platform/test_yolo_to_coco.py` | YOLO → COCO is a format translation only, on synthetic files. |
| `tests/platform/test_taxonomy_and_evidence.py` | Taxonomy invariants and the three-domain evidence separation. |

## Results
No perception result feeds the research questions, so no summary file is listed here.
