"""Unit tests for deterministic critique constraint rules."""
from __future__ import annotations

import pytest

from src.graph.nodes.critique import BUDGET_CAP_USD, critique


def _transfer_rec(qty: int = 400, cost: float = 1200.0) -> dict:
    return {
        "action_type": "transfer_inventory",
        "params": {
            "qty_units": qty,
            "source_locations": ["DC-001"],
            "destination_location_id": "ST-007",
            "timeline_days": 3,
        },
        "cost_usd": cost,
        "confidence": 0.9,
        "doh_improvement_days": 5.0,
    }


def _expedite_rec(qty: int = 500, cost: float = 3000.0) -> dict:
    return {
        "action_type": "expedite_order",
        "params": {"qty_units": qty, "supplier_id": "SUP-001", "timeline_days": 5},
        "cost_usd": cost,
        "confidence": 0.85,
        "doh_improvement_days": 4.0,
    }


def _base_state(**overrides) -> dict:
    state = {
        "run_id": "test-critique",
        "demand_signals": [{
            "sku_id": "SKU-TEST",
            "store_id": "ST-001",
            "week_start": "2026-01-12",
            "units_sold": 100,
            "wow_delta_pct": 50.0,
            "zscore": 3.0,
            "region": "West",
            "severity": "HIGH",
            "anomaly_type": "spike",
        }],
        "inventory_positions": {
            "SKU-TEST": {
                "DC-001": {
                    "units_on_hand": 500,
                    "safety_stock": 100,
                    "days_on_hand": 10.0,
                },
                "ST-001": {
                    "units_on_hand": 50,
                    "days_on_hand": 2.0,
                },
            },
        },
        "evidence": {
            "supplier": {
                "data": [{
                    "supplier_id": "SUP-001",
                    "lead_time_days": 14,
                    "moq_units": 200,
                    "delay_flag": False,
                }],
            },
            "demand": {
                "data": {"trailing_mean": 70.0},
            },
        },
        "retry_count": 0,
    }
    state.update(overrides)
    return state


def test_budget_cap_rejected():
    out = critique(_base_state(recommendations=[_transfer_rec(cost=BUDGET_CAP_USD + 1)]))
    cr = out["critique_result"]
    assert cr["verdict"] == "rejected"
    assert cr["violated_constraint"] == "budget_cap"


def test_transfer_safety_stock_rejected():
    out = critique(_base_state(recommendations=[_transfer_rec(qty=450)]))
    cr = out["critique_result"]
    assert cr["verdict"] == "rejected"
    assert cr["violated_constraint"] == "safety_stock"


def test_transfer_approved():
    out = critique(_base_state(recommendations=[_transfer_rec(qty=200)]))
    assert out["critique_result"]["verdict"] == "approved"


def test_expedite_moq_rejected():
    out = critique(_base_state(recommendations=[_expedite_rec(qty=50)]))
    cr = out["critique_result"]
    assert cr["verdict"] == "rejected"
    assert cr["violated_constraint"] == "moq"


def test_expedite_lead_time_rejected():
    out = critique(_base_state(recommendations=[_expedite_rec(qty=500)]))
    cr = out["critique_result"]
    assert cr["verdict"] == "rejected"
    assert cr["violated_constraint"] == "supplier_lead_time"


def test_expedite_approved_when_lead_time_short():
    state = _base_state(recommendations=[_expedite_rec(qty=500)])
    state["evidence"]["supplier"]["data"][0]["lead_time_days"] = 1
    state["inventory_positions"]["SKU-TEST"]["ST-001"]["days_on_hand"] = 5.0
    out = critique(state)
    assert out["critique_result"]["verdict"] == "approved"


def test_no_recommendations_rejected():
    out = critique(_base_state(recommendations=[]))
    assert out["critique_result"]["verdict"] == "rejected"
