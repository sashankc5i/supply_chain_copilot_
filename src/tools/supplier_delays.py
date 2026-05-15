"""supplier_delays tool -- supplier roster + active delay flags for a SKU.

Day 1 stub: returns 3 suppliers per SKU. SKU-0217 primary supplier has the
seeded 8-day port-congestion delay. Phase 2 swaps in real reads against
`supplier_data.csv` via `src.data.loaders.load_suppliers`.
"""
from __future__ import annotations

if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from langchain_core.tools import tool


@tool
def supplier_delays(sku_id: str) -> list[dict]:
    """Return all suppliers for a SKU with lead time, MOQ, and active delay info.

    Output schema (list of):
        {
          "supplier_id": str, "sku_id": str, "lead_time_days": int,
          "moq_units": int, "delay_flag": bool, "delay_days": int,
          "delay_reason": str, "reliability_score": float, "is_primary": bool,
        }

    Args:
        sku_id: e.g. "SKU-0217".
    """
    if sku_id == "SKU-0217":
        return [
            {"supplier_id": "SUP-0001", "sku_id": sku_id,
             "lead_time_days": 14, "moq_units": 500, "delay_flag": True,
             "delay_days": 8, "delay_reason": "port congestion",
             "reliability_score": 0.71, "is_primary": True},
            {"supplier_id": "SUP-0002", "sku_id": sku_id,
             "lead_time_days": 21, "moq_units": 1000, "delay_flag": False,
             "delay_days": 0, "delay_reason": "",
             "reliability_score": 0.88, "is_primary": False},
            {"supplier_id": "SUP-0003", "sku_id": sku_id,
             "lead_time_days": 10, "moq_units": 250, "delay_flag": False,
             "delay_days": 0, "delay_reason": "",
             "reliability_score": 0.93, "is_primary": False},
        ]
    return [
        {"supplier_id": "SUP-9001", "sku_id": sku_id,
         "lead_time_days": 12, "moq_units": 500, "delay_flag": False,
         "delay_days": 0, "delay_reason": "",
         "reliability_score": 0.90, "is_primary": True},
        {"supplier_id": "SUP-9002", "sku_id": sku_id,
         "lead_time_days": 18, "moq_units": 1000, "delay_flag": False,
         "delay_days": 0, "delay_reason": "",
         "reliability_score": 0.85, "is_primary": False},
    ]
