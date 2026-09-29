"""compile(): the person's zone and places, the model path when a model is available, the rules path otherwise or when
the model's answer does not validate; optionally the commitment is stored. Every result names its path."""
from __future__ import annotations

from datetime import datetime, timezone

from app.agent.models import new_id
from app.lifeos import db, repo
from app.lifeos.compiler import model as model_path, rules
from app.lifeos.entities import Place


def person_context(person_id: str) -> tuple[str, list[Place]]:
    """The zone and saved places: the core Person row first, the pre-plan profile as a fallback."""
    with db.session() as s:
        p = repo.get_person(s, person_id)
    if p:
        return p.timezone, ([p.home] if p.home else []) + p.places
    from app.profile import service as profile
    tz = str(profile.tz_for(person_id)); c = profile.context(person_id)
    places = [Place(name=c["home"], kind="home")] if c.get("home") else []
    if c.get("work"):
        places.append(Place(name=c["work"], kind="work"))
    return tz, places


def compile(text: str, person_id: str, llm=None, now: datetime | None = None, save: bool = False) -> dict:
    now = now or datetime.now(timezone.utc)
    tz, places = person_context(person_id)
    result = None
    if llm is not None:
        try:
            result = model_path.compile_model(text, person_id, now, tz, places, llm, new_id=lambda: new_id("c"))
        except Exception as exc:                                        # noqa: BLE001 - the rules still answer; the reason is reported
            result = None; model_error = f"{type(exc).__name__}: {str(exc)[:120]}"
        else:
            model_error = None if result else "the model gave no commitment"
    else:
        model_error = "no model available"
    if result is None:
        result = rules.compile_rules(text, person_id, now, tz, places, new_id=lambda: new_id("c"))
        result["model_error"] = model_error
    c = result["commitment"]
    if save and c is not None:
        with db.session() as s:
            if repo.get_person(s, person_id) is None:
                from app.lifeos.entities import Person
                repo.put_person(s, Person(id=person_id, timezone=tz))
            result["commitment"] = repo.put_commitment(s, c); result["saved"] = True
    return {"saved": False, **result, "text": text, "person_id": person_id, "timezone": tz, "commitment": result["commitment"].model_dump(mode="json") if result["commitment"] else None}
