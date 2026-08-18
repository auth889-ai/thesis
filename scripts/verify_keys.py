#!/usr/bin/env python3
"""Consolidated provider-key activation pass.

    python scripts/verify_keys.py            # presence board only (no network)
    python scripts/verify_keys.py --live     # + zero/near-zero-cost identity
                                             #   checks for every present key

One command answers: which providers are ready, which are BLOCKED_EXTERNAL_KEY,
and exactly what to run next per provider. Never prints key material. Live
checks use only free identity endpoints (Anthropic model list, AWS STS,
HF whoami, Kaggle auth probe, 511NY getcameras). The Google Routes capture is
per-request billed, so it stays its own explicit command
(scripts/run_live_capture.py) and is only pointed to here.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from dhakaflow.live.ny511_provider import load_ny511_key


def _env_or_dotenv(name: str) -> str:
    v = os.environ.get(name, "")
    if v:
        return v
    envf = REPO / "dhakaflow" / ".env"
    if envf.exists():
        for line in envf.read_text().splitlines():
            m = re.match(rf'\s*(?:export\s+)?{name}\s*=\s*["\']?([^"\'\s]+)', line)
            if m:
                return m.group(1)
    return ""


def _http_status(url: str, headers: dict | None = None) -> int:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return -1


def check_google(live: bool) -> tuple[str, str]:
    key = _env_or_dotenv("GOOGLE_MAPS_API_KEY")
    if not key:
        return ("BLOCKED_EXTERNAL_KEY",
                "set GOOGLE_MAPS_API_KEY (restricted: Routes+Weather), then "
                "python scripts/run_live_capture.py")
    return ("READY_FOR_KEY_VERIFICATION",
            "key present — run: python scripts/run_live_capture.py "
            "(billed per request; 7 requests; RUNTIME_REFERENCE mode)")


def check_511ny(live: bool) -> tuple[str, str]:
    key = load_ny511_key()
    if not key:
        return ("PENDING_EXTERNAL_APPROVAL",
                "request submitted 2026-08-19; when approved: "
                "export NY511_API_KEY=... && python scripts/verify_511ny.py")
    if not live:
        return ("KEY_PRESENT", "run: python scripts/verify_511ny.py")
    code = _http_status(f"https://511ny.org/api/getcameras?key={key}&format=json")
    return (("VERIFIED_LIVE", "activation ok — run scripts/verify_511ny.py for evidence")
            if code == 200 else
            ("KEY_REJECTED", f"getcameras returned HTTP {code}"))


def check_anthropic(live: bool) -> tuple[str, str]:
    key = _env_or_dotenv("ANTHROPIC_API_KEY")
    if not key:
        return ("BLOCKED_EXTERNAL_KEY",
                "needed only at the GenAI copilot gate (last gate)")
    if not live:
        return ("KEY_PRESENT", "live check: --live (free model-list endpoint)")
    code = _http_status("https://api.anthropic.com/v1/models",
                        {"x-api-key": key, "anthropic-version": "2023-06-01"})
    return (("VERIFIED_LIVE", "model list ok") if code == 200 else
            ("KEY_REJECTED", f"HTTP {code}"))


def check_aws(live: bool) -> tuple[str, str]:
    has = bool(_env_or_dotenv("AWS_ACCESS_KEY_ID") and
               _env_or_dotenv("AWS_SECRET_ACCESS_KEY")) or \
        (Path.home() / ".aws" / "credentials").exists()
    if not has:
        return ("BLOCKED_EXTERNAL_KEY",
                "needed for long training runs ($200 credit); spot + S3 checkpoints")
    if not live:
        return ("KEY_PRESENT", "live check: --live (free STS get-caller-identity)")
    r = subprocess.run(["aws", "sts", "get-caller-identity"],
                       capture_output=True, text=True)
    return (("VERIFIED_LIVE", "STS identity ok") if r.returncode == 0 else
            ("KEY_REJECTED", (r.stderr or "aws CLI failed").strip()[:120]))


def check_hf(live: bool) -> tuple[str, str]:
    tok = _env_or_dotenv("HF_TOKEN") or _env_or_dotenv("HUGGING_FACE_HUB_TOKEN")
    if not tok:
        return ("BLOCKED_EXTERNAL_KEY",
                "free token; needed at forecasting gate (Chronos-2 pulls)")
    if not live:
        return ("KEY_PRESENT", "live check: --live (free whoami endpoint)")
    code = _http_status("https://huggingface.co/api/whoami-v2",
                        {"Authorization": f"Bearer {tok}"})
    return (("VERIFIED_LIVE", "whoami ok") if code == 200 else
            ("KEY_REJECTED", f"HTTP {code}"))


def check_kaggle(live: bool) -> tuple[str, str]:
    kj = Path.home() / ".kaggle" / "kaggle.json"
    has = kj.exists() or bool(_env_or_dotenv("KAGGLE_USERNAME") and
                              _env_or_dotenv("KAGGLE_KEY"))
    if not has:
        return ("BLOCKED_EXTERNAL_KEY",
                "free token; needed for BNVD download (P1 BNVD track). "
                "Poribohon-BD track needs NO credentials")
    if not live:
        return ("KEY_PRESENT", "live check: --live (free auth probe)")
    if kj.exists() and not _env_or_dotenv("KAGGLE_USERNAME"):
        creds = json.loads(kj.read_text())
        os.environ["KAGGLE_USERNAME"] = creds.get("username", "")
        os.environ["KAGGLE_KEY"] = creds.get("key", "")
    import base64
    auth = base64.b64encode(
        f"{os.environ.get('KAGGLE_USERNAME')}:{os.environ.get('KAGGLE_KEY')}"
        .encode()).decode()
    code = _http_status(
        "https://www.kaggle.com/api/v1/datasets/list?search=traffic&pageSize=1",
        {"Authorization": f"Basic {auth}"})
    return (("VERIFIED_LIVE", "auth ok") if code == 200 else
            ("KEY_REJECTED", f"HTTP {code}"))


CHECKS = [
    ("GOOGLE_MAPS_API_KEY (Routes+Weather)", check_google),
    ("NY511_API_KEY (511NY cameras)", check_511ny),
    ("ANTHROPIC_API_KEY (copilot gate)", check_anthropic),
    ("AWS (training runs)", check_aws),
    ("HF_TOKEN (Chronos-2)", check_hf),
    ("Kaggle token (BNVD)", check_kaggle),
]


def main() -> int:
    live = "--live" in sys.argv
    print(f"Provider-key activation board ({'LIVE checks' if live else 'presence only'})\n")
    rows = []
    for label, fn in CHECKS:
        try:
            status, note = fn(live)
        except Exception as exc:                       # a broken check never hides the board
            status, note = "CHECK_ERROR", str(exc)[:120]
        rows.append((label, status, note))
    w = max(len(r[0]) for r in rows)
    for label, status, note in rows:
        print(f"  {label:<{w}}  {status:<26}  {note}")
    print("\nBLOCKED_EXTERNAL_KEY / PENDING_EXTERNAL_APPROVAL do NOT block the "
          "build — provider-independent work continues.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
