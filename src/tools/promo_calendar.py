"""promo_calendar tool -- active promotions for a SKU in a region on a date.

Real implementation: filters `promotion_calendar.csv` via the cached
`src.data.loaders.load_promos()` for promos whose date range overlaps the
requested week. Returns an empty list when no promos are active.
"""
from __future__ import annotations

if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd

from src.data.loaders import load_promos
from src.tools._compat import tool


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
    promos = load_promos()
    week = pd.to_datetime(week_start).normalize()

    mask = (
        (promos["sku_id"] == sku_id)
        & (promos["region"] == region)
        & (promos["start_date"] <= week)
        & (promos["end_date"] >= week)
    )
    rows = promos[mask]

    out = []
    for r in rows.itertuples(index=False):
        out.append({
            "promo_id": str(r.promo_id),
            "sku_id": str(r.sku_id),
            "region": str(r.region),
            "start_date": r.start_date.strftime("%Y-%m-%d"),
            "end_date": r.end_date.strftime("%Y-%m-%d"),
            "demand_lift_pct": round(float(r.demand_lift_pct), 1),
            "promo_type": str(r.promo_type),
            "channel": str(r.channel),
        })
    return out
