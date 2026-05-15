"""what_if_sim tool -- project DOH + stockout prob under an order/promo tweak.

Real implementation: pulls the baseline DOH from `inventory_snapshot.csv` and
recent average daily demand from `demand_history.csv`, then applies a simple
linear projection:

    projected_doh = baseline_doh + (qty_adjust / avg_daily_demand)
                                   - 0.04 * promo_shift_days

Stockout probability is the same clipped heuristic the data generator used:
`max(0, 1 - doh/14)`. A real implementation would plug in a forecast model;
this version is the deterministic placeholder the design doc allows.
"""
from __future__ import annotations

if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.data.loaders import load_demand, load_inventory
from src.tools._compat import tool

STOCKOUT_HORIZON_DAYS = 14.0
PROMO_SHIFT_DOH_PER_DAY = 0.04  # placeholder linear coefficient


@tool
def what_if_sim(sku_id: str, store_id: str,
                qty_adjust: int = 0, promo_shift_days: int = 0) -> dict:
    """Project the impact of an order-qty change or promo date shift.

    Output schema:
        {
          "sku_id": str, "store_id": str,
          "qty_adjust": int, "promo_shift_days": int,
          "baseline_doh": float, "projected_doh": float,
          "baseline_stockout_prob": float, "projected_stockout_prob": float,
          "delta_units": int, "notes": str,
        }

    Args:
        sku_id: e.g. "SKU-1042".
        store_id: e.g. "ST-007".
        qty_adjust: extra (or negative) units added to the planned order.
        promo_shift_days: shift the active promo by N days (positive = later).
    """
    inv = load_inventory()
    inv_row = inv[(inv["sku_id"] == sku_id) & (inv["location_id"] == store_id)]
    if inv_row.empty:
        baseline_doh = 0.0
        baseline_on_hand = 0
    else:
        baseline_doh = float(inv_row.iloc[0]["days_on_hand"])
        baseline_on_hand = int(inv_row.iloc[0]["units_on_hand"])

    demand = load_demand()
    recent = (
        demand[(demand["sku_id"] == sku_id) & (demand["store_id"] == store_id)]
        .sort_values("week_start")
        .tail(8)
    )
    avg_weekly = float(recent["units_sold"].mean()) if not recent.empty else 7.0
    avg_daily = max(avg_weekly / 7.0, 0.1)

    projected_doh = baseline_doh + (qty_adjust / avg_daily)
    projected_doh -= PROMO_SHIFT_DOH_PER_DAY * promo_shift_days

    def _stockout(doh: float) -> float:
        return max(0.0, min(0.99, 1.0 - (doh / STOCKOUT_HORIZON_DAYS)))

    return {
        "sku_id": sku_id,
        "store_id": store_id,
        "qty_adjust": int(qty_adjust),
        "promo_shift_days": int(promo_shift_days),
        "baseline_doh": round(baseline_doh, 2),
        "projected_doh": round(projected_doh, 2),
        "baseline_stockout_prob": round(_stockout(baseline_doh), 3),
        "projected_stockout_prob": round(_stockout(projected_doh), 3),
        "delta_units": int(qty_adjust),
        "notes": (
            f"baseline_on_hand={baseline_on_hand}, "
            f"avg_daily_demand={avg_daily:.1f}u/day. "
            "Linear DOH projection; promo shift uses 0.04 days-per-day-shift placeholder."
        ),
    }
