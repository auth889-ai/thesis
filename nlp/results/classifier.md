# Traffic-text classifier — {incident, congestion, irrelevant}

Data: `nlp/data/MANIFEST.json` (source: REAL; test n = 10226, frozen held-out).

| model | CV acc (5-fold) | CV macro-F1 | **test acc** | **test macro-F1** | F1 incident | F1 congestion | F1 irrelevant | Dhaka-seed acc / mF1 (n=150) | train s |
|---|---|---|---|---|---|---|---|---|---|
| tfidf_lr | 0.9758 ± 0.0014 | 0.9697 ± 0.0017 | **0.9764** | **0.9705** | 0.9738 | 0.9516 | 0.9860 | 0.633 / 0.608 | 50.8 |
| tfidf_lr_dhaka_aug | 0.9747 ± 0.0010 | 0.9683 ± 0.0015 | **0.9768** | **0.9712** | 0.9744 | 0.9534 | 0.9858 | 0.873 / 0.873 | 58.1 |
| distilbert | – | – | **0.8224** | **0.5896** | 0.7977 | 0.0000 | 0.9711 | 0.540 / 0.434 | 17.6 |

Confusion matrix (tfidf_lr, test; rows = true, cols = pred; order ['incident', 'congestion', 'irrelevant']):

```
   incident   3404     45     40
 congestion     53   1534     30
 irrelevant     45     28   5047
```

Confusion matrix (tfidf_lr_dhaka_aug, test; rows = true, cols = pred; order ['incident', 'congestion', 'irrelevant']):

```
   incident   3409     39     41
 congestion     53   1535     29
 irrelevant     46     29   5045
```

Confusion matrix (distilbert, test; rows = true, cols = pred; order ['incident', 'congestion', 'irrelevant']):

```
   incident   3384      0    105
 congestion   1517      0    100
 irrelevant     94      0   5026
```

Dhaka-seed column: `tfidf_lr`/`distilbert` = zero-shot (seed never trained on); `tfidf_lr_dhaka_aug` = 5-fold over the seed with the real corpus + 4/5 seed in training.

Regenerate: `python nlp/get_data.py && python nlp/train_classifier.py --augment-seed` (`--model distilbert` for the transformer row).
