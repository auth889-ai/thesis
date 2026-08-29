# START HERE — Colab থেকে পুরো experiment চালানো

## 1. Notebook ও ZIP upload

Google Colab-এ `notebooks/UTD19_Berlin_SUMO_Full_End_to_End.ipynb` খুলুন এবং project ZIP-টি `/content`-এ upload করুন।

## 2. Install ও unzip

Notebook-এর installation/unzip cells চালান। Terminal style command:

```bash
unzip -q -o /content/utd19_berlin_sumo_e2e_v3.zip -d /content
cd /content/utd19_berlin_sumo_e2e_v3
bash scripts/install_colab.sh
```

## 3. আগে demo certification

```bash
python -m src.pipeline --config config/demo.yaml --accept-auto-mapping
```

এটি tiny bundled network-এ download ছাড়া code path, route calibration, headless SUMO, GEH, graphs এবং GUI bundle যাচাই করে।

## 4. Official-data subset certification

```bash
python -m src.pipeline --config config/subset.yaml
```

Pipeline detector mapping review-এ থামলে generated `mapping_review.html` inspect করুন। Manual review না করে শুধু exploratory run করতে:

```bash
python -m src.pipeline \
  --config config/subset.yaml \
  --from-step 08_map_detectors \
  --accept-auto-mapping
```

## 5. Whole-Berlin Colab mode

```bash
bash scripts/run_full_colab.sh
```

এই mode full official UTD19 raw data scan ও preprocess করে, কিন্তু SVM/Polynomial-এর training rows transparently cap করে যাতে Colab-এ চালানো তুলনামূলকভাবে বাস্তবসম্মত হয়। Mapping gate manual review চায়।

## 6. Literal full mode

```bash
bash scripts/run_full.sh
```

এটি পাঁচটি model family-র জন্য configured all-row training এবং whole-Berlin 24-hour simulation request করে। Free Colab-এ RAM/time limit অতিক্রম করতে পারে; server/workstation উপযুক্ত।

## 7. GUI

Final workspace-এর `gui_bundle.zip` Mac-এ download ও unzip করে:

```bash
chmod +x run_gui.sh
./run_gui.sh
```

## 8. Resume

Runtime disk টিকে থাকলে একই pipeline command আবার চালালে completed stages checkpoint দেখে skip হবে। Drive backup-এর command `docs/EXECUTION_GUIDE_BANGLA.md`-এ আছে।
