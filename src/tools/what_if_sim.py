"""what_if_sim tool -- project DOH + stockout prob under an order/promo tweak.

Day 1 stub: simple linear projection. Phase 2 wires in real demand/inventory
joins via `src.data.loaders` and (optionally) a small forecast model.
"""
from __future__ import annotations

if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from langchain_core.tools import tool


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
    baseline_doh = 3.1
    daily_demand = 16.0
    projected_doh = baseline_doh + (qty_adjust / daily_demand)
    # Promo shifts pull demand earlier/later -- crude linear effect on DOH.
    projected_doh -= 0.04 * promo_shift_days

    def _stockout(doh: float) -> float:
        return max(0.0, min(0.99, 1.0 - (doh / 14.0)))

    return {
        "sku_id": sku_id,
        "store_id": store_id,
        "qty_adjust": qty_adjust,
        "promo_shift_days": promo_shift_days,
        "baseline_doh": round(baseline_doh, 2),
        "projected_doh": round(projected_doh, 2),
        "baseline_stockout_prob": round(_stockout(baseline_doh), 3),
        "projected_stockout_prob": round(_stockout(projected_doh), 3),
        "delta_units": qty_adjust,
        "notes": "Day-1 stub: linear DOH projection only.",
    }
