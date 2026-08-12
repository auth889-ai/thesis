"""NLP interfaces — Lab 24: incident text → structured events that actually feed"""
from .interfaces import (IncidentExtractor, IncidentType, Severity, TrafficIncident)

__all__ = ["IncidentExtractor", "IncidentType", "Severity", "TrafficIncident"]
