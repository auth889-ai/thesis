"""References — every paper, dataset, standard, tool and service the code uses, read from
docs/references.json (the single source; docs/REFERENCES.md is generated from it)."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app import evidence_paths as config

router = APIRouter()
SRC = config.REPO / "docs/references.json"


def load() -> dict:
    if not SRC.exists():
        raise HTTPException(404, "docs/references.json is missing")
    data = json.loads(SRC.read_text())
    n = sum(len(g["items"]) for g in data["groups"])
    return {"source": str(SRC.relative_to(config.REPO)), "count": n, "groups": data["groups"], "about": data.get("_about")}


@router.get("/api/references", tags=["references"])
def references():
    return load()


def render_markdown(data: dict) -> str:
    L = ["# References", "", "Every external research artifact the TrafficTwin code uses, with the files that use it. Generated from `docs/references.json` (`python -m app.protocols.routers.references`); the same data is served at `/api/references` and shown on the References page of the web application.", ""]
    for g in data["groups"]:
        L += [f"## {g['title']}", ""]
        for i, it in enumerate(g["items"], 1):
            ident = " · ".join(x for x in [f"DOI {it['doi']}" if it.get("doi") else "", f"data DOI {it['data_doi']}" if it.get("data_doi") else "", it.get("url") or ""] if x)
            L.append(f"{i}. **{it['title']}** — {it.get('authors', '')}. *{it.get('venue', '')}*, {it.get('year', '')}. {ident}")
            L.append(f"   Used for: {it['used_for']}" + (" *(context only — quoted numbers, no code runs here)*" if it.get("context_only") else ""))
            if it.get("code"):
                L.append(f"   Code: {it['code']}")
            L.append("   Files: " + ", ".join(f"`{f}`" for f in it.get("files", [])))
            L.append("")
    return "\n".join(L)


def write_markdown() -> Path:
    out = config.REPO / "docs/REFERENCES.md"
    out.write_text(render_markdown(load()))
    return out


if __name__ == "__main__":
    print(write_markdown())
