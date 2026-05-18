"""Ensure week_start survives LangGraph invoke (schema must include it)."""
from __future__ import annotations

import uuid

from src.graph.graph import app


def test_week_start_preserved_in_final_state():
    week = "2026-01-12"
    run_id = f"test-week-{uuid.uuid4().hex[:8]}"
    out = app.invoke(
        {"run_id": run_id, "week_start": week, "sku_id": "SKU-1042"},
        config={"configurable": {"thread_id": run_id}},
    )
    assert out.get("week_start") == week
