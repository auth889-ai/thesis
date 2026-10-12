# One alert run slower than the siren alone, inspected (2026-10-08)

The run: alert, ITS-G5, 100 % equipped, seed 15, demand ×0.5 (`results/emergency/dhaka/rq2/runs/dhaka/generated/alert_its_g5_p100_s15_x0.5/`).

| Arm | Ambulance travel time | Waiting | Seconds blocked | Teleports |
|---|---|---|---|---|
| Siren only, same seed | 211 s | 24 s | 25 | 0 |
| This run | 482 s | 293 s | 297 | 1 |

**What the re-run showed.** The same run was repeated with a log of the ambulance whenever it moved below 2 m/s.
- From about 950 s to about 1240 s simulated, the ambulance stood **inside junction 2478209117** (internal lane `:2478209117_2`, lane position about 1 m).
- **Most of that time no vehicle was ahead of it within 50 m.** The vehicles that did appear ahead were moving, at 4.8–25 m/s.

**Reading:** the ambulance was held by the junction itself, not by a queue in front of it. The most likely cause is a right-of-way conflict with crossing traffic. That cause was not traced further, so it is not stated as the cause.

**How it is counted:** this run and any like it stay in every mean. They are counted in the summary's "slower_runs" and in "The finding".
