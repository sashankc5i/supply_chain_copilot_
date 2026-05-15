"""inventory_lookup tool -- on-hand, DOH, reorder point, safety stock.

Day 1 stub: hardcoded sample. Phase 2 swaps in real CSV reads against
`inventory_snapshot.csv` via `src.data.loaders.load_inventory`.
"""
from __future__ import annotations

if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from langchain_core.tools import tool


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
    loc_type = "DC" if location_id.startswith("DC") else "store"
    return {
        "sku_id": sku_id,
        "location_id": location_id,
        "location_type": loc_type,
        "units_on_hand": 50,
        "days_on_hand": 3.1,
        "stockout_prob": 0.78,
        "reorder_point": 80,
        "safety_stock": 30,
    }
