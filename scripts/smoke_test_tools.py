"""Smoke test for the 6 real tool implementations.

Run from project root:
    python scripts/smoke_test_tools.py

Doesn't need langchain installed -- _compat.py supplies a no-op @tool when
langchain_core is missing. With or without langchain, each tool function is
directly callable and returns the schema documented in interface_spec.md.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.tools._compat import tool as _tool_decorator  # noqa: F401  (warm cache)
from src.tools.demand_lookup import demand_lookup
from src.tools.inventory_lookup import inventory_lookup
from src.tools.promo_calendar import promo_calendar
from src.tools.weather_events import weather_events
from src.tools.supplier_delays import supplier_delays
from src.tools.what_if_sim import what_if_sim


def _call(fn, **kwargs):
    """Call tool whether wrapped by @tool (StructuredTool) or plain function."""
    if hasattr(fn, "invoke"):
        return fn.invoke(kwargs)
    return fn(**kwargs)


def _print_header(title: str) -> None:
    print(f"\n{'-' * 6} {title} {'-' * 6}")


def main() -> None:
    # Demo scenario 1: SKU-1042 promo+heatwave spike, West, week of 2026-01-12
    print("=" * 70)
    print("DEMO 1 -- SKU-1042 West Week 87 (promo + heatwave spike)")
    print("=" * 70)

    _print_header("demand_lookup(SKU-1042, ST-004, weeks=4)")
    r = _call(demand_lookup, sku_id="SKU-1042", store_id="ST-004", weeks=4)
    print(f"weeks_returned={r['weeks_returned']}  latest_z={r['latest_zscore']}  "
          f"latest_wow={r['latest_wow_delta_pct']}%")
    for s in r["series"]:
        print(f"  {s['week_start']}  units={s['units_sold']:>4}  "
              f"wow={s['wow_delta_pct']:>+7.1f}%  z={s['zscore']:>+6.2f}")

    _print_header("inventory_lookup(SKU-1042, ST-004)")
    r = _call(inventory_lookup, sku_id="SKU-1042", location_id="ST-004")
    print(f"on_hand={r['units_on_hand']}  DOH={r['days_on_hand']}d  "
          f"stockout_prob={r['stockout_prob']}  reorder={r['reorder_point']}  "
          f"safety={r['safety_stock']}")

    _print_header("promo_calendar(SKU-1042, West, 2026-01-12)")
    rs = _call(promo_calendar, sku_id="SKU-1042", region="West", week_start="2026-01-12")
    print(f"promos found: {len(rs)}")
    for p in rs:
        print(f"  {p['promo_id']}  {p['promo_type']} {p['demand_lift_pct']}%  "
              f"{p['start_date']} -> {p['end_date']}  channel={p['channel']}")

    _print_header("weather_events(West, 2026-01-12)")
    rs = _call(weather_events, region="West", week_start="2026-01-12")
    print(f"events found: {len(rs)}")
    for e in rs:
        print(f"  {e['event_id']}  {e['event_type']:8} {e['event_name']:25}  "
              f"impact={e['demand_impact_pct']:>+6.1f}%  cats={e['affected_categories']}  "
              f"conf={e['confidence']}")

    _print_header("supplier_delays(SKU-1042)")
    rs = _call(supplier_delays, sku_id="SKU-1042")
    print(f"suppliers: {len(rs)}")
    for s in rs:
        flag = "DELAY" if s["delay_flag"] else "ok"
        primary = "primary" if s["is_primary"] else "alt    "
        print(f"  {s['supplier_id']}  {primary}  lead={s['lead_time_days']:>2}d  "
              f"MOQ={s['moq_units']:>4}  rel={s['reliability_score']:.2f}  {flag}  "
              f"{s['delay_reason']}")

    _print_header("what_if_sim(SKU-1042, ST-004, qty_adjust=200)")
    r = _call(what_if_sim, sku_id="SKU-1042", store_id="ST-004", qty_adjust=200, promo_shift_days=0)
    print(f"baseline DOH={r['baseline_doh']}d -> projected DOH={r['projected_doh']}d")
    print(f"baseline stockout={r['baseline_stockout_prob']} -> "
          f"projected stockout={r['projected_stockout_prob']}")
    print(f"notes: {r['notes']}")

    # Demo scenario 2: SKU-0217 South, Week 89 (supplier delay)
    print("\n" + "=" * 70)
    print("DEMO 2 -- SKU-0217 South Week 89 (supplier delay)")
    print("=" * 70)

    _print_header("supplier_delays(SKU-0217)")
    rs = _call(supplier_delays, sku_id="SKU-0217")
    for s in rs:
        flag = "DELAY" if s["delay_flag"] else "ok"
        primary = "primary" if s["is_primary"] else "alt    "
        print(f"  {s['supplier_id']}  {primary}  lead={s['lead_time_days']:>2}d  "
              f"MOQ={s['moq_units']:>4}  rel={s['reliability_score']:.2f}  {flag}  "
              f"{s['delay_reason']}")

    _print_header("demand_lookup(SKU-0217, ST-002, weeks=5)")
    r = _call(demand_lookup, sku_id="SKU-0217", store_id="ST-002", weeks=5)
    for s in r["series"]:
        print(f"  {s['week_start']}  units={s['units_sold']:>4}  "
              f"wow={s['wow_delta_pct']:>+7.1f}%  z={s['zscore']:>+6.2f}")

    # Demo scenario 3: SKU-0089 East Week 91 (borderline; should look noisy not actionable)
    print("\n" + "=" * 70)
    print("DEMO 3 -- SKU-0089 East Week 91 (borderline; no real cause)")
    print("=" * 70)

    _print_header("promo_calendar(SKU-0089, East, 2026-02-09)")
    rs = _call(promo_calendar, sku_id="SKU-0089", region="East", week_start="2026-02-09")
    print(f"promos: {len(rs)}  (expect 0 -- this is a no-cause scenario)")

    _print_header("weather_events(East, 2026-02-09)")
    rs = _call(weather_events, region="East", week_start="2026-02-09")
    print(f"events: {len(rs)}  (expect 0 or unrelated)")
    for e in rs:
        print(f"  {e['event_id']}  {e['event_name']}  cats={e['affected_categories']}")

    _print_header("inventory_lookup(SKU-0089, ST-003) -- expect healthy DOH (~18)")
    r = _call(inventory_lookup, sku_id="SKU-0089", location_id="ST-003")
    print(f"on_hand={r['units_on_hand']}  DOH={r['days_on_hand']}d")

    print("\nAll 6 tools smoke-tested.\n")


if __name__ == "__main__":
    main()
