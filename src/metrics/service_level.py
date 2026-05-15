"""Service level (proxy fill rate) per SKU x store over a trailing window.

Our synthetic data has only `units_sold` -- there is no separate
"units_demanded" column to compare against. So we approximate:

    service_level = fraction of trailing weeks with units_sold > 0

The intuition: a week with zero sold units is a stockout proxy (we assume
non-zero true demand for an active SKU; a zero on the books means we
couldn't fulfill). This is conservative -- a SKU with genuinely no demand
that week would also score down. Critique uses this as a soft signal; the
canonical demand-side service level lives in `service_level_target` on
`sku_master.csv`.
"""
from __future__ import annotations

if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd


def service_level(demand_df: pd.DataFrame, sku_id: str, store_id: str,
                  weeks: int = 8) -> float:
    """Return proxy fill rate in [0, 1] for the trailing `weeks` weeks.

    Args:
        demand_df: typically `src.data.loaders.load_demand()` (cached).
        sku_id, store_id: the SKU x store pair to score.
        weeks: trailing window. Default 8 (matches detect's z-score window).

    Returns:
        Fraction of weeks where `units_sold > 0`. Returns 0.0 if no rows match.
    """
    window = (
        demand_df[(demand_df["sku_id"] == sku_id) & (demand_df["store_id"] == store_id)]
        .sort_values("week_start")
        .tail(weeks)
    )
    if window.empty:
        return 0.0
    return float((window["units_sold"] > 0).mean())
