# Static-arm demand-scale sweep (seed 11, horizon 7200 s, demand ends ~4800 s)

| scale | loaded | inserted | arrived | unfinished @ horizon | unfinished % ins | teleports | teleports % ins | mean time loss s | mean TT s | total veh-h | wall s | pass |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.25 | 24000 | 6000 | 6000 | 0 | 0.0 | 13 | 0.22 | 245.6 | 504.5 | 840.9 | 39.7 | yes |
| 0.28 | 24000 | 6720 | 6322 | 398 | 5.9 | 253 | 3.76 | 525.0 | 790.9 | 1751.1 | 63.4 | no |
| 0.3 | 24000 | 6598 | 5861 | 737 | 11.2 | 453 | 6.87 | 941.4 | 1233.8 | 2425.3 | 79.4 | no |
| 0.32 | 24000 | 7677 | 7315 | 362 | 4.7 | 361 | 4.70 | 733.4 | 1005.5 | 2182.3 | 74.2 | no |
| 0.35 | 24000 | 8393 | 6328 | 2065 | 24.6 | 685 | 8.16 | 446.8 | 705.8 | 3093.4 | 92.4 | no |
| 0.45 | 24000 | 10275 | 7024 | 3251 | 31.6 | 1182 | 11.50 | 841.2 | 1105.9 | 4547.0 | 128.7 | no |
| 0.584 | 24000 | 10865 | 7276 | 3589 | 33.0 | 1350 | 12.43 | 805.2 | 1064.2 | 4924.8 | 144.6 | no |

Choice: **0.25** - largest scale with unfinished <= 2% and teleports <= 1% of inserted at horizon 7200 s (congested but not gridlocked); passing scales: [0.25]

Criteria: unfinished/inserted <= 0.02, teleports/inserted <= 0.01. Run dirs `results/routing/scale_<scale>_s<seed>_h<H>/metrics.json`.
