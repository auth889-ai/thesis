"""Score a compiler path on data/lifeos/commitments.jsonl: per-field exact match, and refusal when the time is missing.
    PYTHONPATH=backend python -m app.lifeos.compiler.evaluate [--model]
Writes results/lifeos/compiler.json; the lab reads it. The reference clock is 2026-09-30 09:00 Asia/Dhaka (a Wednesday)."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from app.lifeos.compiler import rules
from app.lifeos.entities import Place
from app.paths import REPO

DATA = REPO / "data/lifeos/commitments.jsonl"; OUT = REPO / "results/lifeos/compiler.json"
NOW = datetime(2026, 9, 30, 9, 0, tzinfo=ZoneInfo("Asia/Dhaka")); TZ = "Asia/Dhaka"
KNOWN = [Place(name="Mirpur", kind="home"), Place(name="Evercare Hospital", kind="saved"), Place(name="IUT", kind="work")]


def score(compile_fn, rows: list[dict]) -> dict:
    fields = {"type": 0, "when": 0, "location": 0, "requirements": 0, "flexibility": 0, "duration": 0}; n = 0; refused_ok = 0; needs = 0; errors = []
    for r in rows:
        res = compile_fn(r["text"]); c = res["commitment"]
        if "needs_time" in r["tags"]:
            needs += 1; refused_ok += c is None and "time" in res["missing"]; continue
        n += 1
        if c is None:
            errors.append({"text": r["text"], "got": None}); continue
        when = (c.start or c.deadline).astimezone(ZoneInfo(TZ)).strftime("%Y-%m-%dT%H:%M")
        got = {"type": c.type.value, "when": when, "location": c.location.name if c.location else None, "requirements": c.requirements, "flexibility": c.flexibility.value, "duration": c.duration_min if r["duration_min"] else None}
        exp = {"type": r["type"], "when": r["when_local"], "location": r["location"], "requirements": r["requirements"], "flexibility": r["flexibility"], "duration": r["duration_min"]}
        for k in fields:
            ok = got[k] == exp[k] if k != "location" else (got[k] == exp[k] or (got[k] and exp[k] and (exp[k].lower() in got[k].lower() or got[k].lower() in exp[k].lower())))
            fields[k] += bool(ok)
            if not ok:
                errors.append({"text": r["text"], "field": k, "expected": exp[k], "got": got[k]})
    return {"n": n, "field_accuracy": {k: round(v / n, 3) for k, v in fields.items()}, "all_fields_exact": None, "needs_time_refused": f"{refused_ok}/{needs}", "errors": errors[:60]}


def main(model: bool = False) -> dict:
    rows = [json.loads(l) for l in DATA.read_text().splitlines() if l.strip()]
    out = {"data": str(DATA.relative_to(REPO)), "rows": len(rows), "reference_now": NOW.isoformat(), "paths": {}}
    out["paths"]["rules"] = score(lambda t: rules.compile_rules(t, "eval", NOW, TZ, KNOWN), rows)
    if model:
        from app.agent.llm import Bedrock
        from app.lifeos.compiler import model as mp
        llm = Bedrock()
        out["paths"][llm.model] = score(lambda t: mp.compile_model(t, "eval", NOW, TZ, KNOWN, llm) or {"commitment": None, "missing": ["time"]}, rows)
    OUT.parent.mkdir(parents=True, exist_ok=True); OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    for k, v in out["paths"].items():
        print(k, v["n"], v["field_accuracy"], "refused", v["needs_time_refused"], "errors", len(v["errors"]))
    return out


if __name__ == "__main__":
    main(model="--model" in sys.argv)
