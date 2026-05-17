"""LangGraph topology for the supply-chain copilot.

Full pipeline (Phase 3):
    detect -> [retrieve_evidence -> diagnose -> recommend -> critique -> escalate] | summarize -> END

Verification:
    python -m src.graph.graph
"""
from __future__ import annotations

if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from src.graph.nodes.critique import critique
from src.graph.nodes.detect import detect
from src.graph.nodes.diagnose import diagnose
from src.graph.nodes.escalate import escalate
from src.graph.nodes.recommend import recommend
from src.graph.nodes.retrieve_evidence import retrieve_evidence
from src.graph.nodes.summarize import summarize
from src.graph.state import SupplyChainState

# Shared SQLite checkpointer — written to data/runtime/checkpoints.db so
# both the Streamlit process and the FastAPI process read the same state.
_DB_PATH = str(Path(__file__).resolve().parents[2] / "data" / "runtime" / "checkpoints.db")


def route_after_detect(state: SupplyChainState) -> str:
    signals = state.get("demand_signals", [])
    if any(s.get("severity") == "HIGH" for s in signals):
        return "retrieve_evidence"
    if signals and all(s.get("anomaly_type") == "flat_line" for s in signals):
        return "summarize"
    return "summarize"


def route_after_critique(state: SupplyChainState) -> str:
    verdict = (state.get("critique_result") or {}).get("verdict")
    retry = state.get("retry_count", 0)
    if verdict == "approved":
        return "escalate"
    if verdict == "rejected" and retry < 1:
        return "recommend"
    return "summarize"


def route_after_escalate(state: SupplyChainState) -> str:
    if state.get("approval_status") == "edited":
        return "critique"
    return END


def build_graph(*, checkpointer=None):
    g = StateGraph(SupplyChainState)

    g.add_node("detect", detect)
    g.add_node("retrieve_evidence", retrieve_evidence)
    g.add_node("diagnose", diagnose)
    g.add_node("recommend", recommend)
    g.add_node("critique", critique)
    g.add_node("escalate", escalate)
    g.add_node("summarize", summarize)

    g.add_edge(START, "detect")
    g.add_conditional_edges(
        "detect",
        route_after_detect,
        {"retrieve_evidence": "retrieve_evidence", "summarize": "summarize"},
    )
    g.add_edge("retrieve_evidence", "diagnose")
    g.add_edge("diagnose", "recommend")
    g.add_edge("recommend", "critique")
    g.add_conditional_edges(
        "critique",
        route_after_critique,
        {"escalate": "escalate", "recommend": "recommend", "summarize": "summarize"},
    )
    g.add_conditional_edges(
        "escalate",
        route_after_escalate,
        {"critique": "critique", END: END},
    )
    g.add_edge("summarize", END)

    if checkpointer is not None:
        return g.compile(checkpointer=checkpointer)
    return g.compile()


import sqlite3 as _sqlite3
_db_dir = Path(_DB_PATH).parent
_db_dir.mkdir(parents=True, exist_ok=True)
_conn = _sqlite3.connect(_DB_PATH, check_same_thread=False)
_checkpointer = SqliteSaver(_conn)
app = build_graph(checkpointer=_checkpointer)


if __name__ == "__main__":
    print(app.get_graph().draw_ascii())
