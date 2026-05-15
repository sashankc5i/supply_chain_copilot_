"""LangChain @tool wrappers used by retrieve_evidence and other nodes."""

# Self-bootstrap so this module can also be loaded when the project root
# isn't already on sys.path (e.g. running a sibling script directly).
if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.tools.demand_lookup import demand_lookup
from src.tools.inventory_lookup import inventory_lookup
from src.tools.promo_calendar import promo_calendar
from src.tools.weather_events import weather_events
from src.tools.supplier_delays import supplier_delays
from src.tools.what_if_sim import what_if_sim

ALL_TOOLS = [
    demand_lookup,
    inventory_lookup,
    promo_calendar,
    weather_events,
    supplier_delays,
    what_if_sim,
]

__all__ = [
    "demand_lookup", "inventory_lookup", "promo_calendar",
    "weather_events", "supplier_delays", "what_if_sim", "ALL_TOOLS",
]
