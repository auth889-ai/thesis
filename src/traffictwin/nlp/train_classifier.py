#!/usr/bin/env python3
"""Train / evaluate the 3-class traffic-text classifier {incident, congestion, irrelevant}.

    python -m traffictwin.nlp.train_classifier                      # TF-IDF (word+char n-grams) + LogisticRegression
    python -m traffictwin.nlp.train_classifier --augment-seed       # + the same model with the 150 Dhaka seed posts added
    python -m traffictwin.nlp.train_classifier --model distilbert   # distilbert-base-uncased, HF Trainer, 3 epochs

Baseline protocol: 5-fold stratified CV on TRAIN+VAL (accuracy, macro-F1 mean +- sd), then refit on
TRAIN+VAL and score the frozen held-out TEST once: accuracy, macro-F1, per-class P/R/F1, confusion
matrix. Also probes the out-of-domain Dhaka seed set (data/nlp/dhaka_seed.csv) if present.

Outputs: results/nlp/classifier.json (all models, keyed by name), results/nlp/classifier.md (table),
         results/nlp/tfidf_lr.joblib (baseline pipeline) / results/nlp/distilbert/ (fine-tuned model).

DistilBERT runs locally only if `transformers` imports AND (a GPU/MPS is present OR the training set
is <= --max-train rows OR --force); otherwise it prints the Colab command and exits 0.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
from traffictwin.paths import REPO
DATA = REPO / "data/nlp"
RESULTS = REPO / "results/nlp"
LABELS = ["incident", "congestion", "irrelevant"]
L2I = {l: i for i, l in enumerate(LABELS)}


def load_splits() -> dict[str, pd.DataFrame]:
    out = {}
    for name in ["train", "val", "test"]:
        p = DATA / f"{name}.csv"
        if not p.exists():
            sys.exit(f"missing {p}: run `python -m traffictwin.nlp.get_data` first")
        df = pd.read_csv(p).dropna(subset=["text", "label"])
        df = df[df["label"].isin(LABELS)]
        out[name] = df.reset_index(drop=True)
    p = DATA / "dhaka_seed.csv"
    if p.exists():
        out["dhaka_seed"] = pd.read_csv(p).dropna(subset=["text", "label"]).reset_index(drop=True)
    return out


def score(y_true, y_pred) -> dict:
    from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score,
                                 precision_recall_fscore_support)
    p, r, f, s = precision_recall_fscore_support(y_true, y_pred, labels=LABELS, zero_division=0)
    return {
        "n": int(len(y_true)),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, labels=LABELS, average="macro", zero_division=0)),
        "per_class": {lab: {"precision": float(p[i]), "recall": float(r[i]), "f1": float(f[i]), "support": int(s[i])}
                      for i, lab in enumerate(LABELS)},
        "confusion_matrix": {"labels": LABELS,
                             "rows_true_cols_pred": confusion_matrix(y_true, y_pred, labels=LABELS).tolist()},
    }


# ----------------------------------------------------------------------------- TF-IDF + LR
def build_tfidf_lr(C: float = 4.0):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import FeatureUnion, Pipeline
    feats = FeatureUnion([
        ("word", TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True, lowercase=True,
                                 token_pattern=r"(?u)\b\w+\b|#\w+|@\w+")),
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=3, sublinear_tf=True,
                                 lowercase=True, max_features=300_000)),
    ])
    clf = LogisticRegression(C=C, max_iter=3000, class_weight="balanced", solver="lbfgs")
    return Pipeline([("features", feats), ("clf", clf)])


def run_tfidf_lr(sp: dict[str, pd.DataFrame], a, augment: bool = False) -> dict:
    """augment=True: Dhaka seed posts are added to the fit set (domain adaptation). The OOD number is
    then a 5-fold CV over the seed (real corpus always in training, held-out seed fold scored) so the
    reported Dhaka accuracy is never measured on posts the final model saw."""
    import joblib
    from sklearn.base import clone
    from sklearn.model_selection import StratifiedKFold

    name = "tfidf_lr_dhaka_aug" if augment else "tfidf_lr"
    real = pd.concat([sp["train"], sp["val"]], ignore_index=True)
    seed = sp.get("dhaka_seed") if augment else None
    fit = pd.concat([real, seed], ignore_index=True) if seed is not None else real
    X, y = fit["text"].tolist(), fit["label"].to_numpy()
    pipe = build_tfidf_lr(a.C)

    t0 = time.time()
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=20260901)
    accs, f1s = [], []
    for k, (tr, te) in enumerate(cv.split(X, y)):
        m = clone(pipe).fit([X[i] for i in tr], y[tr])
        s = score(y[te], m.predict([X[i] for i in te]))
        accs.append(s["accuracy"]); f1s.append(s["macro_f1"])
        print(f"[{name}] fold {k}: acc={s['accuracy']:.4f} macroF1={s['macro_f1']:.4f}")
    cv_res = {"folds": 5, "accuracy_mean": float(np.mean(accs)), "accuracy_sd": float(np.std(accs)),
              "macro_f1_mean": float(np.mean(f1s)), "macro_f1_sd": float(np.std(f1s))}

    pipe.fit(X, y)
    test = score(sp["test"]["label"].to_numpy(), pipe.predict(sp["test"]["text"].tolist()))
    res = {"model": name, "features": "word 1-2gram + char_wb 2-5gram TF-IDF (sublinear)",
           "classifier": f"LogisticRegression(C={a.C}, class_weight=balanced)",
           "fit_set": "train+val" + ("+dhaka_seed" if seed is not None else ""),
           "n_fit": int(len(fit)), "cv_train_val": cv_res, "test": test,
           "train_seconds": round(time.time() - t0, 1)}
    if seed is not None:
        ys, preds = seed["label"].to_numpy(), np.empty(len(seed), dtype=object)
        for tr, te in StratifiedKFold(n_splits=5, shuffle=True, random_state=20260901).split(seed["text"], ys):
            m = clone(pipe).fit(real["text"].tolist() + seed["text"].iloc[tr].tolist(),
                                np.concatenate([real["label"].to_numpy(), ys[tr]]))
            preds[te] = m.predict(seed["text"].iloc[te].tolist())
        res["ood_dhaka_seed"] = score(ys, preds)
        res["ood_dhaka_seed"]["protocol"] = "5-fold over the seed; real corpus + 4/5 seed in training, 1/5 scored"
    elif "dhaka_seed" in sp:
        res["ood_dhaka_seed"] = score(sp["dhaka_seed"]["label"].to_numpy(),
                                      pipe.predict(sp["dhaka_seed"]["text"].tolist()))
        res["ood_dhaka_seed"]["protocol"] = "zero-shot: seed never seen in training"
    RESULTS.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipe, RESULTS / f"{name}.joblib")
    res["artifact"] = f"results/nlp/{name}.joblib"
    return res


# ----------------------------------------------------------------------------- DistilBERT
COLAB_CMD = """# --- run on Google Colab (T4, ~20 min) ---
!pip -q install transformers datasets accelerate scikit-learn
from google.colab import drive; drive.mount('/content/drive')
!git clone <YOUR_REPO_URL> thesis && cd thesis && python -m traffictwin.nlp.get_data
!cd thesis && python -m traffictwin.nlp.train_classifier --model distilbert --epochs 3 --batch-size 32 --force
# then copy results/nlp/classifier.json, classifier.md and results/nlp/distilbert/ back into the repo
"""


def run_distilbert(sp: dict[str, pd.DataFrame], a) -> dict | None:
    try:
        import torch
        import transformers
        from transformers import (AutoModelForSequenceClassification, AutoTokenizer, Trainer,
                                  TrainingArguments, DataCollatorWithPadding)
        from datasets import Dataset
    except Exception as e:  # noqa: BLE001
        print(f"[distilbert] transformers/datasets not importable ({e!r}); run on Colab:\n{COLAB_CMD}")
        return None

    device = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
    train = sp["train"]
    if a.max_train and len(train) > a.max_train:
        train = train.sample(n=a.max_train, random_state=20260901).reset_index(drop=True)
    if device == "cpu" and len(train) > 4000 and not a.force:
        print(f"[distilbert] no GPU/MPS and {len(train)} training rows: too slow locally. Colab command:\n{COLAB_CMD}")
        return None
    print(f"[distilbert] device={device} transformers={transformers.__version__} n_train={len(train)} "
          f"n_val={len(sp['val'])} epochs={a.epochs} max_len={a.max_len}")

    tok = AutoTokenizer.from_pretrained(a.hf_model)
    def enc(batch):
        return tok(batch["text"], truncation=True, max_length=a.max_len)
    def to_ds(df):
        d = Dataset.from_pandas(pd.DataFrame({"text": df["text"], "label": df["label"].map(L2I)}), preserve_index=False)
        return d.map(enc, batched=True, remove_columns=["text"])
    ds_tr, ds_va, ds_te = to_ds(train), to_ds(sp["val"]), to_ds(sp["test"])

    model = AutoModelForSequenceClassification.from_pretrained(
        a.hf_model, num_labels=len(LABELS), id2label=dict(enumerate(LABELS)), label2id=L2I)
    out_dir = RESULTS / "distilbert"
    args = TrainingArguments(
        output_dir=str(out_dir / "ckpt"), num_train_epochs=a.epochs,
        per_device_train_batch_size=a.batch_size, per_device_eval_batch_size=a.batch_size * 2,
        learning_rate=5e-5, weight_decay=0.01,
        warmup_steps=int(0.06 * a.epochs * max(1, len(ds_tr) // a.batch_size)),
        eval_strategy="epoch", save_strategy="no", logging_steps=50, report_to=[],
        seed=20260901, dataloader_num_workers=0, use_cpu=(device == "cpu"),
        fp16=(device == "cuda"))
    def metrics(ev):
        logits, y = ev
        pred = logits.argmax(-1)
        s = score([LABELS[i] for i in y], [LABELS[i] for i in pred])
        return {"accuracy": s["accuracy"], "macro_f1": s["macro_f1"]}
    trainer = Trainer(model=model, args=args, train_dataset=ds_tr, eval_dataset=ds_va, processing_class=tok,
                      data_collator=DataCollatorWithPadding(tok), compute_metrics=metrics)
    t0 = time.time()
    trainer.train()
    secs = time.time() - t0
    val_m = trainer.evaluate(ds_va)
    def predict_labels(ds):
        return [LABELS[i] for i in trainer.predict(ds).predictions.argmax(-1)]
    test = score(sp["test"]["label"].to_numpy(), predict_labels(ds_te))
    res = {"model": "distilbert", "hf_model": a.hf_model, "device": device, "epochs": a.epochs,
           "max_len": a.max_len, "batch_size": a.batch_size, "n_fit": int(len(train)),
           "val": {"accuracy": float(val_m.get("eval_accuracy", float("nan"))),
                   "macro_f1": float(val_m.get("eval_macro_f1", float("nan")))},
           "test": test, "train_seconds": round(secs, 1)}
    if "dhaka_seed" in sp:
        res["ood_dhaka_seed"] = score(sp["dhaka_seed"]["label"].to_numpy(), predict_labels(to_ds(sp["dhaka_seed"])))
    out_dir.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(out_dir / "model"))
    tok.save_pretrained(str(out_dir / "model"))
    res["artifact"] = "results/nlp/distilbert/model"
    return res


# ----------------------------------------------------------------------------- reporting
def write_reports(all_res: dict, manifest: dict | None) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "classifier.json").write_text(json.dumps(all_res, indent=2))
    src = manifest.get("source", "?") if manifest else "?"
    lines = ["# Traffic-text classifier — {incident, congestion, irrelevant}", "",
             f"Data: `data/nlp/MANIFEST.json` (source: {src}; "
             f"test n = {next(iter(all_res.values()))['test']['n']}, frozen held-out).", "",
             "| model | CV acc (5-fold) | CV macro-F1 | **test acc** | **test macro-F1** | F1 incident | F1 congestion | F1 irrelevant | Dhaka-seed acc / mF1 (n=150) | train s |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for name, r in all_res.items():
        cv = r.get("cv_train_val")
        cv_acc = f"{cv['accuracy_mean']:.4f} ± {cv['accuracy_sd']:.4f}" if cv else "–"
        cv_f1 = f"{cv['macro_f1_mean']:.4f} ± {cv['macro_f1_sd']:.4f}" if cv else "–"
        t = r["test"]; pc = t["per_class"]
        ood = r.get("ood_dhaka_seed")
        ood_s = f"{ood['accuracy']:.3f} / {ood['macro_f1']:.3f}" if ood else "–"
        lines.append(f"| {name} | {cv_acc} | {cv_f1} | **{t['accuracy']:.4f}** | **{t['macro_f1']:.4f}** | "
                     f"{pc['incident']['f1']:.4f} | {pc['congestion']['f1']:.4f} | {pc['irrelevant']['f1']:.4f} | "
                     f"{ood_s} | {r.get('train_seconds', '–')} |")
    for name, r in all_res.items():
        cm = r["test"]["confusion_matrix"]["rows_true_cols_pred"]
        lines += ["", f"Confusion matrix ({name}, test; rows = true, cols = pred; order {LABELS}):", "",
                  "```", *[f"{LABELS[i]:>11s} " + " ".join(f"{v:6d}" for v in row) for i, row in enumerate(cm)], "```"]
    lines += ["", "Dhaka-seed column: `tfidf_lr`/`distilbert` = zero-shot (seed never trained on); "
              "`tfidf_lr_dhaka_aug` = 5-fold over the seed with the real corpus + 4/5 seed in training.",
              "", "Regenerate: `python -m traffictwin.nlp.get_data && python -m traffictwin.nlp.train_classifier --augment-seed` "
              "(`--model distilbert` for the transformer row)."]
    (RESULTS / "classifier.md").write_text("\n".join(lines) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", choices=["tfidf_lr", "distilbert", "all"], default="tfidf_lr")
    ap.add_argument("--C", type=float, default=4.0, help="LogReg inverse regularisation")
    ap.add_argument("--hf-model", default="distilbert-base-uncased")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--max-len", type=int, default=64)
    ap.add_argument("--max-train", type=int, default=0, help="subsample training rows for DistilBERT (0 = all)")
    ap.add_argument("--force", action="store_true", help="train DistilBERT locally even on CPU with a large set")
    ap.add_argument("--augment-seed", action="store_true",
                    help="also fit tfidf_lr_dhaka_aug (real corpus + Dhaka seed posts; OOD scored by seed-fold CV)")
    a = ap.parse_args()

    sp = load_splits()
    man_p = DATA / "MANIFEST.json"
    manifest = json.loads(man_p.read_text()) if man_p.exists() else None
    print(f"[data] train={len(sp['train'])} val={len(sp['val'])} test={len(sp['test'])} "
          f"seed={len(sp.get('dhaka_seed', []))} source={manifest.get('source') if manifest else '?'}")

    cj = RESULTS / "classifier.json"
    all_res = json.loads(cj.read_text()) if cj.exists() else {}
    if a.model in ("tfidf_lr", "all"):
        for aug in ([False, True] if a.augment_seed else [False]):
            r = run_tfidf_lr(sp, a, augment=aug); all_res[r["model"]] = r
            print(f"[{r['model']}] TEST acc={r['test']['accuracy']:.4f} macroF1={r['test']['macro_f1']:.4f} "
                  f"OOD-Dhaka acc={r.get('ood_dhaka_seed', {}).get('accuracy', float('nan')):.3f}")
    if a.model in ("distilbert", "all"):
        r = run_distilbert(sp, a)
        if r:
            all_res["distilbert"] = r
            print(f"[distilbert] TEST acc={r['test']['accuracy']:.4f} macroF1={r['test']['macro_f1']:.4f}")
    if all_res:
        write_reports(all_res, manifest)
        print(f"[report] {RESULTS / 'classifier.json'}  {RESULTS / 'classifier.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
