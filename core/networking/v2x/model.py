"""The network model: one question, asked the same way by every phase that sends a message.

    deliver(sender, receiver, time_s, technology, rng) -> Delivery(delivered, delay_s, reason)

Given where the sender and the receiver are, when the message is sent and by which technology: did it arrive, and
after what delay? This is the Python implementation. Every parameter is one entry of configs/network_model.yaml with
its value and the source it was read from; a parameter without a source is null there, and a technology with a null
parameter is REFUSED by name instead of being given a guessed value.

The model is deliberately small: inside a technology's range a message arrives with the delivery ratio the source
states, after the mean delay the source states times the number of radio legs; beyond the range it does not arrive.
It has no fading, no interference between senders and no load. The same seed gives the same answers.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

CONFIG = Path(__file__).parent / "configs/network_model.yaml"
PARAMETERS = ("hops", "range_m", "delivery_ratio_in_range", "delay_s")
IN_RANGE, LOST, OUT_OF_RANGE, EXPIRED = "in range", "lost", "out of range", "expired"


class Refused(Exception):
    """A technology the model will not answer for: unknown, or with a parameter that has no source."""


@dataclass(frozen=True)
class Station:
    id: str
    x: float                     # metres, in the simulation's own plane
    y: float


@dataclass(frozen=True)
class Delivery:
    delivered: bool
    delay_s: float | None        # None when not delivered
    reason: str


@lru_cache(maxsize=4)
def load(path: Path = CONFIG) -> dict:
    return yaml.safe_load(Path(path).read_text())


def unsourced(technology: str, path: Path = CONFIG) -> list[str]:
    """The parameters of a technology that have no value or no source."""
    tech = load(path)["technologies"].get(technology)
    if tech is None:
        raise Refused(f"unknown technology {technology!r}; known: {sorted(load(path)['technologies'])}")
    missing = [p for p in PARAMETERS if (tech.get(p) or {}).get("value") is None or not (tech.get(p) or {}).get("source")]
    return missing + [f"message.{k}" for k, v in load(path)["message"].items() if v.get("value") is None or not v.get("source")]


def parameters(technology: str, path: Path = CONFIG) -> dict:
    """{parameter: value} of a technology, or Refused naming what has no source."""
    missing = unsourced(technology, path)
    if missing:
        raise Refused(f"{technology}: no sourced value for {', '.join(missing)}; the model does not guess one")
    cfg = load(path)
    return {**{p: cfg["technologies"][technology][p]["value"] for p in PARAMETERS}, **{k: v["value"] for k, v in cfg["message"].items()}}


def usable(path: Path = CONFIG) -> dict:
    """{technology: [] when usable, else the parameters without a source}."""
    return {t: unsourced(t, path) for t in load(path)["technologies"]}


def deliver(sender: Station, receiver: Station, time_s: float, technology: str, rng: random.Random, path: Path = CONFIG) -> Delivery:
    """Whether a message sent at `time_s` arrives, and after what delay. `time_s` is carried for implementations that
    read traces; this one does not depend on it."""
    p = parameters(technology, path)
    if math.hypot(sender.x - receiver.x, sender.y - receiver.y) > p["range_m"]:
        return Delivery(False, None, OUT_OF_RANGE)
    if rng.random() >= p["delivery_ratio_in_range"]:
        return Delivery(False, None, LOST)
    delay = p["delay_s"] * p["hops"]
    if delay > p["lifetime_s"]:
        return Delivery(False, None, EXPIRED)
    return Delivery(True, delay, IN_RANGE)
