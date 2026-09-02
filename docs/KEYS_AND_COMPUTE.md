# Keys And Compute Checklist

This is the key plan for the strong 120-hour build. Do not paste secrets into
chat or commit them to git. Put them in `dhakaflow/.env` locally, or in Colab
secrets / notebook environment variables.

## Strong Build Keys

| Credential | Env var / access | Required for | Used in thesis as |
|---|---|---|---|
| Google Maps Platform | `GOOGLE_MAPS_API_KEY` | live pipeline/routing/travel-time reference, weather/reference context, demo comparison | live reference and sanity check, not ML training data |
| Road traffic provider | `ROAD511_API_KEY` or provider equivalent | live incidents, live camera metadata/snapshots if available | provider integration + incident evidence; Dhaka validation only if the provider is actually Dhaka |
| Google Colab Pro | browser login: `anastasiasaat81@gmail.com` | GPU training for BasicTS/STGNN models | compute, not an API key |
| Google Drive 3 TB | same Google account | datasets, checkpoints, logs, large artifacts | remote artifact store with sha256 manifests |
| AWS | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, region config | parallel SUMO sweeps, MOSAIC sweeps, long CPU jobs | compute lane for reproducible paired-seed experiments |
| Hugging Face | `HF_TOKEN` or `HUGGING_FACE_HUB_TOKEN` | Chronos/Transformer downloads, DistilBERT model pulls if needed | model/data access for forecasting/NLP comparisons |
| Kaggle | `~/.kaggle/kaggle.json` or `KAGGLE_USERNAME`, `KAGGLE_KEY` | traffic datasets such as BNVD/Poribohon-style downloads when hosted there | dataset acquisition with license/sha256 record |
| Anthropic / Claude | `ANTHROPIC_API_KEY` | final grounded copilot/explanation over run logs | explanation layer only; not the controller |

## Google API Rules

Use Google Routes for reference/comparison only:

- compare SUMO pipeline/routing/travel-time estimates against a live commercial reference
- display pipeline/routing/reference information in the demo with correct attribution
- avoid using Google Routes responses as a stored ML training dataset
- set API restrictions to only the APIs used by this project
- set daily quota/budget alerts before running loops

Recommended enabled APIs:

- Routes API
- Maps JavaScript API if the demo uses Google Maps
- Geocoding API only if the demo needs address lookup
- Weather API only if weather context is used

## Where Secrets Go

Local file:

```bash
dhakaflow/.env
```

Example:

```bash
GOOGLE_MAPS_API_KEY=...
ROAD511_API_KEY=...
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=us-east-1
HF_TOKEN=...
ANTHROPIC_API_KEY=...
```

Never commit:

- `dhakaflow/.env`
- raw keys copied into notebooks
- Drive share links that expose private files without intent
- AWS credential files

## Verification

Presence check:

```bash
python scripts/verify_keys.py
```

Live verification, where safe:

```bash
python scripts/verify_keys.py --live
```

Google Routes is billed per request, so the verifier reports it as present but
does not spend quota. Run the live Google capture deliberately:

```bash
python pipeline/forecasting/run_live_capture.py
```

## Colab Workflow

Colab Pro is controlled from the browser, not by an API key.

1. Sign into Chrome/Colab with `anastasiasaat81@gmail.com`.
2. Open `notebooks/Predict_BasicTS_Colab.ipynb`.
3. Mount Drive.
4. Set runtime to GPU.
5. Run the notebook cells one model at a time: STID, Graph WaveNet, DCRNN, then
   STAEformer if time remains.
6. Save checkpoints/logs/results under `/MyDrive/dhakaflow/`.
7. Pull only small CSV/JSON/Markdown summaries back into git.

## Key Priority

For the strongest system, activate in this order:

1. Colab Pro + Drive: starts model training.
2. Google Maps key: live reference and demo comparison.
3. Road provider key: live incident/camera evidence.
4. AWS credentials: parallel SUMO/MOSAIC sweeps.
5. HF token: Chronos/DistilBERT/model downloads.
6. Kaggle token: extra datasets if needed.
7. Anthropic key: final grounded explanation layer.

