# route/

Predictive route-optimization harness for the active thesis path.

Main command:

```bash
python route/run_arms.py --seeds 11,12,13 --horizon 3600
python route/stats.py
```

Arms are static, reactive, predictive, DUE, and DSO. All arms must use the same
Dhaka R1 network, demand, seeds, and horizon; only the routing rule changes.

