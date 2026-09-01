# nlp/ — incident text → routing event

Chain: post → 3-class classifier {incident, congestion, irrelevant} → Dhaka gazetteer place → nearest R1 edges (sumolib, 150 m) → travel-time factor (incident ×10, congestion ×3) → meanData weight XML consumed by `route/predictive_routing.py --arm predictive --weights`.

1. `python nlp/get_data.py` — downloads the REAL corpus (Dabiri & Heaslip, Mendeley `c3xvj5snvv` v1, CC BY 4.0, 51k US traffic tweets, 3 classes mapped 0→irrelevant 1→incident 2→congestion), verifies sha256, freezes `data/{train,val,test}.csv` + `data/MANIFEST.json`; also writes `data/dhaka_seed.csv` (150 hand-labelled Dhaka English/Banglish posts, used as the out-of-domain probe; automatic fallback corpus if the download fails).
2. `python nlp/train_classifier.py --augment-seed` — TF-IDF (word 1-2 + char 2-5) + LogisticRegression, 5-fold CV + frozen test → `results/classifier.{json,md}`, `results/tfidf_lr.joblib` (pure) and `results/tfidf_lr_dhaka_aug.joblib` (+ seed posts; Dhaka score by seed-fold CV, never on seen posts). `--model distilbert` fine-tunes distilbert-base-uncased with the HF Trainer (3 epochs) on GPU/MPS, else prints the Colab command.
3. `python nlp/event_feed.py --demo` — 20 example posts → `results/events.jsonl` (label, confidence, place, lat/lon, edges, factor, status ∈ {MAPPED, OUT_OF_NETWORK, NO_EDGE_IN_RADIUS, NO_LOCATION, IGNORED_*}); `--text "..."` / `--file posts.txt` for your own posts.
4. `python nlp/event_feed.py --to-weights nlp/results/weights_demo.xml --base route/results/static_s11_h900/edgedata.xml --events nlp/results/events.jsonl` — writes the weight table (`--begin/--end` limit the affected intervals, `--top-k` limits edges per event).
5. `gazetteer.json` — 44 places with aliases (Latin spellings + Bengali script); 35 resolve to R1 edges, 7 lie outside the R1 bbox (Mohakhali, Motijheel, …) and 2 (Nabisco, Mohammadpur) are inside the bbox but beyond the extracted roads — all reported honestly rather than snapped.

Every number in `results/classifier.md` regenerates from steps 1–2; all data are pinned by sha256 in `data/MANIFEST.json`.
