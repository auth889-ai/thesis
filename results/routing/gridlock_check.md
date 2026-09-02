# Demand-scale sensitivity check (static arm, seed 11, horizon 7200 s)

Question: is the non-monotonic behaviour between scale 0.20 and 0.25 caused by junction deadlock
(SUMO teleports) that `--ignore-junction-blocker` would remove?  Answer: no.

| scale | ignore-junction-blocker | inserted | arrived | unfinished | waiting to insert | mean TT s | mean time loss s | teleports | total veh-h |
|---|---|---|---|---|---|---|---|---|---|
| 0.20 | off | 4618 | 4368 | 250 | 182 | 831 | 490 | 88 | 1037 |
| 0.20 | 60 s | 4603 | 4364 | 239 | 197 | 824 | 482 | 76 | 1026 |
| 0.25 | off | 6000 | 6000 | 0 | 0 | 505 | 246 | 13 | 841 |
| 0.25 | 60 s | 6000 | 6000 | 0 | 0 | 497 | 238 | 2 | 828 |
| 0.30 | off | 6598 | 5861 | 737 | 602 | 1234 | 941 | 453 | 2425 |
| 0.30 | 60 s | 6399 | 5629 | 770 | 801 | 1216 | 921 | 576 | 2644 |

Reading: `--scale` < 1 makes SUMO drop a seed-dependent random subset of the 24,000 DUE trips, so
0.20 and 0.25 are *different trip mixes*, not nested ones; the 0.20 mix of seed 11 contains a
spillback that the 0.25 mix does not.  The junction-blocker option barely moves any number, so the
effect is spillback/trip-mix, not deadlock.  Consequence for the experiment design:

* the primary routing ladder is reported at **scale 0.25 with 10 paired seeds** (the scale-sweep
  choice, `SCALE_CHOICE.json`), where every arm sees exactly the same trip mix per seed;
* scale 0.20 (10 seeds, `results/routing/scale0.2/`) is kept as a sensitivity appendix — the sign of
  the reactive arm flips between the two scales, which is itself a result: en-route rerouting
  effects in this twin are regime-dependent and dominated by spillback dynamics;
* every comparison is paired by seed; unpaired cross-scale comparisons are not meaningful.

Regenerate: `DHAKAFLOW_SUMO_EXTRA="--ignore-junction-blocker 60" python pipeline/routing/predictive_routing.py --arm static --seed 11 --horizon 7200 --scale <s> --out <dir>` (and without the env var).
