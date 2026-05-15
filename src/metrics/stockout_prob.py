"""Stockout probability heuristic.

Linear clip on DOH-vs-horizon. The synthetic data generator uses this same
formula -- keep them aligned so eval ground-truth doesn't drift from runtime.
"""
from __future__ import annotations

if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import math

DEFAULT_HORIZON_DAYS = 14.0
MAX_PROB = 0.99   # never claim certainty -- there's always some forecast noise
MIN_PROB = 0.0


def stockout_prob(doh: float, horizon_days: float = DEFAULT_HORIZON_DAYS) -> float:
    """Probability of stockout within `horizon_days`, given current DOH.

    Formula: clamp(1 - doh/horizon_days, 0, 0.99).
    - DOH = 0       -> 0.99 (essentially stocked out now)
    - DOH = horizon -> 0.00 (covered for the full window)
    - DOH >= horizon -> 0.00 (capped)
    - DOH = inf (no demand) -> 0.00

    Args:
        doh: days-on-hand. Use `compute_doh()` to derive.
        horizon_days: planning horizon. Default 14d (matches data generator).
    """
    if math.isinf(doh) or doh >= horizon_days:
        return MIN_PROB
    if doh <= 0:
        return MAX_PROB
    return max(MIN_PROB, min(MAX_PROB, 1.0 - (doh / horizon_days)))
