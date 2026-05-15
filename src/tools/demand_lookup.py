"""demand_lookup tool -- weekly demand series + WoW delta + z-score.

Real implementation: reads `demand_history.csv` via the cached
`src.data.loaders.load_demand()` and slices the trailing N weeks for the
specified (sku_id, store_id). Z-score and WoW delta are pre-computed at
data-generation time, so this tool is a pure point lookup.
"""
from __future__ import annotations

if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd

from src.data.loaders import load_demand
from src.tools._compat import tool


@tool
def demand_lookup(sku_id: str, store_id: str, weeks: int = 8,
                  anchor_week: str | None = None) -> dict:
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
        anchor_week: optional ISO date "YYYY-MM-DD". If provided, returns
            the `weeks` rows ending at this date (inclusive) -- use this to
            get context AROUND an anomaly week, not the latest data.
            Default: latest week available for that (sku, store).
    """
    demand = load_demand()
    df = demand[(demand["sku_id"] == sku_id) & (demand["store_id"] == store_id)]

    if anchor_week:
        anchor = pd.to_datetime(anchor_week).normalize()
        df = df[df["week_start"] <= anchor]

    df = df.sort_values("week_start").tail(weeks)

    if df.empty:
        return {
            "sku_id": sku_id, "store_id": store_id,
            "weeks_returned": 0, "series": [],
            "latest_zscore": 0.0, "latest_wow_delta_pct": 0.0,
        }

    series = []
    for r in df.itertuples(index=False):
        ws = r.week_start.strftime("%Y-%m-%d") if hasattr(r.week_start, "strftime") else str(r.week_start)
        series.append({
            "week_start": ws,
            "units_sold": int(r.units_sold),
            "wow_delta_pct": round(float(r.wow_delta_pct), 2),
            "zscore": round(float(r.zscore), 3),
        })

    return {
        "sku_id": sku_id,
        "store_id": store_id,
        "weeks_returned": len(series),
        "series": series,
        "latest_zscore": series[-1]["zscore"],
        "latest_wow_delta_pct": series[-1]["wow_delta_pct"],
    }
