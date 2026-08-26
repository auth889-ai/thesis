# DATA INVENTORY — where every dataset physically lives (verified 26 Aug 2026)

Datasets are stored in cloud storage, NOT in git — binary data never belongs in
a source repository (standard practice; also the sprint storage policy: the
laptop keeps only a rolling window). Each entry lists exact location + checksum
so any examiner can verify existence and integrity.

| Dataset | Size | Where | Integrity |
|---|---|---|---|
| **Poribohon-BD (official Mendeley, CC BY 4.0)** | 7.48 GiB, 9,058 images/XMLs | GCS `gs://dhakaflow-p2-direct-abacus/datasets/poribohon_official.zip` | sha256 alongside |
| **Poribohon YOLO-converted + frozen split** | 8.0 GiB | AWS S3 `s3://dhakaflow-train-915644996102/datasets/pori_yolo.tar.gz` | split id `300aabc8` |
| **BNVD** | 6.06 GiB, 17,326 images | S3 `datasets/bnvd.zip` + GCS mirror | sha256 alongside |
| **UTD19 (7 GB raw, 39 cities)** | 6.98 GB | Drive `DhakaFlow-Nexus-Data/Lab00_UTD19/raw/` | Lab 00 manifest |
| **P2 twin tensor (864×250×4)** | 1.5 MiB npz | repo `artifacts/p2_sensor_graph_full/` + S3 + GCS | sha256 `c5b1a9ba…` |
| **road511 live recording** | growing (~1 GB/day) | Drive `DhakaFlow-Nexus-Data/road511/` (snapshots+incidents) | recorder log |
| **Trained detector winner (654 MB)** | r50 ckpt | GCS `models/p1_winner/` + Drive `models/` + local | sha256 `27852d84…` |
| **E4/DUE-DSO route sets + results** | — | repo `artifacts/due_dso_stats/` | in git |
| TFP-BD (23,678 img) | — | fetch scheduled at tracking stage | — |
| BadODD (9,825 img) | — | fetch at robustness stage | — |

One-command verification examples:
```
gsutil ls -l gs://dhakaflow-p2-direct-abacus/datasets/
aws s3 ls s3://dhakaflow-train-915644996102/datasets/
rclone lsf gdrive2tb:DhakaFlow-Nexus-Data/
```
