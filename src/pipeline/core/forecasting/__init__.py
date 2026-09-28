"""Forecasting interfaces — Labs 07-12 (baselines, DCRNN, Graph WaveNet, STID,"""
from .interfaces import (ForecastRequest, ForecastResult, TrafficForecaster)

__all__ = ["ForecastRequest", "ForecastResult", "TrafficForecaster"]
