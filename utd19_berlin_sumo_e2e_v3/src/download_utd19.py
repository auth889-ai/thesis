from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .http_utils import download, session
from .utils import sha256_file, write_json

ITEM_UUID = "bfb14ee7-82c8-4357-a293-3bf18d8f93f9"
API_ROOT = "https://www.research-collection.ethz.ch/server/api"


def _embedded_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for value in payload.get("_embedded", {}).values():
        if isinstance(value, list):
            return value
    return []


def discover_files(item_uuid: str = ITEM_UUID) -> list[dict[str, Any]]:
    s = session()
    item = s.get(f"{API_ROOT}/core/items/{item_uuid}", timeout=60)
    item.raise_for_status()
    bundles_url = item.json()["_links"]["bundles"]["href"]
    bundles = s.get(bundles_url, params={"size": 100}, timeout=60)
    bundles.raise_for_status()
    files: list[dict[str, Any]] = []
    for bundle in _embedded_list(bundles.json()):
        bitstreams_url = bundle.get("_links", {}).get("bitstreams", {}).get("href")
        if not bitstreams_url:
            continue
        response = s.get(bitstreams_url, params={"size": 100}, timeout=60)
        response.raise_for_status()
        for bitstream in _embedded_list(response.json()):
            name = str(bitstream.get("name", "")).strip()
            if not name:
                continue
            content_url = bitstream.get("_links", {}).get("content", {}).get("href")
            files.append({
                "name": name,
                "size": int(bitstream.get("sizeBytes") or 0),
                "bundle": bundle.get("name"),
                "uuid": bitstream.get("uuid"),
                "url": content_url,
            })
    return files


def canonical_name(name: str) -> str:
    low = name.lower()
    if "utd19" in low and low.endswith(".csv"):
        return "utd19_u.csv"
    if "detector" in low and low.endswith(".csv"):
        return "detectors.csv"
    if "link" in low and low.endswith(".csv"):
        return "links.csv"
    if low.endswith(".pdf"):
        return "manual.pdf"
    return name


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--list-only", action="store_true")
    parser.add_argument("--skip-large", action="store_true",
                        help="Download metadata/manual but not the 6.65GB measurements")
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    files = discover_files()
    if not files:
        raise RuntimeError("ETH API returned no UTD19 bitstreams.")
    print("Discovered official UTD19 files:")
    for item in files:
        print(item)
    write_json(out / "eth_manifest_discovered.json", files)
    if args.list_only:
        return

    manifest = []
    for item in files:
        dest_name = canonical_name(item["name"])
        if args.skip_large and dest_name == "utd19_u.csv":
            continue
        if not item.get("url"):
            continue
        dest = download(item["url"], out / dest_name, expected_size=item["size"] or None)
        manifest.append({
            **item,
            "saved_as": str(dest),
            "sha256": sha256_file(dest),
        })
    write_json(out / "eth_manifest_downloaded.json", manifest)


if __name__ == "__main__":
    main()
