"""inventory_lookup tool -- on-hand, DOH, reorder point, safety stock.

Real implementation: point lookup against `inventory_snapshot.csv` via the
cached `src.data.loaders.load_inventory()`. Returns zero-valued defaults if
the (sku, location) pair isn't present (typical for SKUs not stocked at
that location).
"""
from __future__ import annotations

if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.data.loaders import load_inventory
from src.tools._compat import tool


@tool
def inventory_lookup(sku_id: str, location_id: str) -> dict:
    """Return current inventory position for a SKU at a store or DC.

    Output schema:
        {
          "sku_id": str, "location_id": str, "location_type": "store"|"DC",
          "units_on_hand": int, "days_on_hand": float, "stockout_prob": float,
          "reorder_point": int, "safety_stock": int,
        }

    Args:
        sku_id: e.g. "SKU-1042".
        location_id: e.g. "ST-007" (store) or "DC-003" (distribution center).
    """
    inv = load_inventory()
    row = inv[(inv["sku_id"] == sku_id) & (inv["location_id"] == location_id)]

    if row.empty:
        return {
            "sku_id": sku_id,
            "location_id": location_id,
            "location_type": "DC" if location_id.startswith("DC") else "store",
            "units_on_hand": 0,
            "days_on_hand": 0.0,
            "stockout_prob": 0.0,
            "reorder_point": 0,
            "safety_stock": 0,
        }

    r = row.iloc[0]
    return {
        "sku_id": sku_id,
        "location_id": location_id,
        "location_type": str(r["location_type"]),
        "units_on_hand": int(r["units_on_hand"]),
        "days_on_hand": round(float(r["days_on_hand"]), 2),
        "stockout_prob": round(float(r["stockout_prob"]), 3),
        "reorder_point": int(r["reorder_point"]),
        "safety_stock": int(r["safety_stock"]),
    }
