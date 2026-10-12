# core/ml/nlp — traffic incident text

A 3-class classifier for short traffic texts {incident, congestion, irrelevant}. A classified report is placed on
the Dhaka road network and becomes a slowdown event that routing can use. This is supporting work; none of RQ1–RQ6
depends on it. Its routing experiment is `core/simulation/closed_loop/protocols/chains/incident_scenario.py`.

## Papers and data
- **Data:** Dabiri, S. (2018), "Tweets with traffic-related labels for developing a Twitter-based traffic information
  system", Mendeley Data v1, doi:10.17632/c3xvj5snvv.1, CC BY 4.0. Companion paper: Dabiri & Heaslip (2019),
  *Expert Systems with Applications* 118, 425–439. As stated in `get_data.py`'s docstring; **not recorded in third_party/SOURCES.md**.
- **Out-of-domain check:** 150 hand-written Dhaka seed posts (`data/nlp/dhaka_seed.csv`), ours.
- **Models:** scikit-learn TF-IDF + logistic regression; `distilbert-base-uncased` through Hugging Face. Versions and
  licences are not recorded in third_party/SOURCES.md.

## Which file implements which part
| File | Part |
|---|---|
| `get_data.py` | Downloads the labelled corpus, maps its labels to ours, and freezes the train/val/test splits (`data/nlp/` + `MANIFEST.json`). |
| `train_classifier.py` | 5-fold stratified CV on train+val, then one score on the frozen test set: accuracy, macro-F1, per-class F1, confusion matrix. Also probes the Dhaka seed set. |
| `event_feed.py` | Text → event: classify, geolocate against the Dhaka gazetteer (`gazetteer.json`), map to R1 road edges, emit a slowdown. |

## Substitutions and why
- **The corpus is not from Dhaka**, so the Dhaka seed posts are scored separately and reported beside the test score.
- **The gazetteer is Dhaka's.** Another city needs its own before `event_feed.py` can place a report there.

## Tests
`backend/tests/rebuild/test_rebuild.py`:
- `test_incident_helpers`;
- `test_event_feed_maps_karwan_bazar_to_r1_edges`, skipped when the trained classifier, which is git-ignored, is absent;
- `test_gazetteer_all_inside_or_labelled`.

## Results
`results/nlp/classifier.json` and `classifier.md`: every model's CV and frozen-test scores and the Dhaka-seed scores;
the test set is described in `data/nlp/MANIFEST.json`.
