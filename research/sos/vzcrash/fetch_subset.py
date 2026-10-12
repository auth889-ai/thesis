"""Step M, phases 1 and 2, from the terminal: VZCrash (Hugging Face `vzc-research-chapter/VZCrash`, CC BY-NC 4.0, non-commercial
thesis use; Bianconcini et al., IEEE ITSC 2026), read-only look and a small stratified subset. NOTHING from the dataset is stored on
this machine: the subset is read row group by row group over HTTP and streamed to Google Drive (rclone rcat); the repository's two
notebooks are read as text into a temporary folder and copied to Drive. The notebooks are not run.

    PYTHONPATH=. python research/sos/vzcrash/fetch_subset.py [--drive gdrive2tb:dhakaflow/vzcrash] [--phase 1|2|all]

Phase 1: list the files (files.json), save README.md, explore.ipynb, pr_curve.ipynb and their cells as text to Drive.
Phase 2: from the TEST split, the first 300 crashes and 150 near-misses in file order, and 150 normal-driving events: 75 "kinematic
         distractors" (the highest peak |acceleration| in a pool of the first 3 000 normal events read) and 75 random (seed 7).
         subset_test.parquet (about 25 MB) and subset_manifest.json go to Drive. The rule was fixed before any result was seen.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import io
import json
import random
import subprocess
import tempfile
from pathlib import Path

REPO, REV = "vzc-research-chapter/VZCrash", "42e1482d005c0e545379d6cfa4939486c9fe4249"
QUOTA = {"crash": 300, "near_miss": 150, "pool_normal": 3000}
LABEL = {0: "crash", 1: "near_miss", 2: "normal"}


def to_drive(dest: str, data: bytes) -> None:
    """Stream bytes to Drive; no file on this machine."""
    subprocess.run(["rclone", "rcat", dest], input=data, check=True, stderr=subprocess.DEVNULL)


def phase1(api, drive: str, tmp: Path) -> list[dict]:
    from huggingface_hub import hf_hub_download
    info = api.dataset_info(REPO, revision=REV, files_metadata=True)
    files = [{"path": s.rfilename, "bytes": s.size} for s in sorted(info.siblings, key=lambda s: s.rfilename)]
    to_drive(f"{drive}/files.json", json.dumps({"repo": REPO, "revision": REV, "license": (info.card_data or {}).get("license"), "gated": info.gated, "files": files}, indent=1).encode())
    print(f"phase 1: {len(files)} files, {sum(f['bytes'] or 0 for f in files) / 1e9:.2f} GB in the repository (not downloaded)")
    for name in ("README.md", "explore.ipynb", "pr_curve.ipynb"):
        p = Path(hf_hub_download(REPO, name, repo_type="dataset", revision=REV, local_dir=tmp))
        to_drive(f"{drive}/{name}", p.read_bytes())
        if name.endswith(".ipynb"):
            nb = json.loads(p.read_text())
            lines = [f"# {name} @ {REV}  ({len(nb['cells'])} cells)"]
            for i, c in enumerate(nb["cells"]):
                lines += [f"\n===== cell {i} [{c['cell_type']}] =====", "".join(c.get("source", []))]
                for o in c.get("outputs", []):
                    txt = "".join(o.get("text", [])) or "".join((o.get("data") or {}).get("text/plain", []))
                    if txt and len(txt) <= 2000:
                        lines += ["----- output -----", txt]
                    elif (o.get("data") or {}).get("image/png"):
                        lines += ["----- output: an image (not copied) -----"]
            dump = tmp / name.replace(".ipynb", "_cells.txt")
            dump.write_text("\n".join(lines))
            to_drive(f"{drive}/{dump.name}", dump.read_bytes())
        print(f"  saved {name} ({p.stat().st_size / 1e3:.0f} KB) to Drive")
    return files


def peak_g(gs) -> float:
    import numpy as np
    a = np.asarray(gs, dtype="float32")
    return float(np.sqrt((a * a).sum(axis=1)).max()) if a.ndim == 2 and len(a) else float("nan")


def phase2(files: list[dict], drive: str) -> dict:
    import pyarrow as pa
    import pyarrow.parquet as pq
    from huggingface_hub import HfFileSystem
    fs = HfFileSystem()
    test_files = sorted(f["path"] for f in files if f["path"].startswith("data/test-"))
    keep = {"crash": [], "near_miss": []}
    pool: list[dict] = []
    rows_read, done = 0, False
    for path in test_files:
        with fs.open(f"datasets/{REPO}@{REV}/{path}", "rb") as fh:
            pf = pq.ParquetFile(fh)
            for rg in range(pf.num_row_groups):
                for r in pf.read_row_group(rg).to_pylist():
                    rows_read += 1
                    lab = LABEL[int(r["label"])]
                    if lab == "crash" and len(keep["crash"]) < QUOTA["crash"]:
                        keep["crash"].append(r)
                    elif lab == "near_miss" and len(keep["near_miss"]) < QUOTA["near_miss"]:
                        keep["near_miss"].append(r)
                    elif lab == "normal" and len(pool) < QUOTA["pool_normal"]:
                        pool.append(r)
                done = len(keep["crash"]) >= QUOTA["crash"] and len(keep["near_miss"]) >= QUOTA["near_miss"] and len(pool) >= QUOTA["pool_normal"]
                print(f"  {path} row group {rg}: read {rows_read}, crash {len(keep['crash'])}, near_miss {len(keep['near_miss'])}, normal pool {len(pool)}", flush=True)
                if done:
                    break
        if done:
            break
    rng = random.Random(7)
    pool.sort(key=lambda r: -peak_g(r["gsensor"]))
    normal = pool[:75] + rng.sample(pool[75:], 75)
    groups = ["crash"] * len(keep["crash"]) + ["near_miss"] * len(keep["near_miss"]) + ["normal_distractor"] * 75 + ["normal_random"] * 75
    subset = keep["crash"] + keep["near_miss"] + normal
    for r, g in zip(subset, groups):
        r["subset_group"] = g
    buf = io.BytesIO()
    pq.write_table(pa.Table.from_pylist(subset), buf)
    data = buf.getvalue()
    to_drive(f"{drive}/subset_test.parquet", data)
    man = {"repo": REPO, "revision": REV, "license": "CC BY-NC 4.0 (non-commercial thesis use, attribution: Bianconcini et al., IEEE ITSC 2026)", "split": "test",
           "files_read": test_files[:1 + test_files.index(path)], "rows_read": rows_read, "seed": 7,
           "rule": "first 300 crashes and 150 near-misses in file order; normal: pool of the first 3000, 75 highest peak |a| (distractors) + 75 random",
           "counts": dict(collections.Counter(groups)), "parquet": "subset_test.parquet", "parquet_sha256": hashlib.sha256(data).hexdigest(), "parquet_bytes": len(data),
           "peak_g_examples": {g: [round(peak_g(r["gsensor"]), 2) for r in subset if r["subset_group"] == g][:5] for g in ("crash", "near_miss", "normal_distractor", "normal_random")},
           "stored": "Google Drive only; nothing on the laptop"}
    to_drive(f"{drive}/subset_manifest.json", json.dumps(man, indent=1).encode())
    return man


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--drive", default="gdrive2tb:dhakaflow/vzcrash")
    ap.add_argument("--phase", default="all", choices=["1", "2", "all"])
    a = ap.parse_args()
    from huggingface_hub import HfApi
    api = HfApi()
    try:
        api.whoami()
    except Exception as exc:                                    # noqa: BLE001
        print(f"STOP: not logged in to Hugging Face on this machine ({type(exc).__name__}); the dataset is gated"); return 1
    with tempfile.TemporaryDirectory(prefix="vzcrash-") as tmp:
        files = phase1(api, a.drive, Path(tmp)) if a.phase in ("1", "all") else [{"path": s.rfilename, "bytes": s.size} for s in api.dataset_info(REPO, revision=REV, files_metadata=True).siblings]
        if a.phase in ("2", "all"):
            man = phase2(files, a.drive)
            print(json.dumps({k: man[k] for k in ("rows_read", "counts", "parquet_bytes", "parquet_sha256", "peak_g_examples")}, indent=1))
    print(f"done; everything is under {a.drive} on Drive, nothing on this machine")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
