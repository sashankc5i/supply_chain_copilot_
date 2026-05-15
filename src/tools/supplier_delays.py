"""supplier_delays tool -- supplier roster + active delay flags for a SKU.

Real implementation: filters `supplier_data.csv` via the cached
`src.data.loaders.load_suppliers()` for the requested SKU. Sorts primary
suppliers first so callers can take `[0]` to get the main supplier.
"""
from __future__ import annotations

if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.data.loaders import load_suppliers
from src.tools._compat import tool


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
    sup = load_suppliers()
    rows = sup[sup["sku_id"] == sku_id].sort_values("is_primary", ascending=False)

    out = []
    for r in rows.itertuples(index=False):
        reason = r.delay_reason
        out.append({
            "supplier_id": str(r.supplier_id),
            "sku_id": str(r.sku_id),
            "lead_time_days": int(r.lead_time_days),
            "moq_units": int(r.moq_units),
            "delay_flag": bool(r.delay_flag),
            "delay_days": int(r.delay_days),
            "delay_reason": str(reason) if isinstance(reason, str) else "",
            "reliability_score": round(float(r.reliability_score), 2),
            "is_primary": bool(r.is_primary),
        })
    return out
