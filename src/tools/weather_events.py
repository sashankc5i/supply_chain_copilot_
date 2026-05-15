"""weather_events tool -- regional weather/holiday/festival events for a week.

Day 1 stub: returns the seeded demo heatwave when West / 2026-01-12 is queried,
empty list otherwise. Phase 2 swaps in real reads against `weather_events.csv`
via `src.data.loaders.load_weather`.
"""
from __future__ import annotations

if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from langchain_core.tools import tool


@tool
def weather_events(region: str, week_start: str) -> list[dict]:
    """Return weather/holiday/festival events for a region on a given week.

    Output schema (list of):
        {
          "event_id": str, "region": str, "week_start": "YYYY-MM-DD",
          "event_type": "weather"|"holiday"|"festival",
          "event_name": str, "demand_impact_pct": float,
          "affected_categories": list[str], "confidence": float,
        }

    Args:
        region: e.g. "West".
        week_start: ISO date string "YYYY-MM-DD" of the Monday of the target week.
    """
    if region == "West":
        return [{
            "event_id": "EVT-DEMO-001",
            "region": "West",
            "week_start": "2026-01-12",
            "event_type": "weather",
            "event_name": "Regional Heatwave",
            "demand_impact_pct": 12.0,
            "affected_categories": ["Beverage", "Frozen"],
            "confidence": 0.82,
        }]
    return []
