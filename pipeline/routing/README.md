# pipeline/routing/

Predictive route-optimization harness for the active thesis path.

Main command:

```bash
python pipeline/routing/run_arms.py --seeds 11,12,13 --horizon 3600
python pipeline/routing/stats.py
python pipeline/routing/decision_guard.py --horizon 3600 --reference reactive
```

Arms are static, reactive, predictive, DUE, and DSO. All arms must use the same
Dhaka R1 network, demand, seeds, and horizon; only the routing rule changes.

The decision guard is the runtime honesty rule: an intervention is accepted only
when network-wide metrics improve across paired seeds. DUE/DSO are offline
benchmarks, not live actions.
