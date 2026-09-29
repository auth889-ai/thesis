"""The model path: Bedrock fills the Commitment contract through one forced tool call whose input schema is the
contract's own JSON Schema (the same one /api/lifeos/schema serves). The answer is validated by Pydantic; a reply
that does not fit is discarded and the rules path answers. The model never stores anything."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.lifeos.entities import Commitment, CommitmentType, Flexibility, Place, Priority

FIELDS = {"title": {"type": "string"}, "type": {"type": "string", "enum": [t.value for t in CommitmentType]},
          "location": {"type": ["string", "null"], "description": "the place name as written, or null"},
          "start_local": {"type": ["string", "null"], "description": "YYYY-MM-DDTHH:MM in the person's zone when the commitment happens at a time; null for a deadline-only item"},
          "deadline_local": {"type": "string", "description": "YYYY-MM-DDTHH:MM in the person's zone: the latest acceptable arrival or completion"},
          "duration_min": {"type": "integer"}, "priority": {"type": "string", "enum": [p.value for p in Priority]},
          "flexibility": {"type": "string", "enum": [f.value for f in Flexibility]},
          "requirements": {"type": "array", "items": {"type": "string"}, "description": "things to bring or finish first"},
          "missing": {"type": "array", "items": {"type": "string"}, "description": "what the text does not say but the commitment needs (a time, a place)"}}
TOOL = {"toolSpec": {"name": "commitment__record", "description": "Record the commitment the text describes. Never invent a time or a place that the text does not state.",
                     "inputSchema": {"json": {"type": "object", "properties": FIELDS, "required": ["title", "type", "deadline_local", "flexibility"]}}}}
PROMPT = ("Read the text and record the one commitment it describes with commitment__record. Today is {today} ({weekday}) in the person's zone {zone}; "
          "the person's saved places are: {places}. Resolve relative days from today. If the text gives no time, do not guess one: put 'time' in missing and use the day at 23:59 as the deadline.")


def compile_model(text: str, person_id: str, now: datetime, tz: str, known_places: list[Place], llm, new_id=None) -> dict | None:
    local = now.astimezone(ZoneInfo(tz))
    prompt = PROMPT.format(today=local.strftime("%Y-%m-%d %H:%M"), weekday=local.strftime("%A"), zone=tz, places=", ".join(p.name for p in known_places) or "none")
    turn = llm.complete(prompt, [{"role": "user", "content": [{"text": text}]}], [TOOL], max_tokens=500)
    call = next((c for c in turn.tool_calls if c["name"] == "commitment__record"), None)
    if not call:
        return None
    a = call["input"]
    z = ZoneInfo(tz)
    def _dt(s):
        return datetime.fromisoformat(s).replace(tzinfo=z) if s else None
    loc = a.get("location")
    place = None
    if loc:
        from rapidfuzz import fuzz, process, utils
        hit = process.extractOne(loc, [p.name for p in known_places], scorer=fuzz.WRatio, processor=utils.default_process, score_cutoff=80) if known_places else None
        place = known_places[hit[2]].model_copy() if hit else Place(name=loc)
    flex = Flexibility(a.get("flexibility", "fixed"))
    start = _dt(a.get("start_local")) if flex == Flexibility.FIXED else None
    commitment = Commitment(id=new_id() if new_id else f"c_{abs(hash((person_id, text))) % 10**10:010d}", person_id=person_id, title=a["title"], type=CommitmentType(a["type"]), location=place,
                            start=start or (_dt(a["deadline_local"]) if flex == Flexibility.FIXED else None), deadline=_dt(a["deadline_local"]), duration_min=int(a.get("duration_min") or 60),
                            priority=Priority(a.get("priority", "should")), flexibility=flex, requirements=list(a.get("requirements") or []), source="person")
    missing = list(a.get("missing") or [])
    return {"commitment": commitment, "path": getattr(llm, "model", "model") or "model", "confidence": round(1.0 - 0.3 * len(missing), 2), "found": {"time": "time" not in missing, "type": commitment.type != CommitmentType.OTHER, "location": place is not None, "requirements": bool(commitment.requirements), "duration": "duration_min" in a}, "missing": missing, "time_phrase": None, "window": None}
