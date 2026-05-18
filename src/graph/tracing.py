"""Node-level tracing for the supply-chain copilot.

Substitute for LangSmith: every node that wraps its function with the
`@log_node(name)` decorator appends one row to
`data/runtime/node_latency.csv` capturing timing, input/output sizes, and
the routing decision.

Usage in a node file::

    from src.graph.tracing import log_node

    @log_node("detect")
    def detect(state: SupplyChainState) -> dict:
        ...

The decorator is transparent — it passes `state` through unchanged, records
the timing, and returns the original node output.

CSV columns:
    run_id, node_name, input_keys, output_keys, latency_ms, routing_decision, timestamp
"""
from __future__ import annotations

import csv
import sys
import time
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_LOG_PATH = ROOT / "data" / "runtime" / "node_latency.csv"
_FIELDNAMES = [
    "run_id", "node_name", "input_keys", "output_keys",
    "latency_ms", "routing_decision", "timestamp",
]


def _ensure_header() -> None:
    """Create the CSV with a header row if it does not yet exist; migrate older schemas."""
    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not _LOG_PATH.exists():
        with open(_LOG_PATH, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=_FIELDNAMES).writeheader()
        return
    with open(_LOG_PATH, "r", encoding="utf-8", newline="") as f:
        header = f.readline().strip().lstrip("\ufeff")
    if "routing_decision" not in header:
        import pandas as pd
        df = pd.read_csv(_LOG_PATH)
        df["routing_decision"] = ""
        df.to_csv(_LOG_PATH, index=False)


def _append_row(row: dict) -> None:
    _ensure_header()
    full = {k: row.get(k, "") for k in _FIELDNAMES}
    with open(_LOG_PATH, "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=_FIELDNAMES).writerow(full)


def log_node(name: str) -> Callable:
    """Decorator factory — wraps a LangGraph node function with timing/logging."""

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(state: dict) -> dict:
            run_id = state.get("run_id", "") if isinstance(state, dict) else ""
            input_keys = sorted(k for k, v in state.items() if v is not None) if isinstance(state, dict) else []

            t0 = time.perf_counter()
            result = fn(state)
            latency_ms = (time.perf_counter() - t0) * 1000

            output_keys = sorted(result.keys()) if isinstance(result, dict) else []

            _append_row({
                "run_id": run_id,
                "node_name": name,
                "input_keys": "|".join(input_keys),
                "output_keys": "|".join(output_keys),
                "latency_ms": round(latency_ms, 1),
                "routing_decision": "",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            return result

        return wrapper

    return decorator


def log_routing(state: dict, after_node: str, decision: str) -> None:
    """Record a conditional-edge routing decision (substitute for LangSmith branch labels)."""
    run_id = state.get("run_id", "") if isinstance(state, dict) else ""
    _append_row({
        "run_id": run_id,
        "node_name": f"route_after_{after_node}",
        "input_keys": "",
        "output_keys": "",
        "latency_ms": 0.0,
        "routing_decision": str(decision),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
