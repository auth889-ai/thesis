from __future__ import annotations

import argparse
import gzip
import re
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

from .http_utils import download, session
from .utils import safe_filename, sha256_file, write_json

AZURE_ROOT = "https://mdhopendata.blob.core.windows.net/verkehrsdetektion"
LOCATION_URL = "https://api.viz.berlin.de/daten/verkehrsdetektion/teu_standorte.json"


def list_blobs(prefix: str = "") -> list[dict[str, Any]]:
    s = session()
    marker = ""
    records: list[dict[str, Any]] = []
    while True:
        params = {
            "restype": "container", "comp": "list", "include": "metadata",
            "prefix": prefix, "marker": marker, "maxresults": "5000",
        }
        r = s.get(f"{AZURE_ROOT}/", params=params, timeout=120)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        for blob in root.findall("./Blobs/Blob"):
            name = blob.findtext("Name") or ""
            props = blob.find("Properties")
            records.append({
                "name": name,
                "url": f"{AZURE_ROOT}/{urllib.parse.quote(name, safe='/() _-')}".replace(" ", "%20"),
                "size": int(props.findtext("Content-Length") or 0) if props is not None else 0,
                "etag": props.findtext("Etag") if props is not None else None,
                "last_modified": props.findtext("Last-Modified") if props is not None else None,
                "content_type": props.findtext("Content-Type") if props is not None else None,
            })
        marker = root.findtext("NextMarker") or ""
        if not marker:
            break
    return records


def measurement_score(name: str, year: int, month: int, branch_regex: str) -> int:
    text = name.lower()
    score = 0
    if str(year) in text:
        score += 20
    if re.search(branch_regex, name, flags=re.I):
        score += 20
    month_tokens = [f"{month:02d}", f"{year}-{month:02d}", f"{year}_{month:02d}",
                    "feb" if month == 2 else ""]
    for token in month_tokens:
        if token and token in text:
            score += 6
    if text.endswith((".csv", ".csv.gz", ".zip")):
        score += 5
    if "readme" in text:
        score -= 100
    if "stammdaten" in text or "standort" in text:
        score -= 20
    return score


def extract_archives(folder: Path) -> list[str]:
    outputs: list[str] = []
    for path in list(folder.iterdir()):
        low = path.name.lower()
        if low.endswith(".zip"):
            target = folder / path.stem
            target.mkdir(exist_ok=True)
            with zipfile.ZipFile(path) as zf:
                zf.extractall(target)
            outputs.extend(str(p) for p in target.rglob("*") if p.is_file())
        elif low.endswith(".csv.gz"):
            target = folder / path.name[:-3]
            with gzip.open(path, "rb") as src, open(target, "wb") as dst:
                dst.write(src.read())
            outputs.append(str(target))
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--year", type=int, default=2021)
    parser.add_argument("--month", type=int, default=2)
    parser.add_argument("--branch-regex", default=r"Messquerschnitte/mq_hr")
    parser.add_argument("--list-only", action="store_true")
    parser.add_argument("--download-all-year-files", action="store_true")
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    blobs = list_blobs(prefix=str(args.year))
    write_json(out / "berlin_azure_manifest_all.json", blobs)
    print(f"Listed {len(blobs)} official Berlin archive blobs for prefix {args.year}")

    ranked = sorted(
        [{**b, "score": measurement_score(b["name"], args.year, args.month, args.branch_regex)}
         for b in blobs], key=lambda x: (-x["score"], x["name"])
    )
    for item in ranked[:40]:
        print(item["score"], item["name"], item["size"])
    if args.list_only:
        return

    location_path = download(LOCATION_URL, out / "teu_standorte.json")

    # The hourly Messquerschnitt files key on MQ_KURZNAME (TE001...), an id
    # space teu_standorte.json does not contain. The Stammdaten workbook is the
    # published bridge from those ids to WGS84 coordinates and lane counts.
    # Listed without a prefix: the workbook sits at the container root, not
    # under a year folder, so the year-prefixed listing above cannot see it.
    stammdaten = [b for b in list_blobs()
                  if re.search(r"stammdaten.*\.xlsx$", b["name"], re.I)]
    stammdaten_path = None
    if stammdaten:
        newest = sorted(stammdaten, key=lambda b: b["name"])[-1]
        stammdaten_path = download(newest["url"], out / "Stammdaten.xlsx",
                                   expected_size=newest["size"] or None)
        print(f"Detector master data: {newest['name']}")
    else:
        print("WARNING: no Stammdaten workbook found; detector mapping will fail.")

    eligible = [b for b in ranked if b["score"] >= 25]
    selected = []
    if eligible:
        best_score = max(b["score"] for b in eligible)
        # Prefer the most month-specific official files instead of accidentally
        # downloading the complete year archive. Keep all equally ranked parts.
        selected = [b for b in eligible if b["score"] == best_score]
    if args.download_all_year_files:
        selected = [b for b in ranked if b["score"] >= 20]
    if not selected:
        raise RuntimeError(
            "No Berlin measurement files were selected automatically. "
            "Inspect berlin_azure_manifest_all.json and set a different branch regex."
        )

    downloaded = [{
        "name": "teu_standorte.json", "url": LOCATION_URL,
        "saved_as": str(location_path), "sha256": sha256_file(location_path),
    }]
    if stammdaten_path:
        downloaded.append({
            "name": "Stammdaten.xlsx", "saved_as": str(stammdaten_path),
            "sha256": sha256_file(stammdaten_path),
            "role": "MQ_KURZNAME -> WGS84 + monitored lane count",
        })
    for item in selected:
        preserved_name = safe_filename(item["name"].replace("/", "__"))
        dest = download(item["url"], out / preserved_name,
                        expected_size=item["size"] or None)
        downloaded.append({**item, "saved_as": str(dest), "sha256": sha256_file(dest)})
    extracted = extract_archives(out)
    write_json(out / "berlin_manifest_downloaded.json", {
        "year": args.year, "month": args.month, "selected": downloaded,
        "extracted": extracted,
        "archive_revision_warning": "Historical data were revised in 2025; exact paper snapshot unavailable.",
    })


if __name__ == "__main__":
    main()
