"""The researcher's own trips: one named exception to the rule that a road reading needs several phones.

The rule (at least three distinct phones behind a reading) protects people: a reading from one phone shows where
that one person was. The project's researcher may consent to exactly that for their own research trips. Their
device is listed, by its hash, in a file that exists only on their own machine:

    PYTHONPATH=backend python -m core.common.data.researcher --device-id <the id this browser sends>     # adds its hash
    PYTHONPATH=backend python -m core.common.data.researcher --list

The file (`results/live/researcher_devices.txt`) is not tracked by git and is never created by the app. While it
exists on a machine, positions from a listed device are kept in cells of their own, apart from everyone else's, and
the home shows them as "researcher's own trips, 1 device". Where the file does not exist (any other machine, and a
hosted copy of the app) nothing is exempt and such a device is an ordinary phone.

What it means for privacy: every such reading places the researcher on a 70 m stretch of road within a 5-minute
interval, for anyone who can open this machine's app. Raw positions are still deleted after 24 hours; the cells stay.
No other person's device can be listed without their device id, and listing one would break the app's consent rule.
"""
from __future__ import annotations

import os
from pathlib import Path

import hashlib

from core.common.paths import REPO

FILE_ENV = "DHAKAFLOW_RESEARCHER_DEVICES_FILE"
DEFAULT_FILE = REPO / "results/live/researcher_devices.txt"
MARK = "r"                    # the suffix of a cell that holds the researcher's own positions
SOURCE = "researcher's own trips (one consenting device; exempt from the several-phones rule)"


def file() -> Path:
    return Path(os.environ.get(FILE_ENV) or DEFAULT_FILE)


def devices() -> set[str]:
    """Hashes of the devices listed on this machine; empty when the file does not exist."""
    f = file()
    return {line.split("#")[0].strip() for line in f.read_text().splitlines() if line.split("#")[0].strip()} if f.exists() else set()


def is_researcher(device_hash: str) -> bool:
    return device_hash in devices()


def own_cell(cell: str) -> bool:
    return cell.split(":")[-1] == MARK


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--device-id")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.device_id:
        h = device_hash(a.device_id)
        if h not in devices():
            file().parent.mkdir(parents=True, exist_ok=True)
            with open(file(), "a") as f:
                f.write(f"{h}   # the researcher's own device; added by hand with their consent\n")
        print(f"listed {h} in {file()}")
    if a.list or not a.device_id:
        print(sorted(devices()) or f"no device is listed ({file()} does not exist or is empty)")


def device_hash(device_id: str) -> str:
    """A phone's id as stored: a truncated SHA-256 (the probes store uses the same)."""
    return hashlib.sha256(device_id.encode()).hexdigest()[:16]
