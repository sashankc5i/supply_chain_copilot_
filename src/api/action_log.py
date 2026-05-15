"""Append rows to data/runtime/action_log.csv."""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ACTION_LOG_PATH = ROOT / "data" / "runtime" / "action_log.csv"

FIELDNAMES = [
    "run_id", "sku_id", "action_type", "recommendation",
    "approval_status", "approver", "rejection_reason", "timestamp",
]

_HEADER_MARKER = "run_id"


def action_log_needs_header(path: Path = ACTION_LOG_PATH) -> bool:
    """True when the CSV is missing, empty, whitespace-only, or lacks a header row."""
    if not path.exists():
        return True
    if path.stat().st_size == 0:
        return True
    with path.open("r", encoding="utf-8", newline="") as f:
        first = f.readline()
    stripped = first.lstrip("\ufeff").strip()
    if not stripped:
        return True
    return not stripped.startswith(_HEADER_MARKER)


def append_action_log(
    *,
    run_id: str,
    sku_id: str,
    action_type: str,
    recommendation: dict,
    approval_status: str,
    approver: str = "operator@command-center",
    rejection_reason: str = "",
) -> None:
    ACTION_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "run_id": run_id,
        "sku_id": sku_id,
        "action_type": action_type,
        "recommendation": json.dumps(recommendation, default=str),
        "approval_status": approval_status,
        "approver": approver,
        "rejection_reason": rejection_reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    write_header = action_log_needs_header()
    with open(ACTION_LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if write_header:
            writer.writeheader()
        writer.writerow(row)
