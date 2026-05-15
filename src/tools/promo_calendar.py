"""promo_calendar tool -- active promotions for a SKU in a region for a date.

Day 1 stub: returns the seeded demo promo when SKU-1042 / West / 2026-01-12 is
queried, empty list otherwise. Phase 2 swaps in real reads against
`promotion_calendar.csv` via `src.data.loaders.load_promos`.
"""
from __future__ import annotations

if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from datetime import date

from langchain_core.tools import tool


@tool
def promo_calendar(sku_id: str, region: str, week_start: str) -> list[dict]:
    """Return all promotions overlapping `week_start` for a SKU in a region.

    Output schema (list of):
        {
          "promo_id": str, "sku_id": str, "region": str,
          "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD",
          "demand_lift_pct": float, "promo_type": "BOGO"|"discount"|"bundle",
          "channel": "in-store"|"online",
        }

    Args:
        sku_id: e.g. "SKU-1042".
        region: e.g. "West".
        week_start: ISO date string "YYYY-MM-DD" of the Monday of the target week.
    """
    if sku_id == "SKU-1042" and region == "West":
        return [{
            "promo_id": "PROMO-DEMO-001",
            "sku_id": "SKU-1042",
            "region": "West",
            "start_date": "2026-01-12",
            "end_date": "2026-01-25",
            "demand_lift_pct": 40.0,
            "promo_type": "BOGO",
            "channel": "in-store",
        }]
    return []
