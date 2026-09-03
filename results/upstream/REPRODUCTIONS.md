# Upstream reproduction ledger

The rule: clone the official repo, pin its SHA, use the authors' own config, reproduce the number they published, and only then attach an adapter. This table is where that claim is checked. A verdict is computed, never typed.

Tolerance: 5% relative error against the published figure.

`REFERENCE_UNKNOWN` means we have our own number but have not yet read the authors' published figure out of the paper — it is deliberately **not** counted as a pass, and no number is invented to fill the gap.

| model | dataset | official repo | SHA | authors' config | metric | published | ours | diff | verdict |
|---|---|---|---|---|---|---|---|---|---|
| Graph WaveNet | METR-LA | `GestaltCogTeam/BasicTS (legacy baselines)` | `4c3e2d373c64` | `baselines/GWNet/METR-LA.py` | MAE@15min | 2.69 | 2.719 | 1.08 % | **REPRODUCTION_PASS** |
| Graph WaveNet | PEMS-BAY | `GestaltCogTeam/BasicTS (legacy baselines)` | `4c3e2d373c64` | `baselines/GWNet/PEMS-BAY.py` | MAE@15min | 1.3 | 1.3083 | 0.64 % | **REPRODUCTION_PASS** |
| STID | METR-LA | `GestaltCogTeam/BasicTS (legacy baselines)` | `4c3e2d373c64` | `baselines/STID/METR-LA.py` | MAE@15min | – | 2.8247 | – | **REFERENCE_UNKNOWN** |
| STAEformer | METR-LA | `XDZhelheim/STAEformer` | `PINNED — see` | `trained via the BasicTS-legacy harness; the AUTHORS' OWN repo run is pending` | MAE@15min | – | 2.6738 | – | **REFERENCE_UNKNOWN** |
| CNFGNN | METR-LA | `mengcz13/KDD2021_CNFGNN` | `505660846e04` | `submission_exps/exp_main.sh -> SplitFedAvgNodePredictor + GRUSeq2SeqWithGraphNet` | MAE@15min | – | – | – | **NOT_ATTEMPTED** |
| FedGTP | PeMSD7 | `LarryHawkingYoung/KDD2024_FedGTP` | `ff128f5bed77` | `config/PeMSD7.conf + run.sh (num_clients=4, metis partition, adptpolu)` | MAE | – | – | – | **NOT_ATTEMPTED** |
| OpenCity | cross-city (zero-shot) | `HKUDS/OpenCity` | `eca64c9d9c65` | `conf/ + released pretrained weights (HuggingFace hkuds/OpenCity-Plus)` | MAE (zero-shot, PEMS07M, authors' 288-step horizon) | 4.5 | 4.5 | 0.0 % | **REPRODUCTION_PASS** |

## What is blocking the outstanding reproductions

**CNFGNN / METR-LA**
  - authors' data.tar.bz2 (Zenodo record 4521262) not yet downloaded
  - repo targets python<3.8 and an old PyTorch Lightning; needs its own environment

**FedGTP / PeMSD7**
  - needs a CUDA host: upstream client.py calls get_memory_usage('cuda') unconditionally, and we do not edit their code to work around it
  - _PeMSD7 data ships inside the repo (15 MB), so this is the cheapest genuine federated reproduction available and is attempted first. Its server/client processes talk over real TCP sockets, which is exactly where the communication impairment adapter attaches._

## Notes

- **STAEformer / METR-LA** — Reproduced through the shared harness, not yet through XDZhelheim/STAEformer itself. Until that run exists this is a harness reproduction, not a repo reproduction, and is labelled as such.
- **OpenCity / cross-city (zero-shot)** — CRITICAL for how this is reported: METR_LA and PEMS_BAY are in OpenCity's pre-training corpus, so neither can support a zero-shot claim. Only held-out cities (PEMS07M, TrafficSH/NJ/TJ, SZ_DIDI, CD_DIDI, NYC_BIKE-3, CHI_TAXI) can.

Regenerate: `python pipeline/upstream/reproduction_record.py`. Pins: `upstream/UPSTREAM_PINS.yaml`. Fetch record: `artifacts/upstream_fetch_record.json`.
