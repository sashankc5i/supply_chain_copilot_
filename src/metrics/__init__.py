"""Business-metric utilities shared by detect, critique, eval, and dashboard.

Centralised so the formulas live in exactly one place. Drift between the
detect node's DOH and the eval harness's DOH would silently invalidate the
precision/recall numbers we report.
"""

if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.metrics.compute_doh import compute_doh
from src.metrics.stockout_prob import stockout_prob
from src.metrics.service_level import service_level

__all__ = ["compute_doh", "stockout_prob", "service_level"]
