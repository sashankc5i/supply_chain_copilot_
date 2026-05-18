"""Ranked recommendation table with HITL Approve / Reject / Edit actions.

HITL resume is executed directly via the in-process LangGraph graph instance
(no HTTP round-trip).  The FastAPI /approval endpoint is kept for external /
API-testing use, but the dashboard never calls it — calling it from Streamlit
caused 404 errors because the two processes don't share an in-process
MemorySaver and SQLite connections don't guarantee immediate cross-process
visibility.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from langgraph.types import Command

from src.graph.graph import app as graph_app


def _thread_config(run_id: str) -> dict:
    return {"configurable": {"thread_id": run_id}}


def render_recommendation_table(
    recommendations: list[dict],
    critique: dict | None,
    run_id: str,
) -> None:
    """Render recommendations and optional HITL controls when critique approved."""
    if not recommendations:
        st.info("No recommendations generated.")
        return

    for i, rec in enumerate(recommendations, 1):
        with st.container(border=True):
            cols = st.columns([3, 1, 1, 1])
            cols[0].markdown(f"**[{i}] `{rec['action_type']}`**")
            cols[1].metric("cost", f"${rec['cost_usd']:,.0f}")
            cols[2].metric("confidence", f"{rec['confidence']:.2f}")
            cols[3].metric("DOH +", f"{rec['doh_improvement_days']:.1f}d")
            st.caption(f"params: `{json.dumps(rec.get('params', {}))}`")

    if critique:
        verdict = critique.get("verdict", "")
        color = {"approved": "green", "rejected": "red", "flagged": "orange"}.get(verdict, "gray")
        st.markdown(
            f":{color}[**Critique: {verdict}**] — {critique.get('reason', '')}"
        )
        if critique.get("violated_constraint"):
            st.caption(f"Constraint: `{critique['violated_constraint']}`")

    if (critique or {}).get("verdict") == "approved" and run_id:
        st.markdown("**HITL approval**")
        _render_hitl_controls(recommendations[0], run_id)


def _render_hitl_controls(top_action: dict, run_id: str) -> None:
    c1, c2, c3 = st.columns(3)

    with c1:
        if st.button("✅ Approve", type="primary", key=f"hitl-approve-{run_id}"):
            _resume_graph(run_id, {"decision": "approve", "reason": "Operator approved"})

    with c2:
        reject_reason = st.text_input("Reject reason", key=f"hitl-reject-reason-{run_id}")
        if st.button("🚫 Reject", key=f"hitl-reject-{run_id}"):
            _resume_graph(run_id, {
                "decision": "reject",
                "reason": reject_reason or "Operator rejected",
            })

    with c3:
        edit_qty = st.number_input(
            "Edit qty_units",
            min_value=0,
            value=int((top_action.get("params") or {}).get("qty_units", 0)),
            key=f"hitl-edit-qty-{run_id}",
        )
        edit_reason = st.text_input("Edit reason", key=f"hitl-edit-reason-{run_id}")
        if st.button("✏️ Edit & re-critique", key=f"hitl-edit-{run_id}"):
            _resume_graph(run_id, {
                "decision": "edit",
                "params": {"qty_units": int(edit_qty)},
                "reason": edit_reason or "Operator edited quantity",
            })


def _resume_graph(run_id: str, payload: dict) -> None:
    """Resume the interrupted LangGraph run directly (in-process, no HTTP)."""
    config = _thread_config(run_id)

    # Verify the graph is actually paused before resuming
    snap = graph_app.get_state(config)
    if not snap or not snap.tasks:
        st.error(
            f"No paused graph found for run_id `{run_id}`. "
            "Re-run the pipeline — the previous run may have already completed or the "
            "session was reset."
        )
        return

    try:
        with st.spinner("Resuming graph..."):
            result = graph_app.invoke(Command(resume=payload), config)
        values = result if isinstance(result, dict) else dict(result)
        status = values.get("approval_status", payload.get("decision", "?"))
        decision = payload["decision"]
        if decision == "approve":
            st.success(f"✅ Action **approved** — logged to action_log.csv.")
        elif decision == "reject":
            st.warning(f"🚫 Action **rejected** — logged to action_log.csv.")
        else:
            st.info(f"✏️ Action **edited** — graph re-routed to critique.")
        # Persist the updated state back into session so the page reflects it
        import streamlit as _st
        if hasattr(_st, "session_state") and "state" in _st.session_state:
            _st.session_state.state = values
            _st.session_state.interrupted = bool(
                graph_app.get_state(config).tasks
            )
        st.rerun()
    except Exception as exc:
        st.error(f"Graph resume failed: {exc}")
