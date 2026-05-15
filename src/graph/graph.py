"""LangGraph topology for the supply-chain copilot.

Day 1 build: every node is a no-op passthrough returning `{}`. The point of
this file today is to lock the graph *shape* -- nodes, edges, routing
functions -- so P3/P4 can slot real logic in without touching wiring.

Verification:
    python -m src.graph.graph        # canonical
    python src/graph/graph.py        # also works via the bootstrap below

Real node bodies land in `src/graph/nodes/*.py` during Phase 2 and 3.
"""
from __future__ import annotations

# Make absolute `src.*` imports work when this file is run directly
# (python src/graph/graph.py or VSCode "Run"), not just via `python -m`.
if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from langgraph.graph import END, START, StateGraph

from src.graph.state import SupplyChainState


# ---------------------------------------------------------------------------
# Placeholder nodes -- swapped for real ones in src/graph/nodes/* (Phase 2-3).
# Each node returns a partial state dict that LangGraph merges back.
# ---------------------------------------------------------------------------
def detect(state: SupplyChainState) -> dict:
    return {"demand_signals": state.get("demand_signals", [])}


def retrieve_evidence(state: SupplyChainState) -> dict:
    return {"evidence": state.get("evidence", {})}


def diagnose(state: SupplyChainState) -> dict:
    return {"root_cause_hypotheses": state.get("root_cause_hypotheses", [])}


def recommend(state: SupplyChainState) -> dict:
    return {"recommendations": state.get("recommendations", [])}


def critique(state: SupplyChainState) -> dict:
    return {"critique_result": state.get("critique_result", {"verdict": "approved",
                                                             "top_action": None,
                                                             "violated_constraint": "",
                                                             "reason": ""})}


def escalate(state: SupplyChainState) -> dict:
    return {"approval_status": state.get("approval_status", "n/a")}


def summarize(state: SupplyChainState) -> dict:
    exc = list(state.get("exceptions", []))
    exc.append("summarize: placeholder summary")
    return {"exceptions": exc}


# ---------------------------------------------------------------------------
# Routing (per design doc §7.3). Pure functions of state.
# ---------------------------------------------------------------------------
def route_after_detect(state: SupplyChainState) -> str:
    signals = state.get("demand_signals", [])
    if any(s.get("anomaly_type") == "flat_line" for s in signals):
        return "summarize"
    if any(s.get("severity") == "HIGH" for s in signals):
        return "retrieve_evidence"
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


# ---------------------------------------------------------------------------
# Graph wiring
# ---------------------------------------------------------------------------
def build_graph():
    g = StateGraph(SupplyChainState)

    g.add_node("detect",            detect)
    g.add_node("retrieve_evidence", retrieve_evidence)
    g.add_node("diagnose",          diagnose)
    g.add_node("recommend",         recommend)
    g.add_node("critique",          critique)
    g.add_node("escalate",          escalate)
    g.add_node("summarize",         summarize)

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

    return g.compile()


app = build_graph()


if __name__ == "__main__":
    print(app.get_graph().draw_ascii())
