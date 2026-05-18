"""Generate data/raw/dim_date.csv — one row per week in the demand calendar."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from src.data.loaders import DATA_RAW, load_demand

OUT = DATA_RAW / "dim_date.csv"


def main() -> None:
    demand = load_demand()
    weeks = (
        demand[["week_start"]]
        .drop_duplicates()
        .sort_values("week_start")
        .reset_index(drop=True)
    )
    weeks["week_start"] = pd.to_datetime(weeks["week_start"])
    weeks["date_id"] = weeks["week_start"].dt.strftime("%Y%m%d")
    weeks["year"] = weeks["week_start"].dt.year
    weeks["quarter"] = weeks["week_start"].dt.quarter
    weeks["month"] = weeks["week_start"].dt.month
    weeks["iso_week"] = weeks["week_start"].dt.isocalendar().week.astype(int)
    weeks["week_start"] = weeks["week_start"].dt.strftime("%Y-%m-%d")
    weeks["is_holiday"] = False

    weeks.to_csv(OUT, index=False)
    print(f"Wrote {len(weeks)} rows to {OUT}")


if __name__ == "__main__":
    main()
