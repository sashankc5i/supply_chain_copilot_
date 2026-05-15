"""demand_lookup tool -- weekly demand series + WoW delta + z-score.

Day 1 stub: returns hardcoded sample for SKU-1042 / ST-001. Phase 2 swaps in
real CSV reads against `demand_history.csv` via `src.data.loaders.load_demand`.
"""
from __future__ import annotations

if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from langchain_core.tools import tool


@tool
def demand_lookup(sku_id: str, store_id: str, weeks: int = 8) -> dict:
    """Return the trailing `weeks` of weekly demand for a SKU at a store.

    Output schema:
        {
          "sku_id": str, "store_id": str, "weeks_returned": int,
          "series": [
            {"week_start": "YYYY-MM-DD", "units_sold": int,
             "wow_delta_pct": float, "zscore": float},
            ...
          ],
          "latest_zscore": float, "latest_wow_delta_pct": float,
        }

    Args:
        sku_id: e.g. "SKU-1042".
        store_id: e.g. "ST-007".
        weeks: trailing window length. Default 8.
    """
    sample_series = [
        {"week_start": "2026-03-23", "units_sold":  95, "wow_delta_pct":  -2.1, "zscore": -0.2},
        {"week_start": "2026-03-30", "units_sold": 102, "wow_delta_pct":   7.4, "zscore":  0.3},
        {"week_start": "2026-04-06", "units_sold":  98, "wow_delta_pct":  -3.9, "zscore": -0.1},
        {"week_start": "2026-04-13", "units_sold": 110, "wow_delta_pct":  12.2, "zscore":  0.6},
        {"week_start": "2026-04-20", "units_sold": 105, "wow_delta_pct":  -4.5, "zscore":  0.2},
        {"week_start": "2026-04-27", "units_sold": 100, "wow_delta_pct":  -4.8, "zscore":  0.0},
        {"week_start": "2026-05-04", "units_sold": 115, "wow_delta_pct":  15.0, "zscore":  0.9},
        {"week_start": "2026-05-11", "units_sold": 253, "wow_delta_pct": 120.0, "zscore":  3.4},
    ]
    return {
        "sku_id": sku_id,
        "store_id": store_id,
        "weeks_returned": min(weeks, len(sample_series)),
        "series": sample_series[-weeks:],
        "latest_zscore": sample_series[-1]["zscore"],
        "latest_wow_delta_pct": sample_series[-1]["wow_delta_pct"],
    }
