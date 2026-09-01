# Asset Manifest

Generated UTC: `2026-09-01T09:25:52.672627+00:00`.

This manifest covers the active rebuild evidence path only. It excludes bulky SUMO XML outputs, raw datasets, model weights, and secrets.

| category | files | bytes |
|---|---:|---:|
| demand | 1 | 69725 |
| frozen-network | 1 | 17176962 |
| live-reference | 3 | 5929 |
| networking-results | 19 | 1807931 |
| nlp-results | 3 | 17732 |
| prediction-data | 16 | 5626899 |
| prediction-results | 2 | 2935 |
| routing-results | 5 | 64961 |

Restore/check command:

```bash
DHAKAFLOW_ASSET_ROOT=/path/to/DhakaFlow-assets bash download_assets.sh
```
