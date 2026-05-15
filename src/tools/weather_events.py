"""weather_events tool -- regional weather/holiday/festival events for a week.

Real implementation: filters `weather_events.csv` via the cached
`src.data.loaders.load_weather()` for events matching region and week_start.
The `affected_categories` column is stored as pipe-separated string in the
CSV; this tool splits it into a `list[str]` for downstream consumers.
"""
from __future__ import annotations

if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd

from src.data.loaders import load_weather
from src.tools._compat import tool


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
    weather = load_weather()
    week = pd.to_datetime(week_start).normalize()

    mask = (weather["region"] == region) & (weather["week_start"] == week)
    rows = weather[mask]

    out = []
    for r in rows.itertuples(index=False):
        cats_raw = r.affected_categories
        cats = cats_raw.split("|") if isinstance(cats_raw, str) and cats_raw else []
        out.append({
            "event_id": str(r.event_id),
            "region": str(r.region),
            "week_start": r.week_start.strftime("%Y-%m-%d"),
            "event_type": str(r.event_type),
            "event_name": str(r.event_name),
            "demand_impact_pct": round(float(r.demand_impact_pct), 1),
            "affected_categories": cats,
            "confidence": round(float(r.confidence), 2),
        })
    return out
