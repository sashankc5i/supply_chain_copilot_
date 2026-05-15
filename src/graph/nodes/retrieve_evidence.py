"""retrieve_evidence node -- parallel evidence retrieval for the focal anomaly.

Identifies the strongest HIGH-severity signal in state["demand_signals"] (max
abs zscore), then calls 4 tools concurrently via a ThreadPoolExecutor:

    promo_calendar (sku, region, week_start)
    weather_events (region, week_start)
    supplier_delays (sku)
    demand_lookup  (sku, store, weeks=8, anchor_week=week_start)

Returns a structured evidence dict keyed by source. Each block follows the
shape locked in interface_spec.md:

    {
      "source": <filename or system>,
      "data":   <tool output>,
      "confidence": <0-1 float>,
      "estimated_impact_pct": <signed float>,
    }

ThreadPoolExecutor (vs asyncio) keeps the node sync from LangGraph's POV
while still parallelising the 4 lookups. Latency is bounded by the slowest
tool (typically demand_lookup, ~30-60ms on cached loaders).
"""
from __future__ import annotations

if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from concurrent.futures import ThreadPoolExecutor

from src.graph.state import SupplyChainState
from src.tools.demand_lookup import demand_lookup
from src.tools.promo_calendar import promo_calendar
from src.tools.supplier_delays import supplier_delays
from src.tools.weather_events import weather_events


def retrieve_evidence(state: SupplyChainState) -> dict:
    """Gather promo/weather/supplier/demand evidence for the strongest HIGH signal."""
    signals = state.get("demand_signals") or []
    high = [s for s in signals if s.get("severity") == "HIGH"]
    if not high:
        return {"evidence": {}}

    focal = max(high, key=lambda s: abs(s.get("zscore", 0.0)))
    sku, store = focal["sku_id"], focal["store_id"]
    region, week = focal["region"], focal["week_start"]

    with ThreadPoolExecutor(max_workers=4) as ex:
        f_promo = ex.submit(_call, promo_calendar,
                            sku_id=sku, region=region, week_start=week)
        f_weather = ex.submit(_call, weather_events,
                              region=region, week_start=week)
        f_supplier = ex.submit(_call, supplier_delays, sku_id=sku)
        f_demand = ex.submit(_call, demand_lookup,
                             sku_id=sku, store_id=store, weeks=8, anchor_week=week)
        promo = f_promo.result()
        weather = f_weather.result()
        supplier = f_supplier.result()
        demand = f_demand.result()

    return {"evidence": _assemble(promo, weather, supplier, demand)}


def _call(fn, **kwargs):
    """Call a @tool-decorated function whether it's wrapped (StructuredTool) or plain."""
    return fn.invoke(kwargs) if hasattr(fn, "invoke") else fn(**kwargs)


def _assemble(promo: list, weather: list, supplier: list, demand: dict) -> dict:
    """Build the canonical evidence dict per interface_spec.md."""
    return {
        "promo": {
            "source": "promotion_calendar.csv",
            "data": promo,
            "confidence": 0.95 if promo else 0.50,
            "estimated_impact_pct": sum(p["demand_lift_pct"] for p in promo),
        },
        "weather": {
            "source": "weather_events.csv",
            "data": weather,
            "confidence": _avg([e["confidence"] for e in weather]) if weather else 0.50,
            "estimated_impact_pct": sum(e["demand_impact_pct"] for e in weather),
        },
        "supplier": {
            "source": "supplier_data.csv",
            "data": supplier,
            "confidence": 0.95,
            # Rough: each delayed day shifts effective supply ~5% downward.
            "estimated_impact_pct": -5.0 * sum(
                s["delay_days"] for s in supplier if s["delay_flag"]
            ),
        },
        "demand": {
            "source": "demand_history.csv",
            "data": demand,
            "confidence": 1.00,
            "estimated_impact_pct": demand.get("latest_wow_delta_pct", 0.0),
        },
    }


def _avg(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


if __name__ == "__main__":
    import json
    import time

    from src.graph.nodes.detect import detect as detect_node

    def run(label: str, week_start: str) -> None:
        print(f"\n{'=' * 72}\nSCENARIO  {label}\n{'=' * 72}")
        state: dict = {"run_id": f"re-{label}", "week_start": week_start}
        state.update(detect_node(state))

        high = [s for s in state["demand_signals"] if s["severity"] == "HIGH"]
        if not high:
            print("no HIGH signals -- skipping")
            return
        focal = max(high, key=lambda s: abs(s["zscore"]))
        print(f"focal:  {focal['sku_id']} @ {focal['store_id']} ({focal['region']})  "
              f"z={focal['zscore']:+.2f}  type={focal['anomaly_type']}")

        t0 = time.perf_counter()
        out = retrieve_evidence(state)
        elapsed = (time.perf_counter() - t0) * 1000

        print(f"latency: {elapsed:.0f} ms\n")
        for k, block in out["evidence"].items():
            n = len(block["data"]) if isinstance(block["data"], list) else "dict"
            print(f"  {k:8} records={n!s:>4}  confidence={block['confidence']:.2f}  "
                  f"impact={block['estimated_impact_pct']:+.1f}%  "
                  f"source={block['source']}")

    run("Demo-1 SKU-1042 / West / Wk87", "2026-01-12")
    run("Demo-2 SKU-0217 / South / Wk89", "2026-01-26")
    run("Demo-3 SKU-0089 / East / Wk91", "2026-02-09")
