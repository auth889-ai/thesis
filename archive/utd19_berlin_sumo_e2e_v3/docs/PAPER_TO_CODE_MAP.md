# Paper page/section → code/output

| Paper content | V3 lesson/code | Output |
|---|---|---|
| Pages 1–2: motivation and related scenarios | Notebook Lessons 1–2 | conceptual comparison |
| Pages 2–3: UTD19 and Table II | `preprocess_utd19.py` | `utd19_hourly.parquet`, audit |
| Pages 3–4: Berlin baseline and Tables III–IV | `download_berlin.py`, `preprocess_berlin.py`, `build_berlin_features.py` | actual and prediction feature tables |
| Pages 3–4: Step 1 predictions | `train_models.py`, `predict_berlin.py` | five-model comparison, RF predictions |
| Page 4: Step 2 network | `build_network.py` | Berlin SUMO network |
| Pages 4–5: randomTrips, TAZ, duarouter | `generate_candidates.py` | three candidate route sets |
| Page 5: routeSampler Figure 3 | `calibrate.py` | calibrated demand and mismatch report |
| Page 5: Table V | `train_models.py`, `evaluate.py` | paper vs independent metrics |
| Page 6: Figure 4 | `evaluate.py` | actual vs predicted plots |
| Page 6: GEH | `evaluate.py` | detector-hour GEH table and threshold summary |
| Pages 6–7: Figure 5 and final scenario | `run_simulation.py`, `evaluate.py` | 24-hour network trajectory and GUI bundle |
