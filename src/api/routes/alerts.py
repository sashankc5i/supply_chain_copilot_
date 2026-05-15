"""GET /alerts -- current demand signals from the latest graph state."""
from __future__ import annotations

from fastapi import APIRouter, Query

from src.graph.nodes.detect import detect

router = APIRouter()

_latest: dict = {"run_id": "", "signals": []}


def set_latest_alerts(run_id: str, signals: list) -> None:
    _latest["run_id"] = run_id
    _latest["signals"] = signals


@router.get("/alerts")
def get_alerts(week_start: str = Query(default="2026-05-11")) -> list[dict]:
    """Return active alerts (post-detect) for the alert-list panel."""
    if _latest["signals"] and _latest.get("week_start") == week_start:
        return [
            {**s, "run_id": _latest["run_id"]}
            for s in _latest["signals"]
        ]

    state = detect({"week_start": week_start, "run_id": "api-alerts"})
    signals = state.get("demand_signals", [])
    _latest["week_start"] = week_start
    set_latest_alerts("api-alerts", signals)
    return [{**s, "run_id": _latest["run_id"]} for s in signals]
