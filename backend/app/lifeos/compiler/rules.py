"""The rules path: a conservative reading of one sentence. spaCy finds the date, time, place and organisation spans;
dateparser turns the time phrase into an instant in the person's zone; rapidfuzz matches a typed place to the
person's saved places. Where a rule cannot decide it leaves the field empty and names it in `missing`."""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import dateparser
from rapidfuzz import fuzz, process, utils

from app.lifeos.entities import Commitment, CommitmentType, Flexibility, Place, Priority

TYPE_WORDS = [(CommitmentType.INTERVIEW, r"\binterview\b"), (CommitmentType.EXAM, r"\b(exam|viva|quiz|test)\b"), (CommitmentType.CLASS, r"\b(class|lecture|lab session|tutorial)\b"),
              (CommitmentType.MEETING, r"\b(meeting|call|presentation|seminar|workshop)\b"), (CommitmentType.DEADLINE, r"\b(submit|submission|deadline|due|hand in|assignment)\b"),
              (CommitmentType.MEDICAL, r"\b(hospital|doctor|dentist|clinic|check-?up|therapy|vaccin)\w*"),
              (CommitmentType.TRAVEL, r"\b(flight|airport|train|bus to|station|trip)\b"), (CommitmentType.WORK, r"\b(shift|office|work day|standup)\b"),
              (CommitmentType.ERRAND, r"\b(bank|pharmacy|grocer\w*|shopping|pick up|collect|renew|passport)\b"), (CommitmentType.SOCIAL, r"\b(dinner|lunch|wedding|party|birthday|coffee with)\b")]
_TIME = r"(?:\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM)|\d{1,2}:\d{2}|noon|midnight)"
_DAY = r"(?:today|tonight|tomorrow|day after tomorrow|this (?:morning|afternoon|evening|monday|tuesday|wednesday|thursday|friday|saturday|sunday)|next (?:week|monday|tuesday|wednesday|thursday|friday|saturday|sunday)|(?:mon|tues|wednes|thurs|fri|satur|sun)day|\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\w*|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\w*\s+\d{1,2}(?:st|nd|rd|th)?|\d{4}-\d{2}-\d{2})"
TIME_PHRASE = re.compile(rf"(?:\bby\s+|\bat\s+|\bon\s+|\bbefore\s+)?({_DAY}(?:\s*(?:at|,)?\s*{_TIME})?|{_TIME}(?:\s+(?:on\s+)?{_DAY})?)", re.I)
AT_ANY = re.compile(r"\b(?:at|in|@)\s+([^,.;]+?)(?=\s+(?:on|at|by|before|tomorrow|today|tonight|next|this|for|from)\b|,|\.|;|$)", re.I)
PLACE_AT = re.compile(r"\b(?:at|in|@)\s+(?!\d)((?:[A-Z][\w'&.-]*)(?:\s+(?:[A-Z][\w'&.-]*|of|the|de))*)")
BRING = re.compile(r"\b(?:bring|carry|take|need(?:s|ed)?|remember)\s+(?:my\s+|the\s+|your\s+)?([^.;]+?)(?=\s+(?:at|by|on|before|to|for)\b|[.;]|$)", re.I)
DURATION = re.compile(r"\bfor\s+(\d+(?:\.\d+)?)\s*(h|hr|hrs|hours?|m|min|mins|minutes?)\b", re.I)
PRIORITY = [(Priority.MUST, r"\b(must|important|critical|cannot miss|can't miss|mandatory)\b"), (Priority.COULD, r"\b(maybe|if possible|optional|if I can)\b")]
_nlp = None


def _spacy():
    global _nlp
    if _nlp is None:
        import spacy
        _nlp = spacy.load("en_core_web_sm")
    return _nlp


_CLOCK = re.compile(r"\b(?P<h>\d{1,2})(?::(?P<m>\d{2}))?\s*(?P<ap>am|pm)?\b|\b(?P<noon>noon)\b|\b(?P<mid>midnight)\b", re.I)


def _clock(phrase: str) -> tuple[tuple[int, int], str] | None:
    """The clock time inside a phrase as ((hour, minute), matched text); a bare number counts only with am/pm or a colon."""
    for m in _CLOCK.finditer(phrase):
        if m.group("noon"):
            return (12, 0), m.group(0)
        if m.group("mid"):
            return (0, 0), m.group(0)
        if m.group("h") and (m.group("ap") or m.group("m") is not None):
            h = int(m.group("h")) % 12 + (12 if (m.group("ap") or "").lower() == "pm" else 0) if m.group("ap") else int(m.group("h"))
            return (min(h, 23), int(m.group("m") or 0)), m.group(0)
    return None


def time_phrase(text: str) -> str | None:
    """The span that says when: the day words and the clock time found by our own patterns, joined in text order.
    (spaCy's DATE/TIME labels were tried first and dropped: they miss "10 Oct" next to "9 am" and label ISO times as numbers.)"""
    body = DURATION.sub(" ", text)
    day = re.search(_DAY, body, re.I); clock = _clock(body)
    parts = [(day.start(), day.group(0)) if day else None, (body.find(clock[1]), clock[1].strip()) if clock else None]
    parts = [x for x in parts if x]
    return " ".join(t for _, t in sorted(parts)) or None


_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _day_from_words(day_text: str, local_now: datetime) -> datetime | None:
    """Relative days the way people say them; dateparser handles the explicit dates."""
    t = day_text.lower().strip(" ,")
    if t in ("", "today", "tonight", "this morning", "this afternoon", "this evening"):
        return local_now
    if t == "tomorrow":
        return local_now + timedelta(days=1)
    if t == "day after tomorrow":
        return local_now + timedelta(days=2)
    m = re.fullmatch(r"(?:(next|this)\s+)?(?:on\s+)?(mon|tue|tues|wed|wednes|thu|thur|thurs|fri|sat|satur|sun)(?:day)?", t)
    if m:
        target = next(i for i, w in enumerate(_WEEKDAYS) if w.startswith(m.group(2)[:3]))
        ahead = (target - local_now.weekday()) % 7
        if ahead == 0 and m.group(1) != "this":
            ahead = 7                                      # "Friday" said on a Friday means next week's
        if m.group(1) == "next" and ahead < 7 and (local_now + timedelta(days=ahead)).isocalendar()[1] == local_now.isocalendar()[1]:
            ahead += 7                                     # "next Friday" said on a Wednesday is the Friday of next week
        return local_now + timedelta(days=ahead)
    return None


def parse_when(phrase: str | None, now: datetime, tz: str) -> datetime | None:
    """The instant a phrase names, in the person's zone. The day comes from dateparser (relative to now, future preferred);
    the clock time from the phrase itself. A day without a time is not an instant and returns None."""
    if not phrase:
        return None
    local_now = now.astimezone(ZoneInfo(tz)); found = _clock(phrase)
    if found is None:
        return None
    (hour, minute), span = found
    day_text = re.sub(r"\s+", " ", phrase.replace(span, " ")).replace(" at ", " ").replace(" on ", " ").strip(" ,")
    day = _day_from_words(day_text, local_now)
    if day is None:
        d = dateparser.parse(day_text, settings={"RELATIVE_BASE": local_now, "TIMEZONE": tz, "RETURN_AS_TIMEZONE_AWARE": True, "PREFER_DATES_FROM": "future"}, languages=["en"])
        if d is None:
            return None
        day = d
    when = day.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if not day_text and when <= local_now:
        when += timedelta(days=1)                            # "6 PM" said after 6 PM means tomorrow
    return when


def find_type(text: str) -> CommitmentType:
    """The activity, read with the place phrase removed: a bank visit at a hospital is an errand."""
    t = AT_ANY.sub(" ", text).lower()
    return next((k for k, rx in TYPE_WORDS if re.search(rx, t)), CommitmentType.OTHER) if t.strip() else CommitmentType.OTHER


def find_place(text: str, known: list[Place], time_span: str | None) -> tuple[Place | None, float]:
    """A named place: the 'at X' phrase or a GPE/FAC/ORG entity outside the time phrase; snapped to a saved place when it fuzzily matches."""
    if known:                                                      # a saved place written in any case, e.g. "at ucla"
        for m in AT_ANY.finditer(text):
            cand = m.group(1).strip()
            if time_span and cand in time_span:
                continue
            hit = process.extractOne(cand, [p.name for p in known], scorer=fuzz.WRatio, processor=utils.default_process, score_cutoff=80)
            if hit:
                return known[hit[2]].model_copy(), hit[1] / 100
    cands = [m.group(1).strip() for m in PLACE_AT.finditer(text)]
    cands += [e.text for e in _spacy()(text).ents if e.label_ in ("GPE", "FAC", "ORG", "LOC")]
    cands = [c for c in cands if c and not (time_span and c in time_span) and not re.fullmatch(_DAY, c, re.I)]
    if not cands:
        return None, 0.0
    ats = [m.group(1).strip() for m in PLACE_AT.finditer(text) if m.group(0).lower().startswith("at")]
    ins = [m.group(1).strip() for m in PLACE_AT.finditer(text) if m.group(0).lower().startswith("in")]
    name = f"{ats[0]}, {ins[0]}" if ats and ins and ats[0] != ins[0] and not (time_span and (ats[0] in time_span or ins[0] in time_span)) else max(cands, key=len)
    if known:
        hit = process.extractOne(name, [p.name for p in known], scorer=fuzz.WRatio, processor=utils.default_process, score_cutoff=80)
        if hit:
            p = known[hit[2]]; return p.model_copy(), hit[1] / 100
    return Place(name=name), 0.6


def find_requirements(text: str) -> list[str]:
    out: list[str] = []
    for m in BRING.finditer(text):
        out += [re.sub(r"^(?:the|my|your|a|an)\s+", "", x.strip(" .")) for x in re.split(r",|\band\b|&", m.group(1)) if x.strip(" .")]
    return [x for x in out if len(x) <= 40 and not re.search(_TIME, x, re.I)]


def compile_rules(text: str, person_id: str, now: datetime, tz: str, known_places: list[Place] | None = None, new_id=None) -> dict:
    """The rules reading: a dict with the Commitment (or None), the fields that were found, the fields missing, and a confidence."""
    span = time_phrase(text)
    when = parse_when(span, now, tz)
    ctype = find_type(text)
    place, place_conf = find_place(text, known_places or [], span)
    reqs = find_requirements(text)
    dur = DURATION.search(text)
    duration = round(float(dur.group(1)) * (60 if dur.group(2).lower().startswith("h") else 1)) if dur else (30 if ctype in (CommitmentType.DEADLINE,) else 60)
    priority = next((p for p, rx in PRIORITY if re.search(rx, text, re.I)), Priority.SHOULD)
    by = bool(span and re.search(rf"\b(by|before)\s+{re.escape(span)}", text, re.I)) or ctype == CommitmentType.DEADLINE
    missing = [f for f, ok in (("time", when is not None), ("location", place is not None or ctype == CommitmentType.DEADLINE)) if not ok]
    found = {"time": when is not None, "type": ctype != CommitmentType.OTHER, "location": place is not None, "requirements": bool(reqs), "duration": bool(dur)}
    confidence = round((0.45 * found["time"] + 0.25 * found["type"] + 0.2 * (place_conf if place else 0) + 0.1 * found["requirements"]), 2)
    title = f"{ctype.value.capitalize()}{' at ' + place.name if place and ctype != CommitmentType.DEADLINE else ''}" if ctype != CommitmentType.OTHER else text.strip().rstrip(".")[:80]
    commitment = None
    if when is not None:
        commitment = Commitment(id=(new_id() if new_id else f"c_{abs(hash((person_id, text, when.isoformat()))) % 10**10:010d}"), person_id=person_id, title=title, type=ctype, location=place,
                                start=None if by else when, deadline=when, duration_min=duration, priority=priority, flexibility=Flexibility.ANYTIME_BEFORE if by else Flexibility.FIXED,
                                requirements=reqs, source="person")
    return {"commitment": commitment, "path": "rules", "confidence": confidence, "found": found, "missing": missing, "time_phrase": span, "window": None if not when else (when - timedelta(minutes=duration)).isoformat()}
