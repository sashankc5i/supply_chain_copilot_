"""End-to-end smoke checks without Streamlit.

Usage:
    python scripts/smoke_e2e.py

Exits 0 on success, 1 on failure.
"""
from __future__ import annotations

import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv()

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from src.graph.graph import build_graph, route_after_detect
from src.graph.nodes.detect import detect


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def main() -> None:
    print("=== smoke_e2e ===\n")

    demand = ROOT / "data" / "raw" / "demand_history.csv"
    if not demand.exists():
        print("Data missing — running generate_data.py ...")
        subprocess.check_call([sys.executable, str(ROOT / "scripts" / "generate_data.py")])

    print("[1] pytest ...")
    subprocess.check_call([sys.executable, "-m", "pytest", "tests/", "-q"], cwd=ROOT)

    print("[2] detect Demo 1 week_start preserved ...")
    d1 = detect({"week_start": "2026-01-12"})
    assert d1.get("week_start") == "2026-01-12", "detect must echo week_start"
    route = route_after_detect(d1)
    if route != "retrieve_evidence":
        _fail(f"Demo 1 expected retrieve_evidence, got {route}")
    hits = [s for s in d1["demand_signals"] if s["sku_id"] == "SKU-1042" and s["severity"] == "HIGH"]
    if not hits:
        _fail("Demo 1: no HIGH for SKU-1042")
    print(f"    route={route} SKU-1042 HIGH ok")

    print("[3] Demo 3 MEDIUM at ST-003 ...")
    d3 = detect({"week_start": "2026-02-09"})
    st003 = [s for s in d3["demand_signals"] if s["sku_id"] == "SKU-0089" and s["store_id"] == "ST-003"]
    if st003 and st003[0]["severity"] not in ("MEDIUM", "HIGH"):
        _fail(f"Demo 3 ST-003 severity={st003[0]['severity']}, expected MEDIUM")
    print(f"    ST-003 severity={st003[0]['severity'] if st003 else 'n/a'}")

    print("[4] graph invoke Demo 1 (auto-approve HITL) ...")
    app = build_graph(checkpointer=MemorySaver())
    run_id = f"smoke-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": run_id}}
    state = app.invoke(
        {"run_id": run_id, "week_start": "2026-01-12", "sku_id": "SKU-1042"},
        config=config,
    )
    snap = app.get_state(config)
    if snap and snap.tasks:
        state = app.invoke(
            Command(resume={"decision": "approve", "reason": "smoke", "approver": "smoke"}),
            config=config,
        )
    if state.get("week_start") != "2026-01-12":
        _fail("week_start not preserved in graph output")
    print(f"    approval_status={state.get('approval_status')}")

    print("\n=== ALL SMOKE CHECKS PASSED ===")


if __name__ == "__main__":
    main()
