# QA preparation: two results the examiners will ask about (read-only note, 2026-10-11)

Every number here is read from a saved results file; the file and the key (or line) to open are given. Where the cause is not
established, it says so.

## 1. Why does "alert + signal pre-emption" save a median 3 s when "alert only" saves 26 s? (RQ3, Dhaka density)

**Where the numbers are.** `results/emergency/dhaka/rq2/summary.json`: `saved.alert["1"].dhaka` (line 350) and
`saved.alert_preemption["1"].dhaka` (line 624): every car equipped, scale 0.78 ("Dhaka density"), 10 seeds (11-20).

| Arm | Mean saving, s | Median saving, s | 25th / 75th percentile, s | Runs slower than no alert |
|---|---|---|---|---|
| alert only | 60.4 | **26.0** | −17.0 / 39.8 | 4 of 10 |
| alert + pre-emption | 18.3 | **3.0** | −21.0 / 32.5 | 4 of 10 |

**Per seed** (ambulance travel time, s; `results/emergency/dhaka/rq2/runs/dhaka/dhaka_density/<arm>_its_g5_p100_s<seed>_x0.78/metrics.json`,
key `ambulance.travel_time_s`; `no_alert_s<seed>_x0.78` for the siren-only run):

| Seed | no alert | alert only | alert + pre-emption | saving: alert | saving: alert + pre-emption |
|---|---|---|---|---|---|
| 11 | 292 | 269 | 202 | 23 | 90 |
| 12 | 343 | 578 | 293 | −235 | 50 |
| 13 | 898 | 507 | 508 | 391 | 390 |
| 14 | 299 | (SUMO stopped) | 596 | — | −297 |
| 15 | 226 | 490 | 487 | −264 | −261 |
| 16 | 561 | (SUMO stopped) | 503 | — | 58 |
| 17 | 737 | 624 | 503 | 113 | 234 |
| 18 | 608 | 760 | 830 | −152 | −222 |
| 19 | 241 | 545 | 231 | −304 | 10 |
| 20 | 348 | 573 | 303 | −225 | 45 |

(A missing value is a run in which SUMO 1.27.1's bluelight device crashed, recorded in `evidence/emergency/dhaka/sumo_bluelight_crash.json`;
the summary's statistics use the 10 seeds whose paired runs finished, so its seed set is not exactly this table's.)

**What the table shows.** The two arms are not consistently ordered: pre-emption is better on seeds 11, 12, 17, 19 and 20, worse on
14 and 18, equal on 13 and 15. Both arms have a wide spread (the alert's 25th percentile is a loss of 17 s) and 4 slower runs each.
The medians 26 s and 3 s are the middle of ten noisy numbers; the difference between them is far inside the spread and is not a
reliable effect. The honest statement is: **at Dhaka density neither arm gives a reliable saving**, which is what the everyday
sentence says (`summary.json` `plain.alert_reliable: false`, `plain.not_every_time: true`).

**What the data says about the cause** (`summary.json` `why_dhaka`, Spearman correlations over 80 paired runs):
- The saving rises with how long the siren-only ambulance stood blocked (rho 0.29, 95 % CI 0.05 to 0.50): the alert helps when
  there was a blockage to clear.
- It is not clearly related to the free width ahead (rho −0.12, CI −0.37 to +0.13), to the queue at the signals (rho −0.06,
  CI −0.29 to +0.17), or to the share of alerted cars that moved aside (rho −0.16, CI −0.38 to +0.08).
- The signals on this route: 2 signalised junctions (`service.scenario`, `core/simulation/ambulance/service.py:57-103`). Pre-emption
  changes a phase only when the alert reaches a junction within `ahead_m` (`service.py:197-207`) and then within the safety limits of
  the copied state machine (`core/simulation/signals/preemption/phases.py:62-101`). With two junctions and a request that may arrive
  while the ambulance is already queued behind cars that cannot move, the extra green cannot shorten the queue; the ambulance's time
  is set by the cars in front, which is what the siren-blocked correlation says.
- **Cause of the 3 s vs 26 s gap: not established.** No run-level variable separates the two arms, and the gap is inside the spread.
  Say so. What is established (RQ2 at generated densities, `summary.json` `findings.why`, 400 paired runs): the saving falls with
  free width (rho −0.16, CI −0.25 to −0.06) and rises with the queue at the signals (rho 0.18, CI 0.08 to 0.27).

**If asked "so does the alert help?"** "At the counted Dhaka density, not reliably: a median 26 s with the alert alone and 3 s with
pre-emption, but a quarter of the runs are slower, and the two arms swap places from seed to seed. Signal control alone (Q-learning)
gives the ambulance 188 s against 292 s on seed 11, at a cost of 794 against 532 vehicle-hours for everyone else
(`docs/LIVE_RUNS.md`, `summary.json` `qlearning_dhaka`)."

## 2. Why is rerouting on current travel times (1 047 s) worse than no steering (964 s) in the live twin?

**Where the numbers are.** `evidence/live_twin/steer_compare.json` (sha256 `be0ae1f3…`), `summary` rows "off" (line 18) and
"current" (line 29); per seed in `rows`. The cohort mean is the mean trip time of every vehicle that departed between minute 15 and
minute 60, a vehicle still driving at minute 60 counting its time so far (`scripts/live_twin/steer_compare.py`, `one()`).

| Seed | no steering, s | current travel times, s | difference, s | routes changed by the "current" arm |
|---|---|---|---|---|
| 11 | 1 019.5 | 1 018.2 | −1.3 | 10 |
| 12 | 726.5 | 879.9 | +153.4 | 12 |
| 13 | 1 236.3 | 1 265.9 | +29.6 | 11 |
| 14 | 870.4 | 883.8 | +13.4 | 8 |
| 15 | 965.8 | 1 186.3 | +220.5 | 7 |
| mean | 963.7 | 1 046.8 | **+83.1 ± 98.3** (1 of 5 better) | 9.6 |

(The per-seed values are `rows[*].cohort_mean_s`; the differences are the paired values the summary averages.)

**What the data says.**
- The "current" arm asks SUMO to reroute the informed 30 % of vehicles every simulated minute on the edges' current travel times
  (`core/simulation/live_twin/session.py:283-304`, `rerouteTraveltime(vid, currentTravelTimes=True)` at line 298). It changed only
  7-12 routes per run: on this corridor the current-time shortest path is almost always the route the vehicle already has, so the
  arm barely acts.
- With so few changes, a difference of 83 s in the cohort mean cannot come from those vehicles' own trips. It comes from the whole
  simulation drifting: a reroute at minute 20 changes the order of cars at a junction, and at a density where about 64 % of the
  cohort is still driving at minute 60 (`summary.off.still_driving_mean` 1 572 of about 2 450), the gridlock then forms earlier or
  later. The seed-to-seed spread (sd 98 s, 2 of 5 seeds within ±15 s) says the same.
- Statistically: mean +83 s, standard error about 44 s over 5 seeds; a 95 % interval covers 0. **"Worse" is not established;
  "not better" is.** The same holds for the three forecasters (−36 to −12 s, sd 92-124 s).
- **Cause of the sign: not established.** What is established is the mechanism of the small effect (few reroutes, a gridlocked
  corridor) and that no arm is reliably different from no steering.

**If asked "so is the forecast useful for routing?"** "In this corridor at this density, no arm is reliably better than not
steering: the differences are smaller than the spread between seeds, and two thirds of the trips are still in the jam at the end
either way. RQ2 found the same in Los Angeles against reactive rerouting (−0.9 %, 95 % CI −2.2 to +0.3, `docs/PAPER_MAP.md`)."
