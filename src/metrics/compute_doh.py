"""Compute Days-on-Hand from on-hand units + average daily demand.

Canonical formula used by detect, critique, what_if_sim, and the eval harness.
Keep all DOH math here -- duplicate calls in nodes would invite drift.
"""
from __future__ import annotations

if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import math


def compute_doh(units_on_hand: float, avg_daily_demand: float) -> float:
    """Return days-of-cover for a given on-hand inventory and daily run-rate.

    Conventions:
        units_on_hand  <= 0   ->  0.0  (stocked out)
        avg_daily_demand <= 0 ->  inf  (no demand at all, DOH is unbounded)

    Args:
        units_on_hand: integer or float; current units in stock at the location.
        avg_daily_demand: average units sold per day over the relevant lookback
            window. Compute as `weekly_demand_mean / 7`.

    Returns:
        Days-of-cover as a float. Callers downstream cap or bucket as needed
        (e.g. detect node uses HIGH < 5, MEDIUM <= 10, LOW > 10).
    """
    if units_on_hand <= 0:
        return 0.0
    if avg_daily_demand <= 0:
        return math.inf
    return float(units_on_hand) / float(avg_daily_demand)
