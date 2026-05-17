"""Critique node -- deterministic constraint checker (no LLM).

Validates the top-ranked recommendation against four rule families:
  1. transfer_inventory: source DC DOH after move >= safety_stock
  2. expedite_order: supplier lead_time < days-to-stockout
  3. expedite_order: qty >= supplier MOQ
  4. any action: cost_usd <= budget cap ($5,000 default)
"""
from __future__ import annotations

if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.graph.state import SupplyChainState
from src.graph.tracing import log_node
from src.tools.inventory_lookup import inventory_lookup
from src.tools.supplier_delays import supplier_delays


def _call_tool(fn, **kwargs):
    return fn.invoke(kwargs) if hasattr(fn, "invoke") else fn(**kwargs)

BUDGET_CAP_USD = 5000.0


@log_node("critique")
def critique(state: SupplyChainState) -> dict:
    """Check top recommendation against business constraints."""
    recs = state.get("recommendations") or []
    if not recs:
        return {
            "critique_result": {
                "verdict": "rejected",
                "top_action": None,
                "violated_constraint": "no_recommendations",
                "reason": "No recommendations to validate.",
            },
        }

    top = recs[0]
    signals = state.get("demand_signals") or []
    high = [s for s in signals if s.get("severity") == "HIGH"]
    focal = max(high, key=lambda s: abs(s.get("zscore", 0.0))) if high else {}
    store_id = focal.get("store_id", "")
    sku_id = focal.get("sku_id", "")

    violation = _check_constraints(top, sku_id, store_id, state)
    retry = state.get("retry_count", 0)

    if violation is None:
        result = {
            "verdict": "approved",
            "top_action": top,
            "violated_constraint": "",
            "reason": "All constraints satisfied.",
        }
        return {"critique_result": result}

    result = {
        "verdict": "rejected",
        "top_action": top,
        "violated_constraint": violation[0],
        "reason": violation[1],
    }
    return {"critique_result": result}


def _check_constraints(
    rec: dict,
    sku_id: str,
    store_id: str,
    state: SupplyChainState,
) -> tuple[str, str] | None:
    action = rec.get("action_type", "")
    params = rec.get("params") or {}
    cost = float(rec.get("cost_usd", 0))

    if cost > BUDGET_CAP_USD:
        return (
            "budget_cap",
            f"cost_usd ${cost:,.0f} exceeds budget cap ${BUDGET_CAP_USD:,.0f}.",
        )

    if action == "transfer_inventory":
        return _check_transfer(rec, sku_id, params, state)
    if action == "expedite_order":
        return _check_expedite(rec, sku_id, store_id, params, state)
    return None


def _check_transfer(
    rec: dict,
    sku_id: str,
    params: dict,
    state: SupplyChainState,
) -> tuple[str, str] | None:
    qty = int(params.get("qty_units", 0))
    sources = params.get("source_locations") or []
    if not sources:
        return ("safety_stock", "transfer_inventory requires source_locations.")

    positions = (state.get("inventory_positions") or {}).get(sku_id, {})
    for src in sources:
        inv = positions.get(src)
        if inv is None:
            inv = _call_tool(inventory_lookup, sku_id=sku_id, location_id=src)
        on_hand = int(inv.get("units_on_hand", 0))
        safety = int(inv.get("safety_stock", 0))
        avg_daily = _avg_daily_demand(sku_id, state)
        doh_after = (on_hand - qty) / avg_daily if avg_daily > 0 else 0.0
        safety_doh = safety / avg_daily if avg_daily > 0 else float(safety)
        if doh_after < safety_doh:
            return (
                "safety_stock",
                f"Source {src} DOH after transfer ({doh_after:.1f}d) would fall "
                f"below safety-stock floor ({safety_doh:.1f}d).",
            )
    return None


def _check_expedite(
    rec: dict,
    sku_id: str,
    store_id: str,
    params: dict,
    state: SupplyChainState,
) -> tuple[str, str] | None:
    qty = int(params.get("qty_units", 0))
    supplier_id = params.get("supplier_id")

    suppliers = _suppliers_for_sku(sku_id, state)
    if not suppliers:
        return ("supplier_lead_time", f"No supplier data for {sku_id}.")

    supplier = None
    for s in suppliers:
        if supplier_id and s.get("supplier_id") == supplier_id:
            supplier = s
            break
    if supplier is None:
        supplier = suppliers[0]

    moq = int(supplier.get("moq_units", 0))
    if qty < moq:
        return (
            "moq",
            f"Ordered qty {qty} is below supplier MOQ {moq} units.",
        )

    lead_time = int(supplier.get("lead_time_days", 999))
    days_to_stockout = _days_to_stockout(sku_id, store_id, state)
    if lead_time >= days_to_stockout:
        return (
            "supplier_lead_time",
            f"Supplier lead time ({lead_time}d) is not less than days-to-stockout "
            f"({days_to_stockout:.1f}d).",
        )
    return None


def _suppliers_for_sku(sku_id: str, state: SupplyChainState) -> list[dict]:
    evidence = state.get("evidence") or {}
    block = evidence.get("supplier") or {}
    data = block.get("data")
    if isinstance(data, list) and data:
        return data
    return _call_tool(supplier_delays, sku_id=sku_id)


def _days_to_stockout(sku_id: str, store_id: str, state: SupplyChainState) -> float:
    positions = (state.get("inventory_positions") or {}).get(sku_id, {})
    inv = positions.get(store_id)
    if inv is None:
        inv = _call_tool(inventory_lookup, sku_id=sku_id, location_id=store_id)
    return max(float(inv.get("days_on_hand", 0)), 0.1)


def _avg_daily_demand(sku_id: str, state: SupplyChainState) -> float:
    evidence = state.get("evidence") or {}
    demand = (evidence.get("demand") or {}).get("data") or {}
    if isinstance(demand, dict):
        mean = demand.get("trailing_mean") or demand.get("rolling_mean")
        if mean:
            return max(float(mean) / 7.0, 1.0)
    signals = state.get("demand_signals") or []
    for s in signals:
        if s.get("sku_id") == sku_id:
            return max(float(s.get("units_sold", 100)) / 7.0, 1.0)
    return 10.0
