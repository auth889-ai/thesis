# DhakaFlow Nexus project architecture

```text
DhakaFlow-Nexus/
├── apps/                       # UI / traffic copilot later
├── services/                   # deployable inference/control services later
│   ├── perception/
│   ├── forecasting/
│   ├── simulation/
│   ├── control/
│   ├── routing/
│   └── incident/
├── modules/                    # research/core algorithms promoted from passed labs
│   ├── perception/
│   ├── tracking/
│   ├── forecasting/
│   ├── digital_twin/
│   ├── control/
│   ├── routing/
│   └── nlp/
├── paper_labs/
│   ├── 00_utd19/
│   └── 01_sumo_foundation/
├── datasets/
│   ├── schemas/                # tracked
│   ├── metadata/               # tracked
│   ├── manifests/              # tracked hashes/versions
│   ├── raw/                    # NOT tracked; Drive/S3
│   └── processed/              # NOT tracked when large
├── experiments/                # cross-lab controlled experiments
├── infrastructure/
│   ├── docker/
│   └── aws/
├── configs/
├── secrets/                    # README only; real secrets excluded
├── .env.example
└── CLAUDE.md
```

## Promotion rule

Code starts in a paper lab. Only after the lab passes does reusable, independently tested logic move into `modules/`. This prevents the final system from becoming a pile of unverified paper code.
