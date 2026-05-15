"""Unit tests for src.metrics. Run from project root:

    pytest tests/ -v
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import pytest

from src.metrics import compute_doh, service_level, stockout_prob


# ---------------------------------------------------------------------------
# compute_doh
# ---------------------------------------------------------------------------
class TestComputeDOH:
    def test_normal_case(self):
        # 70 units / 10 units per day = 7 days
        assert compute_doh(70, 10) == 7.0

    def test_fractional(self):
        assert compute_doh(50, 7) == pytest.approx(7.142857, rel=1e-4)

    def test_zero_on_hand(self):
        assert compute_doh(0, 10) == 0.0

    def test_negative_on_hand_clamped(self):
        # Defensive: real data shouldn't go negative, but if it does -> stockout
        assert compute_doh(-5, 10) == 0.0

    def test_zero_demand_means_infinite_doh(self):
        # No demand = inventory lasts forever
        assert compute_doh(100, 0) == math.inf

    def test_both_zero(self):
        # Zero stock + zero demand: stockout convention wins
        assert compute_doh(0, 0) == 0.0


# ---------------------------------------------------------------------------
# stockout_prob
# ---------------------------------------------------------------------------
class TestStockoutProb:
    def test_zero_doh_returns_max(self):
        assert stockout_prob(0) == 0.99

    def test_full_horizon_returns_zero(self):
        assert stockout_prob(14) == 0.0

    def test_beyond_horizon_returns_zero(self):
        assert stockout_prob(30) == 0.0

    def test_midpoint(self):
        assert stockout_prob(7) == pytest.approx(0.5, rel=1e-6)

    def test_quarter_horizon(self):
        # DOH 3.5 -> 1 - 3.5/14 = 0.75
        assert stockout_prob(3.5) == pytest.approx(0.75, rel=1e-6)

    def test_infinite_doh_returns_zero(self):
        assert stockout_prob(math.inf) == 0.0

    def test_custom_horizon(self):
        # 7d horizon: DOH 3.5 -> 1 - 3.5/7 = 0.5
        assert stockout_prob(3.5, horizon_days=7) == pytest.approx(0.5, rel=1e-6)


# ---------------------------------------------------------------------------
# service_level
# ---------------------------------------------------------------------------
class TestServiceLevel:
    @staticmethod
    def _make_df(sold: list[int], sku="SKU-A", store="ST-A") -> pd.DataFrame:
        return pd.DataFrame({
            "sku_id": [sku] * len(sold),
            "store_id": [store] * len(sold),
            "week_start": pd.date_range("2026-01-05", periods=len(sold), freq="7D"),
            "units_sold": sold,
        })

    def test_all_weeks_sold(self):
        df = self._make_df([10, 12, 14, 11, 9, 13, 15, 10])
        assert service_level(df, "SKU-A", "ST-A", weeks=8) == 1.0

    def test_one_zero_week(self):
        df = self._make_df([10, 12, 0, 11, 9, 13, 15, 10])
        assert service_level(df, "SKU-A", "ST-A", weeks=8) == pytest.approx(0.875)

    def test_half_zero_weeks(self):
        df = self._make_df([0, 12, 0, 11, 0, 13, 0, 10])
        assert service_level(df, "SKU-A", "ST-A", weeks=8) == pytest.approx(0.5)

    def test_no_rows_returns_zero(self):
        df = self._make_df([10, 10, 10])
        assert service_level(df, "SKU-B", "ST-B", weeks=8) == 0.0

    def test_trailing_window_respects_weeks_arg(self):
        # 10 weeks of data; weeks=4 should only see the last 4 (all 0s)
        df = self._make_df([10] * 6 + [0] * 4)
        assert service_level(df, "SKU-A", "ST-A", weeks=4) == 0.0
        assert service_level(df, "SKU-A", "ST-A", weeks=10) == pytest.approx(0.6)
