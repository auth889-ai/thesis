"""Perception interfaces — camera → detections → tracks → traffic measurements."""
from .interfaces import (BoundingBox, Detection, Detector, Track, Tracker, TrafficSensor)

__all__ = ["BoundingBox", "Detection", "Detector", "Track", "Tracker", "TrafficSensor"]
