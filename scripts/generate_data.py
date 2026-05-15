"""Generate synthetic supply-chain CSVs for the LangGraph copilot project.

Run once:
    python scripts/generate_data.py

Dependencies: pandas, numpy, faker

Outputs (under data/):
    raw/sku_master.csv               200 rows
    raw/location_master.csv          60 rows  (10 DCs + 50 stores)
    raw/promotion_calendar.csv       ~800 rows
    raw/weather_events.csv           ~500 rows
    raw/supplier_data.csv            600 rows (200 SKUs x 3 suppliers)
    raw/demand_history.csv           ~52,000 rows (500 SKU-store pairs x 104 weeks)
    raw/inventory_snapshot.csv       12,000 rows (200 SKUs x 60 locations)
    processed/anomalies_labeled.csv  ground-truth label file for evaluation
    runtime/action_log.csv           header-only, appended by graph at runtime

The three demo scenarios from the design doc are pre-seeded so the diagnose
node has matching signals to correlate:
    SKU-1042  West   Week 87   demand +120%   promo +40%   regional heatwave
    SKU-0217  South  Week 89   supplier delay 8 days       low DOH
    SKU-0089  East   Week 91   borderline z-score          high DOH (false alert)
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

SEED = 42
np.random.seed(SEED)
rng = np.random.default_rng(SEED)
fake = Faker()
Faker.seed(SEED)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
N_SKUS = 200
N_DCS = 10
N_STORES = 50
N_WEEKS = 104
ASSORTMENT_PER_STORE = 10          # 50 stores * 10 SKUs = 500 pairs -> 52,000 demand rows
N_PROMOS = 800
N_WEATHER_EVENTS = 500
SUPPLIERS_PER_SKU = 3

REGIONS = ["North", "South", "East", "West", "Central"]
CATEGORIES = ["Beverage", "Snack", "Dairy", "Frozen", "Bakery", "PersonalCare", "HouseholdCare"]

# Anchor "this week" -- inventory snapshot is taken on this Monday.
ANCHOR_DATE = date(2026, 5, 11)
START_DATE = ANCHOR_DATE - timedelta(weeks=N_WEEKS - 1)
WEEKS = [START_DATE + timedelta(weeks=w) for w in range(N_WEEKS)]

# Demo scenarios. Week index is 1-based (matches the design doc references).
DEMO = {
    "SKU-1042": {"category": "Beverage", "region": "West",  "week": 87,
                 "type": "spike",        "wow_multiplier": 2.2},
    "SKU-0217": {"category": "Dairy",    "region": "South", "week": 89,
                 "type": "drop",         "wow_multiplier": 0.5},
    "SKU-0089": {"category": "Snack",    "region": "East",  "week": 91,
                 "type": "borderline",   "wow_multiplier": 1.55},
}

ROOT = Path(__file__).resolve().parents[1]
OUT_RAW = ROOT / "data" / "raw"
OUT_PROC = ROOT / "data" / "processed"
OUT_RUN = ROOT / "data" / "runtime"
for p in (OUT_RAW, OUT_PROC, OUT_RUN):
    p.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# 1. SKU master
# ---------------------------------------------------------------------------
def generate_sku_master() -> pd.DataFrame:
    demo_nums = sorted(int(s.split("-")[1]) for s in DEMO)
    pool = [i for i in range(1, 1101) if i not in demo_nums]
    picks = rng.choice(pool, size=N_SKUS - len(demo_nums), replace=False)
    sku_nums = sorted(set(picks.tolist() + demo_nums))

    base_cost = {"Beverage": 2.5, "Snack": 1.5, "Dairy": 3.0, "Frozen": 4.5,
                 "Bakery": 2.0, "PersonalCare": 5.0, "HouseholdCare": 6.5}
    shelf = {"Beverage": 180, "Snack": 270, "Dairy": 21, "Frozen": 365,
             "Bakery": 14, "PersonalCare": 720, "HouseholdCare": 1095}
    abc_mult = {"A": 1.5, "B": 1.0, "C": 0.7}
    svc = {"A": 0.98, "B": 0.95, "C": 0.90}

    rows = []
    for num in sku_nums:
        sku_id = f"SKU-{num:04d}"
        if sku_id in DEMO:
            cat = DEMO[sku_id]["category"]
            abc = "A"
        else:
            cat = rng.choice(CATEGORIES)
            abc = rng.choice(["A", "B", "C"], p=[0.20, 0.30, 0.50])
        cost = round(base_cost[cat] * abc_mult[abc] * rng.uniform(0.85, 1.25), 2)
        rows.append({
            "sku_id": sku_id,
            "sku_name": f"{cat}-{sku_id.split('-')[1]}",
            "category": cat,
            "unit_cost": cost,
            "service_level_target": svc[abc],
            "abc_class": abc,
            "shelf_life_days": shelf[cat],
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 2. Location master
# ---------------------------------------------------------------------------
def generate_location_master() -> pd.DataFrame:
    rows = []
    dc_ids_by_region: dict[str, list[str]] = {r: [] for r in REGIONS}

    for i in range(1, N_DCS + 1):
        region = REGIONS[(i - 1) % len(REGIONS)]
        loc_id = f"DC-{i:03d}"
        dc_ids_by_region[region].append(loc_id)
        rows.append({
            "location_id": loc_id,
            "location_type": "DC",
            "region": region,
            "name": f"{region} DC {i}",
            "dc_id": "",
            "max_capacity": int(rng.integers(80_000, 160_000)),
            "transfer_cost_per_unit": round(rng.uniform(0.30, 0.90), 2),
        })

    for i in range(1, N_STORES + 1):
        region = REGIONS[(i - 1) % len(REGIONS)]
        loc_id = f"ST-{i:03d}"
        parent_dc = rng.choice(dc_ids_by_region[region])
        rows.append({
            "location_id": loc_id,
            "location_type": "store",
            "region": region,
            "name": f"{fake.city()} Store {i}",
            "dc_id": parent_dc,
            "max_capacity": int(rng.integers(2_000, 8_000)),
            "transfer_cost_per_unit": round(rng.uniform(1.00, 3.50), 2),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 3. Promotion calendar
# ---------------------------------------------------------------------------
def generate_promotion_calendar(sku_df: pd.DataFrame) -> pd.DataFrame:
    promo_types = ["BOGO", "discount", "bundle"]
    channels = ["in-store", "online"]
    sku_ids = sku_df.sku_id.values
    rows = []

    # Demo scenario 1: SKU-1042 West Week 87 +40% lift
    demo_start = WEEKS[86]
    rows.append({
        "promo_id": "PROMO-DEMO-001",
        "sku_id": "SKU-1042",
        "region": "West",
        "start_date": demo_start,
        "end_date": demo_start + timedelta(days=13),
        "demand_lift_pct": 40.0,
        "promo_type": "BOGO",
        "channel": "in-store",
    })

    for i in range(2, N_PROMOS + 1):
        sku = rng.choice(sku_ids)
        region = rng.choice(REGIONS)
        start_week = rng.integers(0, N_WEEKS - 1)
        duration_weeks = int(rng.integers(1, 5))
        start = WEEKS[start_week]
        end = start + timedelta(days=7 * duration_weeks - 1)
        lift = round(float(rng.uniform(5, 60)), 1)
        rows.append({
            "promo_id": f"PROMO-{i:04d}",
            "sku_id": sku,
            "region": region,
            "start_date": start,
            "end_date": end,
            "demand_lift_pct": lift,
            "promo_type": rng.choice(promo_types),
            "channel": rng.choice(channels),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 4. Weather / external events
# ---------------------------------------------------------------------------
def generate_weather_events() -> pd.DataFrame:
    event_types = ["weather", "holiday", "festival"]
    weather_names = ["Heatwave", "Storm", "Cold Snap", "Heavy Rain", "Snowstorm"]
    holidays = ["Independence Day", "Thanksgiving", "Christmas", "New Year", "Memorial Day", "Labor Day"]
    festivals = ["Music Fest", "Food Truck Rally", "Sports Final", "Local Carnival"]

    rows = []

    # Demo scenario 1: West heatwave Week 87, impacts Beverage + Frozen
    rows.append({
        "event_id" : "EVT-DEMO-001",
        "region": "West",
        "week_start": WEEKS[86],
        "event_type": "weather",
        "event_name": "Regional Heatwave",
        "demand_impact_pct": 12.0,
        "affected_categories": "Beverage|Frozen",
        "confidence": 0.82,
    })

    for i in range(2, N_WEATHER_EVENTS + 1):
        etype = rng.choice(event_types, p=[0.55, 0.25, 0.20])
        region = rng.choice(REGIONS)
        week_idx = int(rng.integers(0, N_WEEKS))
        if etype == "weather":
            name = rng.choice(weather_names)
            impact = round(float(rng.uniform(-15, 20)), 1)
            affected = "|".join(rng.choice(CATEGORIES, size=int(rng.integers(1, 4)), replace=False))
        elif etype == "holiday":
            name = rng.choice(holidays)
            impact = round(float(rng.uniform(10, 35)), 1)
            affected = "|".join(rng.choice(CATEGORIES, size=int(rng.integers(2, 5)), replace=False))
        else:
            name = rng.choice(festivals)
            impact = round(float(rng.uniform(5, 25)), 1)
            affected = "|".join(rng.choice(CATEGORIES, size=int(rng.integers(1, 3)), replace=False))
        rows.append({
            "event_id": f"EVT-{i:04d}",
            "region": region,
            "week_start": WEEKS[week_idx],
            "event_type": etype,
            "event_name": name,
            "demand_impact_pct": impact,
            "affected_categories": affected,
            "confidence": round(float(rng.uniform(0.4, 0.95)), 2),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 5. Supplier data
# ---------------------------------------------------------------------------
def generate_supplier_data(sku_df: pd.DataFrame) -> pd.DataFrame:
    delay_reasons = [
        "port congestion", "material shortage", "labor strike",
        "weather disruption", "quality hold", "customs delay",
    ]
    rows = []
    sup_counter = 1
    for sku_id in sku_df.sku_id:
        for s_idx in range(SUPPLIERS_PER_SKU):
            is_primary = s_idx == 0
            sup_id = f"SUP-{sup_counter:04d}"
            sup_counter += 1
            lead_time = int(rng.integers(3, 21))
            moq = int(rng.choice([100, 200, 250, 500, 1000]))
            reliability = round(float(rng.uniform(0.70, 0.99)), 2)

            # Demo scenario 2: SKU-0217 primary supplier delay 8 days
            if sku_id == "SKU-0217" and is_primary:
                delay_flag = True
                delay_days = 8
                reason = "port congestion"
                reliability = 0.71
            else:
                delay_flag = bool(rng.random() < 0.10)
                delay_days = int(rng.integers(2, 12)) if delay_flag else 0
                reason = str(rng.choice(delay_reasons)) if delay_flag else ""

            rows.append({
                "supplier_id": sup_id,
                "sku_id": sku_id,
                "lead_time_days": lead_time,
                "moq_units": moq,
                "delay_flag": delay_flag,
                "delay_days": delay_days,
                "delay_reason": reason,
                "reliability_score": reliability,
                "is_primary": is_primary,
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 6. Demand history (with realistic seasonality + injected anomalies)
# ---------------------------------------------------------------------------
def _build_assortment(sku_df: pd.DataFrame, loc_df: pd.DataFrame) -> list[tuple[str, str, str]]:
    """Map each store to ~10 SKUs. Force demo SKUs into their target regions."""
    stores = loc_df[loc_df.location_type == "store"]
    sku_ids = sku_df.sku_id.values
    pairs: list[tuple[str, str, str]] = []
    for _, store in stores.iterrows():
        forced = []
        if store.region == "West":
            forced.append("SKU-1042")
        if store.region == "South":
            forced.append("SKU-0217")
        if store.region == "East":
            forced.append("SKU-0089")
        remaining = ASSORTMENT_PER_STORE - len(forced)
        candidates = [s for s in sku_ids if s not in forced]
        picks = rng.choice(candidates, size=remaining, replace=False).tolist()
        for sid in forced + picks:
            pairs.append((sid, store.location_id, store.region))
    return pairs


def _seasonality(category: str, week_start: date) -> float:
    """Multiplicative seasonal factor in [0.7, 1.3] driven by week-of-year + category phase."""
    woy = week_start.isocalendar().week
    phase = {"Beverage": 26, "Snack": 0, "Dairy": 12, "Frozen": 26,
             "Bakery": 50, "PersonalCare": 0, "HouseholdCare": 0}[category]
    return 1.0 + 0.30 * np.sin(2 * np.pi * (woy - phase) / 52)


def generate_demand_history(sku_df: pd.DataFrame, loc_df: pd.DataFrame,
                            promo_df: pd.DataFrame, weather_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    assortment = _build_assortment(sku_df, loc_df)
    sku_info = sku_df.set_index("sku_id").to_dict("index")

    # Pre-index promos by (sku_id, region) -> list of (start, end, lift)
    promo_idx: dict[tuple[str, str], list[tuple[date, date, float]]] = {}
    for r in promo_df.itertuples():
        promo_idx.setdefault((r.sku_id, r.region), []).append((r.start_date, r.end_date, r.demand_lift_pct))

    # Pre-index weather by (region, week_start) -> list of (impact, affected_categories)
    weather_idx: dict[tuple[str, date], list[tuple[float, set[str]]]] = {}
    for r in weather_df.itertuples():
        cats = set(r.affected_categories.split("|"))
        weather_idx.setdefault((r.region, r.week_start), []).append((r.demand_impact_pct, cats))

    baselines: dict[tuple[str, str], float] = {}
    for sku, store, _ in assortment:
        abc = sku_info[sku]["abc_class"]
        if abc == "A":
            base = rng.uniform(80, 200)
        elif abc == "B":
            base = rng.uniform(30, 80)
        else:
            base = rng.uniform(5, 30)
        baselines[(sku, store)] = float(base)

    rows = []
    for sku, store, region in assortment:
        cat = sku_info[sku]["category"]
        base = baselines[(sku, store)]
        for week_start in WEEKS:
            season = _seasonality(cat, week_start)
            noise = rng.normal(1.0, 0.10)

            promo_lift = 1.0
            for s, e, lift_pct in promo_idx.get((sku, region), []):
                if s <= week_start <= e:
                    promo_lift *= (1 + lift_pct / 100)

            weather_lift = 1.0
            for impact, cats in weather_idx.get((region, week_start), []):
                if cat in cats:
                    weather_lift *= (1 + impact / 100)

            units = max(0.0, base * season * noise * promo_lift * weather_lift)
            rows.append((sku, store, week_start, region, units))

    df = pd.DataFrame(rows, columns=["sku_id", "store_id", "week_start", "region", "units_sold"])

    # --- Inject scenario-specific anomalies on top of natural baseline ---
    labels: list[dict] = []

    # Scenario 1: SKU-1042 West Week 87 spike (already lifted by promo+heatwave;
    # bump further so WoW delta hits ~+120%)
    wk87 = WEEKS[86]
    m = (df.sku_id == "SKU-1042") & (df.region == "West") & (df.week_start == wk87)
    df.loc[m, "units_sold"] *= DEMO["SKU-1042"]["wow_multiplier"]
    for _, r in df[m].iterrows():
        labels.append({"sku_id": r.sku_id, "store_id": r.store_id, "week_start": r.week_start,
                       "scenario": "promo_spike_heatwave", "ground_truth_cause": "promo+weather",
                       "expected_severity": "HIGH"})

    # Scenario 2: SKU-0217 South demand drop (weeks 88-91, supplier delay pulling sell-through down)
    for w in [87, 88, 89, 90]:
        wk = WEEKS[w]
        m = (df.sku_id == "SKU-0217") & (df.region == "South") & (df.week_start == wk)
        df.loc[m, "units_sold"] *= DEMO["SKU-0217"]["wow_multiplier"]
        if w == 88:
            for _, r in df[m].iterrows():
                labels.append({"sku_id": r.sku_id, "store_id": r.store_id, "week_start": r.week_start,
                               "scenario": "supplier_delay", "ground_truth_cause": "supplier_delay",
                               "expected_severity": "HIGH"})

    # Scenario 3: SKU-0089 East Week 91 borderline (~z=2.4)
    wk91 = WEEKS[90]
    m = (df.sku_id == "SKU-0089") & (df.region == "East") & (df.week_start == wk91)
    df.loc[m, "units_sold"] *= DEMO["SKU-0089"]["wow_multiplier"]
    for _, r in df[m].iterrows():
        labels.append({"sku_id": r.sku_id, "store_id": r.store_id, "week_start": r.week_start,
                       "scenario": "borderline_no_action", "ground_truth_cause": "noise",
                       "expected_severity": "MEDIUM"})

    # Flat-line data glitch: pick one SKU-store, force zero at week 100
    glitch_pair = assortment[rng.integers(0, len(assortment))]
    wk100 = WEEKS[99]
    m = ((df.sku_id == glitch_pair[0]) & (df.store_id == glitch_pair[1])
         & (df.week_start == wk100))
    df.loc[m, "units_sold"] = 0
    labels.append({"sku_id": glitch_pair[0], "store_id": glitch_pair[1], "week_start": wk100,
                   "scenario": "data_glitch", "ground_truth_cause": "data_anomaly",
                   "expected_severity": "LOW"})

    # Sprinkle ~30 extra organic anomalies so the system has work beyond the demo
    extra_pairs = rng.choice(len(assortment), size=30, replace=False)
    for idx in extra_pairs:
        sku, store, _ = assortment[idx]
        w = int(rng.integers(10, N_WEEKS - 5))
        wk = WEEKS[w]
        mult = float(rng.choice([0.3, 0.4, 1.8, 2.0, 2.3]))
        m = (df.sku_id == sku) & (df.store_id == store) & (df.week_start == wk)
        df.loc[m, "units_sold"] *= mult
        labels.append({"sku_id": sku, "store_id": store, "week_start": wk,
                       "scenario": "organic_anomaly", "ground_truth_cause": "unknown",
                       "expected_severity": "HIGH" if mult > 1.5 or mult < 0.4 else "MEDIUM"})

    df["units_sold"] = df["units_sold"].round().clip(lower=0).astype(int)

    # WoW delta % and rolling z-score (trailing 8-week mean/std, computed per pair)
    df = df.sort_values(["sku_id", "store_id", "week_start"]).reset_index(drop=True)
    df["wow_delta_pct"] = (
        df.groupby(["sku_id", "store_id"])["units_sold"]
          .pct_change()
          .fillna(0)
          .replace([np.inf, -np.inf], 0) * 100
    ).round(2)

    def _z(s: pd.Series) -> pd.Series:
        mean = s.rolling(8, min_periods=4).mean().shift(1)
        std = s.rolling(8, min_periods=4).std().shift(1).replace(0, np.nan)
        return ((s - mean) / std).fillna(0)

    df["zscore"] = (
        df.groupby(["sku_id", "store_id"])["units_sold"]
          .transform(_z)
          .round(3)
    )
    df["is_anomaly"] = (df["zscore"].abs() > 2.0) | (df["units_sold"] == 0)

    labels_df = pd.DataFrame(labels)
    return df, labels_df


# ---------------------------------------------------------------------------
# 7. Inventory snapshot (anchored to ANCHOR_DATE)
# ---------------------------------------------------------------------------
def generate_inventory_snapshot(sku_df: pd.DataFrame, loc_df: pd.DataFrame,
                                demand_df: pd.DataFrame) -> pd.DataFrame:
    # Average weekly demand per (sku, region) over trailing 8 weeks for DOH estimate
    recent = demand_df[demand_df.week_start >= WEEKS[N_WEEKS - 9]]
    avg_region_demand = (recent.groupby(["sku_id", "region"])["units_sold"]
                         .mean().rename("avg_weekly").reset_index())
    region_lookup = {(r.sku_id, r.region): r.avg_weekly for r in avg_region_demand.itertuples()}

    sku_info = sku_df.set_index("sku_id").to_dict("index")
    rows = []

    for sku in sku_df.sku_id:
        abc = sku_info[sku]["abc_class"]
        for _, loc in loc_df.iterrows():
            avg_weekly = region_lookup.get((sku, loc.region), 0.0)
            if loc.location_type == "DC":
                # DCs hold ~6-12 weeks of regional demand across all their stores
                weekly_dc_throughput = max(avg_weekly * N_STORES / N_DCS, 5.0)
                on_hand = weekly_dc_throughput * rng.uniform(6, 12)
                safety_stock = weekly_dc_throughput * 2
                reorder = weekly_dc_throughput * 4
            else:
                weekly_store = max(avg_weekly, 1.0) if avg_weekly > 0 else float(rng.uniform(2, 8))
                on_hand = weekly_store * rng.uniform(1.5, 4.0)
                safety_stock = weekly_store * 0.75
                reorder = weekly_store * 1.5

            # Demo: force tight DOH on demo SKU-region combos at store level
            if loc.location_type == "store":
                if sku == "SKU-1042" and loc.region == "West":
                    on_hand = max(avg_weekly, 50) * (3.1 / 7)
                elif sku == "SKU-0217" and loc.region == "South":
                    on_hand = max(avg_weekly, 30) * (4.8 / 7)
                elif sku == "SKU-0089" and loc.region == "East":
                    on_hand = max(avg_weekly, 20) * (18.0 / 7)

            daily_demand = max(avg_weekly / 7.0, 0.1)
            doh = round(on_hand / daily_demand, 2) if daily_demand > 0 else 999.0
            stockout_prob = round(float(np.clip(1.0 - (doh / 14.0), 0.0, 0.99)), 3)

            rows.append({
                "sku_id": sku,
                "location_id": loc.location_id,
                "location_type": loc.location_type,
                "units_on_hand": int(round(on_hand)),
                "days_on_hand": doh,
                "stockout_prob": stockout_prob,
                "reorder_point": int(round(reorder)),
                "safety_stock": int(round(safety_stock)),
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 8. Empty action log (header only)
# ---------------------------------------------------------------------------
def generate_action_log() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "run_id", "sku_id", "action_type", "recommendation",
        "approval_status", "approver", "rejection_reason", "timestamp",
    ])


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------
def main() -> None:
    print("Generating synthetic supply-chain data (seed=42)...")

    sku_df = generate_sku_master()
    print(f"  sku_master:           {len(sku_df):>6} rows")

    loc_df = generate_location_master()
    print(f"  location_master:      {len(loc_df):>6} rows")

    promo_df = generate_promotion_calendar(sku_df)
    print(f"  promotion_calendar:   {len(promo_df):>6} rows")

    weather_df = generate_weather_events()
    print(f"  weather_events:       {len(weather_df):>6} rows")

    supplier_df = generate_supplier_data(sku_df)
    print(f"  supplier_data:        {len(supplier_df):>6} rows")

    demand_df, labels_df = generate_demand_history(sku_df, loc_df, promo_df, weather_df)
    print(f"  demand_history:       {len(demand_df):>6} rows  ({int(demand_df.is_anomaly.sum())} flagged)")

    inv_df = generate_inventory_snapshot(sku_df, loc_df, demand_df)
    print(f"  inventory_snapshot:   {len(inv_df):>6} rows")

    action_df = generate_action_log()

    # Write files
    sku_df.to_csv(OUT_RAW / "sku_master.csv", index=False)
    loc_df.to_csv(OUT_RAW / "location_master.csv", index=False)
    promo_df.to_csv(OUT_RAW / "promotion_calendar.csv", index=False)
    weather_df.to_csv(OUT_RAW / "weather_events.csv", index=False)
    supplier_df.to_csv(OUT_RAW / "supplier_data.csv", index=False)
    demand_df.to_csv(OUT_RAW / "demand_history.csv", index=False)
    inv_df.to_csv(OUT_RAW / "inventory_snapshot.csv", index=False)
    labels_df.to_csv(OUT_PROC / "anomalies_labeled.csv", index=False)
    action_df.to_csv(OUT_RUN / "action_log.csv", index=False)

    print("\nDemo scenario sanity check")
    for sku, meta in DEMO.items():
        wk = WEEKS[meta["week"] - 1]
        slice_ = demand_df[(demand_df.sku_id == sku) & (demand_df.region == meta["region"])
                           & (demand_df.week_start == wk)]
        if not slice_.empty:
            print(f"  {sku} {meta['region']:7} wk{meta['week']:>3}  "
                  f"units_sold={int(slice_.units_sold.mean()):>4}  "
                  f"wow={slice_.wow_delta_pct.mean():>+6.1f}%  "
                  f"z={slice_.zscore.mean():>+5.2f}")
        inv_row = inv_df[(inv_df.sku_id == sku) & (inv_df.location_type == "store")
                         & inv_df.location_id.isin(
                            loc_df[loc_df.region == meta["region"]].location_id)]
        if not inv_row.empty:
            print(f"             store-level DOH mean = {inv_row.days_on_hand.mean():.2f} days")

    print(f"\nFiles written under: {ROOT}")
    print("Done.")


if __name__ == "__main__":
    main()
