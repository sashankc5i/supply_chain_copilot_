"""Detect node -- flags demand anomalies and assigns severity + anomaly_type.

Pure pandas. No LLM. Per design doc §7.2, must run in <5s on 200 SKUs x 50
stores. Reads demand_history.csv + inventory_snapshot.csv via the cached
loaders, computes a trailing z-score, joins inventory, and emits a list of
DemandSignal dicts plus an inventory_positions map for downstream nodes.

State inputs:
    week_start (str, ISO date)  -- target "current week" Monday.
                                   Defaults to ANCHOR_DATE if absent.

State outputs:
    demand_signals          -- list[DemandSignal] for every flagged sku/store
    inventory_positions     -- dict[sku_id, dict[location_id, inv_row]]
                               for every flagged SKU at every location

Severity rules (design doc §7.2):
    HIGH    DOH < 5 days
    MEDIUM  5 <= DOH <= 10
    LOW     DOH > 10
    unknown -> MEDIUM (no inventory row means we don't know -- err on caution)

Anomaly type:
    flat_line  units_sold == 0          (likely data glitch)
    spike      zscore >  +2
    drop       zscore <  -2
    normal     everything else
"""
from __future__ import annotations

if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import numpy as np
import pandas as pd

from src.data.loaders import ANCHOR_DATE, load_demand, load_inventory
from src.graph.state import SupplyChainState
from src.graph.tracing import log_node

TRAILING_WEEKS = 8
Z_THRESHOLD = 2.0
HIGH_DOH_MAX = 5.0
MEDIUM_DOH_MAX = 10.0


@log_node("detect")
def detect(state: SupplyChainState) -> dict:
    """Run anomaly detection on the target week and return state updates."""
    week_str = state.get("week_start") or ANCHOR_DATE.isoformat()
    target_week = pd.to_datetime(week_str).normalize()

    demand = load_demand()
    inventory = load_inventory()

    window_start = target_week - pd.Timedelta(weeks=TRAILING_WEEKS)
    window = demand[
        (demand["week_start"] >= window_start)
        & (demand["week_start"] <= target_week)
    ]
    if window.empty:
        return {"week_start": week_str, "demand_signals": [], "inventory_positions": {}}

    trailing = window[window["week_start"] < target_week]
    stats = (
        trailing.groupby(["sku_id", "store_id"])["units_sold"]
        .agg(rolling_mean="mean", rolling_std="std")
        .reset_index()
    )

    current = window[window["week_start"] == target_week].copy()
    if current.empty:
        return {"week_start": week_str, "demand_signals": [], "inventory_positions": {}}

    current = current.merge(stats, on=["sku_id", "store_id"], how="left")
    current["zscore"] = (
        (current["units_sold"] - current["rolling_mean"])
        / current["rolling_std"].replace(0, np.nan)
    ).fillna(0.0)

    flagged = current[
        (current["zscore"].abs() > Z_THRESHOLD) | (current["units_sold"] == 0)
    ].copy()
    if flagged.empty:
        return {"week_start": week_str, "demand_signals": [], "inventory_positions": {}}

    inv_store = inventory[inventory["location_type"] == "store"][[
        "sku_id", "location_id", "units_on_hand", "days_on_hand",
        "stockout_prob", "reorder_point", "safety_stock",
    ]]

    flagged = flagged.merge(
        inv_store,
        left_on=["sku_id", "store_id"],
        right_on=["sku_id", "location_id"],
        how="left",
    )

    flagged["severity"] = flagged["days_on_hand"].apply(_severity)
    flagged["anomaly_type"] = [
        _anomaly_type(u, z) for u, z in zip(flagged["units_sold"], flagged["zscore"])
    ]

    signals: list[dict] = []
    for r in flagged.itertuples(index=False):
        signals.append({
            "sku_id": r.sku_id,
            "store_id": r.store_id,
            "week_start": pd.Timestamp(r.week_start).strftime("%Y-%m-%d"),
            "units_sold": int(r.units_sold),
            "wow_delta_pct": _safe_float(getattr(r, "wow_delta_pct", 0.0)),
            "zscore": round(float(r.zscore), 3),
            "region": r.region,
            "severity": r.severity,
            "anomaly_type": r.anomaly_type,
        })

    flagged_skus = flagged["sku_id"].unique().tolist()
    inv_for_flagged = inventory[inventory["sku_id"].isin(flagged_skus)]
    positions: dict[str, dict] = {}
    for r in inv_for_flagged.itertuples(index=False):
        positions.setdefault(r.sku_id, {})[r.location_id] = {
            "location_type": r.location_type,
            "units_on_hand": int(r.units_on_hand),
            "days_on_hand": float(r.days_on_hand),
            "stockout_prob": float(r.stockout_prob),
            "reorder_point": int(r.reorder_point),
            "safety_stock": int(r.safety_stock),
        }

    return {
        "week_start": week_str,
        "demand_signals": signals,
        "inventory_positions": positions,
    }


def _severity(doh: float) -> str:
    if pd.isna(doh):
        return "MEDIUM"
    if doh < HIGH_DOH_MAX:
        return "HIGH"
    if doh <= MEDIUM_DOH_MAX:
        return "MEDIUM"
    return "LOW"


def _anomaly_type(units: float, z: float) -> str:
    if units == 0:
        return "flat_line"
    if z > Z_THRESHOLD:
        return "spike"
    if z < -Z_THRESHOLD:
        return "drop"
    return "normal"


def _safe_float(v) -> float:
    try:
        f = float(v)
        return round(f, 2) if not pd.isna(f) else 0.0
    except (TypeError, ValueError):
        return 0.0


if __name__ == "__main__":
    import time

    # Demo scenarios from the design doc (1-indexed weeks)
    # Week 87 = 2026-01-12, Week 89 = 2026-01-26, Week 91 = 2026-02-09
    cases = [
        ("Demo 1 - SKU-1042 spike (West, Wk87)",  "2026-01-12", "SKU-1042"),
        ("Demo 2 - SKU-0217 drop  (South, Wk89)", "2026-01-26", "SKU-0217"),
        ("Demo 3 - SKU-0089 borderline (East, Wk91)", "2026-02-09", "SKU-0089"),
        ("Default - latest week (Wk104, anchor)", None, None),
    ]

    for label, week, target_sku in cases:
        state = {"run_id": "detect-smoke"}
        if week:
            state["week_start"] = week

        t0 = time.perf_counter()
        out = detect(state)
        elapsed = time.perf_counter() - t0

        signals = out["demand_signals"]
        print(f"\n=== {label} ===")
        print(f"latency: {elapsed*1000:.0f} ms   flagged: {len(signals)}")

        if target_sku:
            hits = [s for s in signals if s["sku_id"] == target_sku]
            for s in hits[:3]:
                print(f"  {s['sku_id']} @ {s['store_id']} ({s['region']:7}) "
                      f"sev={s['severity']:6} type={s['anomaly_type']:9} "
                      f"z={s['zscore']:+.2f}  units={s['units_sold']}")
            if not hits:
                print(f"  (no rows for {target_sku} -- check the seed week)")
        else:
            sev_counts = {}
            for s in signals:
                sev_counts[s["severity"]] = sev_counts.get(s["severity"], 0) + 1
            print(f"  severity mix: {sev_counts}")
