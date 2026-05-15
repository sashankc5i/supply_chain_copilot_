"""Tests for shared action_log header detection."""
from __future__ import annotations

from pathlib import Path

from src.api.action_log import action_log_needs_header


def test_needs_header_when_missing(tmp_path: Path) -> None:
    assert action_log_needs_header(tmp_path / "missing.csv") is True


def test_needs_header_when_empty(tmp_path: Path) -> None:
    p = tmp_path / "log.csv"
    p.write_text("", encoding="utf-8")
    assert action_log_needs_header(p) is True


def test_needs_header_when_newline_only(tmp_path: Path) -> None:
    p = tmp_path / "log.csv"
    p.write_text("\n", encoding="utf-8")
    assert action_log_needs_header(p) is True


def test_no_header_when_run_id_present(tmp_path: Path) -> None:
    p = tmp_path / "log.csv"
    p.write_text(
        "run_id,sku_id,action_type\n",
        encoding="utf-8",
    )
    assert action_log_needs_header(p) is False
