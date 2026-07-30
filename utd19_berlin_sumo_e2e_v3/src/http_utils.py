from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any

import requests
from tqdm.auto import tqdm


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": "UTD19-Berlin-SUMO-Reconstruction/3.0"})
    return s


def download(url: str, destination: str | Path, *, expected_size: int | None = None,
             timeout: int = 120, retries: int = 5) -> Path:
    dest = Path(destination)
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, retries + 1):
        existing = dest.stat().st_size if dest.exists() else 0
        headers: dict[str, str] = {}
        mode = "wb"
        if existing:
            headers["Range"] = f"bytes={existing}-"
            mode = "ab"
        try:
            with session().get(url, headers=headers, stream=True, timeout=timeout) as r:
                if existing and r.status_code != 206:
                    existing = 0
                    mode = "wb"
                r.raise_for_status()
                total = int(r.headers.get("Content-Length", 0)) + existing
                with open(dest, mode) as f, tqdm(
                    total=total or expected_size, initial=existing,
                    unit="B", unit_scale=True, desc=dest.name
                ) as bar:
                    for chunk in r.iter_content(chunk_size=16 * 1024 * 1024):
                        if chunk:
                            f.write(chunk)
                            bar.update(len(chunk))
            if expected_size and dest.stat().st_size != expected_size:
                raise IOError(
                    f"Expected {expected_size} bytes, got {dest.stat().st_size} for {dest}"
                )
            return dest
        except Exception:
            if attempt == retries:
                raise
            time.sleep(min(30, 2 ** attempt))
    return dest


def head_metadata(url: str) -> dict[str, Any]:
    r = session().head(url, allow_redirects=True, timeout=60)
    r.raise_for_status()
    return {
        "url": r.url,
        "size": int(r.headers.get("Content-Length", 0) or 0),
        "etag": r.headers.get("ETag"),
        "last_modified": r.headers.get("Last-Modified"),
        "content_type": r.headers.get("Content-Type"),
    }
