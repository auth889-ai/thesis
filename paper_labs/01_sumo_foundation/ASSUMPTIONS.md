# Assumptions and Limitations

1. The four-arm scenario is a **unit-validation environment**, not evidence of city-scale performance.
2. The unit Max-Pressure implementation uses movement queue differences on a two-stage straight-only junction. Generalized stage selection, turn ratios, saturation-flow weighting and multi-intersection coordination are later work.
3. `lane.getLastStepHaltingNumber` is used as a queue proxy.
4. Spillback is reported as a documented proxy based on estimated queued vehicle length relative to incoming-lane length; it is not a physical detector jam-length measurement.
5. The official Bologna/Acosta run validates real-world scenario compatibility and reproducibility; Lab 01 does not claim to recalibrate Bologna or reproduce every historical validation statistic.
6. Results are invalid if controllers receive different demand realizations or safety transitions.
7. SUMO/Scenario upstream versions are recorded and pinned because current development changes over time.
