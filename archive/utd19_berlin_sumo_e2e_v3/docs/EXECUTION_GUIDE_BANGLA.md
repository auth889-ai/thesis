# Execution Guide — তিনটি mode

## 1. Demo mode

Purpose: 10–30 minutes-এর মধ্যে code path এবং GUI যাচাই। এটি official full data নয়।

```bash
bash scripts/install_colab.sh
python -m src.pipeline --config config/demo.yaml --accept-auto-mapping
```

Expected GUI bundle:

```text
/content/utd19_berlin_e2e_demo/gui_bundle.zip
```

## 2. Subset mode

Purpose: official full UTD19 training data, কিন্তু 30 Berlin detectors এবং clipped network দিয়ে correctness certify করা।

```bash
python -m src.pipeline --config config/subset.yaml
```

Pipeline mapping gate-এ থামবে। `mapping_review.html` inspect করে accepted CSV তৈরি করে:

```bash
python -m src.pipeline \
  --config config/subset.yaml \
  --from-step 08_map_detectors
```

Unreviewed automatic acceptance:

```bash
python -m src.pipeline \
  --config config/subset.yaml \
  --from-step 08_map_detectors \
  --accept-auto-mapping
```

## 3. Full Colab mode

Purpose: official full UTD19 raw scan/preprocessing, whole Berlin, 24 hours; expensive SVM/Polynomial stages use disclosed row caps for ordinary Colab.

```bash
bash scripts/run_full_colab.sh
```

Mapping review gate applies here too.

## 4. Literal Full mode

Purpose: official full UTD19, all selected Berlin archive detectors, current full Berlin OSM, 24-hour experiment।

```bash
python -m src.pipeline --config config/full.yaml
```

This can require many hours, substantial disk/RAM, and a stable runtime. Free Colab may disconnect. Checkpoints allow resume while the same runtime disk survives.

## Save results to Drive

```python
from google.colab import drive
drive.mount('/content/drive')
```

```bash
python -m src.archive_workspace \
  --workspace /content/utd19_berlin_e2e_full \
  --destination /content/drive/MyDrive/utd19_berlin_e2e_full_backup
```

## Mac GUI

Download `gui_bundle.zip`, unzip, then:

```bash
cd gui_bundle
chmod +x run_gui.sh
./run_gui.sh
```

The full simulation should first run headlessly in Colab. `sumo-gui` is for viewing; it is not required for numerical output generation.
