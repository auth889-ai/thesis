"""No Google API is called.

Google Maps Platform Terms 3.2.3 (read 2026-10-05) forbid storing Google Maps Content, creating content from it, and
using it "to improve machine learning and artificial intelligence models, including to train, test, validate or
fine-tune the models". This project did all three with Routes API results (audit: evidence/audit_2026-10-05/), so every
request to a Google endpoint now passes through `check()` first, and `check()` refuses.

The switch below is for a person who has read the terms for a specific, permitted use. Nothing in the app sets it.
"""
from __future__ import annotations

import os

ALLOW_ENV = "TRAFFICTWIN_GOOGLE_CALLS_APPROVED"


class GoogleCallsDisabled(RuntimeError):
    pass


def allowed() -> bool:
    return os.environ.get(ALLOW_ENV) == "1"


def check() -> None:
    if not allowed():
        raise GoogleCallsDisabled(f"Google APIs are not called by this project (Google Maps Platform Terms 3.2.3); set {ALLOW_ENV}=1 only for a use the terms permit")
