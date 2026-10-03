# Imputation on METR-LA: point, 25% of observed points, seed 42

chronological 70/10/20 on non-overlapping windows; hidden points only; outages never scored; budget: 60 epochs on the laptop (paper: 300 x 300 batches).

| method | MAE on hidden points | MAPE % | published MAE (paper, point missing) |
|---|---|---|---|
| mean | 7.5134 | 24.786 | 7.52 |
| linear | 2.4793 | 5.731 | – |
| last | 2.925 | 6.83 | – |
| ImputeFormer | 2.4181 | 6.023 | 1.8 |
