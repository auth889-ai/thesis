# RQ1 — forecasting, made strong

How well can traffic speed be forecast 15, 30 and 60 minutes ahead in Los Angeles and in Dhaka, and why does Dhaka differ?

**Where things are:**
- the plan and the results: `docs/PAPER_MAP.md` (RQ1);
- the code: `core/ml/forecasting/transfer_dhaka/`;
- the results: `results/forecasting/rq1/`;
- the hashes: `evidence/forecasting/rq1/`.

**Licences** (`third_party/SOURCES.md`, "Forecasting comparison, RQ1"): Chronos, Chronos-Bolt, TimesFM 2.5 and BasicTS are all Apache-2.0.

```bash
research/forecasting_rq1/scripts/00_reproduce.sh     # each repository's own example first -> evidence/forecasting/reproduce/SUMMARY.json
research/forecasting_rq1/scripts/01_protocol_b.sh    # Protocol B, METR-LA and PEMS-BAY x seeds 11/23/37, every model; then every RQ1 stage
python -m core.ml.forecasting.transfer_dhaka.run rescore|dhaka|transfer|character|summary   # one stage again
DHAKAFLOW_NO_OBSERVATORY=1 python -m pytest tests/forecasting/test_rq1.py -q
```

**Steps:**
0. **Reproduce first.** Each repository's own example is run before its model is used:
   - Chronos-Bolt: `evaluate.py chronos-bolt` on two datasets of its own zero-shot config, against its published CSV.
   - TimesFM 2.5: its global-temperature example, against the output it ships.
   - Chronos-2: its README example, recorded only; no per-dataset table is published.
1. **Baselines.** Persistence; the historical average by time of day; the historical average by time of day and weekday (new). Everything comes from the train split.
2. **Models.** Chronos-Bolt-small, Chronos-2 and TimesFM 2.5 zero-shot, and our trained checkpoints where they apply.
3. **Data and metrics.**
   - METR-LA (207 roads) and PEMS-BAY (325 roads): Protocol B, a contiguous block of 120 test windows per seed, context 96.
   - DhaTraX: three sites, one recorded day each, rolling origin with a one-hour context.
   - Metrics: BasicTS's masked MAE, RMSE and MAPE.
4. **Unseen city.** Trees trained on METR-LA only, on speeds scaled by each window's own context mean, run unchanged on PEMS-BAY and Dhaka. They are compared with the same recipe trained at home. The six graph models cannot move: each is fixed to METR-LA's 207 sensors.
5. **Why Dhaka differs.** Stop-and-go share, congested share, coefficient of variation, and autocorrelation at 5–60 minutes, on weekday 06:00–19:00 days.

**Compute:** this Mac's CPU, measured first. One METR-LA seed takes under an hour (TimesFM about 14 series a second), under the 2-hour line in the cost rules, so no AWS.
