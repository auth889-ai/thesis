#!/usr/bin/env python3
"""Generate experiments/notebooks/OpenCity_CrossCity_Colab.ipynb — the cross-city generalization experiment.

Kept as a builder script (the pattern already used by build_predict_basicts_colab.py) so the
notebook is regenerable and reviewable as source rather than as a wall of JSON.
"""
from __future__ import annotations

import json
from pathlib import Path


def md(*lines):
    return {"cell_type": "markdown", "metadata": {}, "source": [l + "\n" for l in lines]}


def code(*lines):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
            "source": [l + "\n" for l in lines]}


CELLS = [
 md("# Cross-city generalization: city-specific vs OpenCity zero-shot vs fine-tuned",
    "",
    "**The claim this notebook exists to earn.** Having several dataset loaders proves the pipeline",
    "is portable. It says nothing about whether a model trained on one city forecasts well on",
    "another. A cross-city claim needs this comparison and nothing less:",
    "",
    "| arm | what it is |",
    "|---|---|",
    "| city-specific | GWNet / STAEformer trained on that city (our existing checkpoints) |",
    "| OpenCity zero-shot | the released pretrained weights, never shown this city |",
    "| OpenCity fine-tuned | those weights, adapted on the city's training split |",
    "",
    "Cities: **METR-LA**, **PEMS-BAY**, and at least one held-out third city supported by the",
    "official code. Until all three arms report on all three cities, no cross-city generalization",
    "claim is made.",
    "",
    "Official repo `HKUDS/OpenCity`, pinned at `eca64c9d9c65ff803d0f9d02c65e2544a0d2e96f`.",
    "**Pretrained weights are used as released — no foundation model is pretrained from scratch.**"),
 code("!nvidia-smi -L",
      "import torch; print('cuda:', torch.cuda.is_available())"),
 md("## 1. Repo and the pinned checkout"),
 code("import pathlib, os, json",
      "REPO = pathlib.Path('/content/thesis')",
      "if not REPO.exists():",
      "    !git clone -q --branch rebuild-120h https://github.com/auth889-ai/thesis.git {REPO}",
      "os.chdir(REPO)",
      "WS = pathlib.Path('/root/.dhakaflow/upstream'); WS.mkdir(parents=True, exist_ok=True)",
      "os.environ['DHAKAFLOW_WORKSPACE'] = str(WS)",
      "!python src/pipeline/upstream/fetch_upstream.py --name OpenCity",
      "OC = WS/'OpenCity'",
      "!git -C {OC} rev-parse HEAD"),
 code("!pip -q install fastdtw tslearn huggingface_hub"),
 md("## 2. Released weights and datasets",
    "",
    "Both come from the authors' own HuggingFace repos, named in their README. Everything lands on",
    "Drive, never on the laptop."),
 code("from google.colab import drive; drive.mount('/content/drive')",
      "DRIVE = pathlib.Path('/content/drive/MyDrive/dhakaflow/opencity'); DRIVE.mkdir(parents=True, exist_ok=True)",
      "from huggingface_hub import snapshot_download",
      "w = snapshot_download(repo_id='hkuds/OpenCity-Plus', local_dir=str(DRIVE/'weights'))",
      "print('weights ->', w)",
      "d = snapshot_download(repo_id='hkuds/OpenCity-dataset', repo_type='dataset', local_dir=str(DRIVE/'data'))",
      "print('data ->', d)",
      "!du -sh {DRIVE}/weights {DRIVE}/data"),
 code("# link the released assets into the upstream layout the authors' Run.py expects",
      "import shutil, os",
      "for name in ('data', 'model_weights'):",
      "    tgt = OC/name",
      "    src = DRIVE/('data' if name == 'data' else 'weights')",
      "    if tgt.is_symlink() or tgt.exists():",
      "        pass",
      "    os.system(f'ln -sfn {src} {tgt}_released')",
      "!ls {OC}"),
 md("## 3. Zero-shot evaluation",
    "",
    "The authors' own test mode, one dataset at a time as their README instructs. Set the target",
    "city in `conf/general_conf/pretrain.conf` (`dataset_use`) before each run."),
 code("os.chdir(OC)",
      "!python Run.py -mode test -model OpenCity -load_pretrain_path OpenCity-plus.pth \\",
      "    -batch_size 2 --embed_dim 512 --skip_dim 512 --enc_depth 6"),
 md("## 4. Fine-tuned arm",
    "",
    "Same released weights, adapted on the target city's training split. Record epochs and the",
    "split so the comparison against the city-specific arm is like for like."),
 code("# fill in per the authors' fine-tuning instructions for the chosen city",
      "# !python Run.py -mode ori -model OpenCity -load_pretrain_path OpenCity-plus.pth ..."),
 md("## 5. Record the comparison",
    "",
    "One row per (city, arm) so the three arms are directly comparable, with the pinned SHA and the",
    "exact command attached to every number."),
 code("os.chdir(REPO)",
      "!python src/pipeline/forecasting/crosscity_record.py --show"),
 md("## 6. Back to Drive"),
 code("import shutil",
      "OUT = pathlib.Path('/content/drive/MyDrive/dhakaflow/crosscity'); OUT.mkdir(parents=True, exist_ok=True)",
      "for f in (REPO/'results/forecasting').glob('crosscity*'):",
      "    shutil.copy2(f, OUT/f.name)",
      "print('copied to', OUT)"),
]


def main() -> None:
    nb = {"cells": CELLS,
          "metadata": {"kernelspec": {"display_name": "Python 3", "name": "python3"},
                       "language_info": {"name": "python"}, "accelerator": "GPU"},
          "nbformat": 4, "nbformat_minor": 0}
    out = Path(__file__).resolve().parent / "OpenCity_CrossCity_Colab.ipynb"
    out.write_text(json.dumps(nb, indent=1))
    print(f"wrote {out} ({len(CELLS)} cells)")


if __name__ == "__main__":
    main()
