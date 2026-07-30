# How to learn from the outputs

Read the results in this order. Each step answers one question, and each one tells you what
to look at *next* if the number is bad. Do not start with the simulation — start with the data.

---

## Step 1 — Do I trust the input data?

**File:** `processed/utd19/utd19_audit.json`

```json
{"raw_rows": ..., "hourly_rows": ..., "cities": 40, "detectors": ..., "days": ...}
```

Ask yourself:

* `raw_rows` should be ~169,032,955. Less means the download or the CSV parse is truncated.
* `hourly_rows` will be far smaller — that is the 3–5 minute intervals collapsing into hours,
  *and* the error filter dropping rows. Roughly a 12:1 reduction plus the filter.
* `cities` should be 40.

**Then:** `processed/utd19/city_coverage.csv` — rows per city. You will see the data is very
unbalanced (some cities have far more detectors and days than others). That imbalance is a
real limitation of the paper worth writing about: a model trained on this is dominated by a
few well-instrumented cities.

---

## Step 2 — Is the model any good, and *why* that model?

**File:** `models/model_comparison.csv` and `models/paper_vs_reimplementation.csv`

The thing to understand: **SMAPE and MAE measure different failures.**

* MAE is in vehicles/hour. "On average I am wrong by 71 cars."
* SMAPE is a percentage. It punishes being wrong on *small* values very hard — being wrong by
  20 cars at 3 a.m. (when true flow is 30) hurts far more than being wrong by 20 at rush hour.

That is why the linear models look catastrophic (~72 %): they cannot represent the night/day
shape at all, so they are badly wrong exactly where SMAPE is most sensitive.

**Experiment to run:** open `models/training_protocol.json` and look at `feature_columns`.
Then retrain without the hour feature and watch SMAPE collapse. That single experiment teaches
you what the model is actually using.

---

## Step 3 — Does the prediction look like real traffic?

**File:** `reports/detector_<ID>_actual_vs_predicted.png` (one per detector)

This is the paper's Figure 4. What to look for, in order:

1. **Shape** — does the dashed prediction have a morning rise, a daytime plateau and an
   evening fall? If yes, the model learned the daily cycle. This is the paper's actual claim:
   *"the general traffic pattern is captured."*
2. **Peak height** — the prediction will usually be *lower* than the actual peaks. It is one
   model averaging over 40 cities, so it predicts a typical road, not this specific busy one.
3. **The odd day out** — one coloured line usually sits far below the others. Check the date:
   it is normally the weekend day, or a holiday. The model only sees weekday/weekend as a
   feature, so it cannot know about holidays.

**File:** `reports/actual_prediction_summary.csv` — the same thing as numbers (MAE, SMAPE per
detector). Sort it and look at the worst detector, then look at its PNG. Usually it is a
motorway ramp or a road whose real flow is far outside the training distribution.

---

## Step 4 — Did the calibration actually work?

This is where most people get confused, because **there are two different GEH numbers.**

**File:** `sumo/calibration/route_sampler_summary.json`

```json
"weighted_GEH_lt_threshold_percent": 100.0
```

This is the **linear program**. It says: "given the candidate routes, I found a combination
whose counts match the prediction." It is almost always ~100 %. It proves nothing about
traffic — it is pure arithmetic on paper.

**File:** `reports/geh_summary.csv` and `final_evaluation.json → GEH`

This is the **simulation**. It says: "after actually driving the cars, this many really
crossed the detectors." This is the honest number and the one the paper's 85 % claim refers to.

**If the second number is much lower than the first**, the demand did not physically fit.
Go to Step 5.

---

## Step 5 — Why did vehicles not arrive?

**File:** `final_evaluation.json → simulation_extraction.statistics`

Look at these four fields together:

| Field | Healthy | Trouble |
|---|---|---|
| `vehicles.inserted` vs `loaded` | close | inserted ≪ loaded |
| `vehicles.waiting` | near 0 at the end | thousands |
| `teleports.total` | small | large |
| `vehicleTripStatistics.speed` | 20–40 km/h | single digits |

`waiting` is the killer. It means SUMO wanted to insert a car but there was no room on its
first edge, so the car queued outside the network and never counted. Mean speed of 3 km/h with
a big `departDelay` means gridlock.

Causes, in order of likelihood:

1. **The network is too small for the demand.** (A clipped test network will always do this —
   arterial traffic has nowhere to go and the cut edges dead-end.)
2. `scale_counts` is too high in the config.
3. Too few candidate routes, so routeSampler reuses the same few routes thousands of times and
   piles every car onto one edge. Check `sumo/candidates/candidate_coverage_summary.json`.

**File:** `reports/network_24h_trajectory.png` — the Figure 5 equivalent. If the green
"running" line flatlines while the blue "predicted" line keeps climbing, that flat line *is*
the saturation point of your network.

---

## Step 6 — Watch it, and connect numbers to behaviour

```bash
cd gui_bundle && sumo-gui -c berlin.sumocfg
```

Do these three things deliberately:

1. **Colour by speed** (*View → Color vehicles by → speed*). Run to ~07:00 and watch red
   spread from the junctions outward. That is the jam forming, and it is the thing that turns
   your Step 4 GEH from 100 % into something worse.
2. **Find a monitored edge.** Open `sumo/mapping/mapping_accepted.csv`, take an `edge_id`, and
   use *Edit → Find* in the GUI. Right-click it → *Show parameter*. Compare its live count to
   the `predicted_count` for that hour in `sumo/calibration/edge_predictions.csv`. That single
   comparison is the whole paper in one screen.
3. **Watch the time shift.** The paper mentions it in Section V-C: routeSampler inserts cars to
   match a count, but they take time to travel, so the simulated curve lags the predicted one.
   You can see this directly in the trajectory plot.

---

## Step 7 — Prove you understand it

If you can answer these without looking, you know the experiment:

1. Why can `routeSampler` report 100 % GEH while the simulation reports 30 %?
2. Why does the paper need *coverage trips* in addition to `randomTrips.py`?
3. Why is the target `flow × lanes` rather than `flow`? (Hint: UTD19 `flow` is per-lane, Berlin
   `q_kfz` is per cross-section.)
4. Why is the train/test split done by whole detector instead of randomly by row?
5. Why do the linear models score ~72 % SMAPE while Random Forest scores ~17 %?
6. What would change if you fed the model a *sequence* of past hours instead of one row?
   (This is your LSTM contribution.)

---

## Step 8 — Your own experiments

Cheap changes with real thesis value, roughly in order of effort:

| Change | Where | What you learn |
|---|---|---|
| Drop the `hour` feature | `train_models.py` | How much of the score is just the daily cycle |
| `hourly_aggregation: median` | config | Sensitivity to outlier intervals |
| `target_mode: per_lane` | config | How the lane multiplication affects Berlin transfer |
| Add XGBoost | `train_models.py` | A stronger tabular baseline than Random Forest |
| Add LSTM on past-24h sequence | new module | The paper's own "Future Scope" |
| Raise `random_route_count` | config | Whether poor GEH was a route-diversity problem |
| Predict a different Berlin date | config | Whether the model generalises across days |

Everything except the last two only needs steps 03 and 09–20 rerun, because the SUMO half does
not depend on which model produced the numbers:

```bash
python -m src.pipeline --config <cfg> --from-step 03_train_models --force
```
