"""Cached pandas readers for the synthetic supply-chain CSVs.

Every loader is zero-arg, type-annotated, and wrapped in `lru_cache` so callers
(nodes, tools, dashboard, eval harness) can import freely without worrying
about repeated disk I/O. Date columns are parsed at read time so downstream
code works with `datetime64` directly.

Re-generate the CSVs with `python scripts/generate_data.py` then call
`reload_all()` (or restart the process) to bust the cache.
"""
from __future__ import annotations

if __package__ in (None, ""):
    import sys
    from pathlib import Path as _Path
    sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

from datetime import date
from functools import lru_cache
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = ROOT / "data" / "raw"
DATA_PROC = ROOT / "data" / "processed"
DATA_RUN = ROOT / "data" / "runtime"
DATA_REF = ROOT / "data" / "reference"     # P5 official-dataset extracts (reference only)

ANCHOR_DATE = date(2026, 5, 11)


@lru_cache(maxsize=1)
def load_skus() -> pd.DataFrame:
    return pd.read_csv(DATA_RAW / "sku_master.csv")


@lru_cache(maxsize=1)
def load_locations() -> pd.DataFrame:
    return pd.read_csv(DATA_RAW / "location_master.csv")


@lru_cache(maxsize=1)
def load_demand() -> pd.DataFrame:
    return pd.read_csv(
        DATA_RAW / "demand_history.csv",
        parse_dates=["week_start"],
    )


@lru_cache(maxsize=1)
def load_inventory() -> pd.DataFrame:
    return pd.read_csv(DATA_RAW / "inventory_snapshot.csv")


@lru_cache(maxsize=1)
def load_promos() -> pd.DataFrame:
    return pd.read_csv(
        DATA_RAW / "promotion_calendar.csv",
        parse_dates=["start_date", "end_date"],
    )


@lru_cache(maxsize=1)
def load_weather() -> pd.DataFrame:
    return pd.read_csv(
        DATA_RAW / "weather_events.csv",
        parse_dates=["week_start"],
    )


@lru_cache(maxsize=1)
def load_suppliers() -> pd.DataFrame:
    return pd.read_csv(DATA_RAW / "supplier_data.csv")


@lru_cache(maxsize=1)
def load_labeled_anomalies() -> pd.DataFrame:
    return pd.read_csv(
        DATA_PROC / "anomalies_labeled.csv",
        parse_dates=["week_start"],
    )


def load_action_log() -> pd.DataFrame:
    """Runtime-written file. Not cached -- callers want fresh reads."""
    return pd.read_csv(
        DATA_RUN / "action_log.csv",
        parse_dates=["timestamp"] if _has_rows(DATA_RUN / "action_log.csv") else None,
    )


def load_reference(filename: str):
    """Load a borrowed P5-dataset artifact from `data/reference/`.

    Reference files are **not aligned with our generated SKU/store IDs** --
    use them for design inspiration, eval templates, and gold-standard
    examples only. See `data/reference/README.md` for the catalogue.

    Returns a `pd.DataFrame` for .csv files and a parsed Python object
    (dict / list) for .json files. Markdown is returned as a string.
    """
    import json

    path = DATA_REF / filename
    if not path.exists():
        raise FileNotFoundError(
            f"{filename} not found under data/reference/. "
            "Did you extract P5_LangGraph_SupplyChain_SyntheticDataset.zip?"
        )
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix == ".json":
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    if suffix == ".md":
        return path.read_text(encoding="utf-8")
    raise ValueError(f"Unsupported reference file type: {suffix}")


def reload_all() -> None:
    """Bust every cached loader. Call after regenerating CSVs in-process."""
    for fn in (
        load_skus, load_locations, load_demand, load_inventory,
        load_promos, load_weather, load_suppliers, load_labeled_anomalies,
    ):
        fn.cache_clear()


def _has_rows(path: Path) -> bool:
    with open(path, "r", encoding="utf-8") as f:
        next(f, None)
        return next(f, None) is not None


__all__ = [
    "ROOT", "DATA_RAW", "DATA_PROC", "DATA_RUN", "DATA_REF", "ANCHOR_DATE",
    "load_skus", "load_locations", "load_demand", "load_inventory",
    "load_promos", "load_weather", "load_suppliers",
    "load_labeled_anomalies", "load_action_log",
    "load_reference", "reload_all",
]
