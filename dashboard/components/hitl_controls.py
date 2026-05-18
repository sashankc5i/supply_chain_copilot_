"""Shared HITL approve / reject / edit controls for Streamlit pages."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from langgraph.types import Command

from src.graph.graph import app as graph_app


def thread_config(run_id: str) -> dict:
    return {"configurable": {"thread_id": run_id}}


def resume_graph(run_id: str, payload: dict, *, rerun: bool = True) -> dict | None:
    """Resume interrupted graph; update session state. Returns final values or None on error."""
    config = thread_config(run_id)
    snap = graph_app.get_state(config)
    if not snap or not snap.tasks:
        st.error(
            f"No paused graph found for run_id `{run_id}`. "
            "Re-run the pipeline on Command Center first."
        )
        return None

    try:
        with st.spinner("Resuming graph..."):
            result = graph_app.invoke(Command(resume=payload), config)
        values = result if isinstance(result, dict) else dict(result)
        decision = payload.get("decision", "")
        if decision == "approve":
            st.success("Action approved — logged to action_log.csv.")
        elif decision == "reject":
            st.warning("Action rejected — logged to action_log.csv.")
        else:
            st.info("Action edited — graph re-routed to critique.")

        if "state" in st.session_state:
            st.session_state.state = values
            st.session_state.interrupted = bool(graph_app.get_state(config).tasks)
            st.session_state.pending_hitl = None if not st.session_state.interrupted else {
                "run_id": run_id,
                "critique": values.get("critique_result"),
                "top_action": (values.get("critique_result") or {}).get("top_action"),
            }
        if rerun:
            st.rerun()
        return values
    except Exception as exc:
        st.error(f"Graph resume failed: {exc}")
        return None


def render_hitl_controls(top_action: dict, run_id: str, *, key_prefix: str = "hitl") -> None:
    """Approve / reject / edit buttons for a paused escalate node."""
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Approve", type="primary", key=f"{key_prefix}-approve-{run_id}"):
            resume_graph(run_id, {"decision": "approve", "reason": "Operator approved"})
    with c2:
        reject_reason = st.text_input("Reject reason", key=f"{key_prefix}-reject-reason-{run_id}")
        if st.button("Reject", key=f"{key_prefix}-reject-{run_id}"):
            resume_graph(run_id, {
                "decision": "reject",
                "reason": reject_reason or "Operator rejected",
            })
    with c3:
        edit_qty = st.number_input(
            "Edit qty_units",
            min_value=0,
            value=int((top_action.get("params") or {}).get("qty_units", 0)),
            key=f"{key_prefix}-edit-qty-{run_id}",
        )
        edit_reason = st.text_input("Edit reason", key=f"{key_prefix}-edit-reason-{run_id}")
        if st.button("Edit and re-critique", key=f"{key_prefix}-edit-{run_id}"):
            resume_graph(run_id, {
                "decision": "edit",
                "params": {"qty_units": int(edit_qty)},
                "reason": edit_reason or "Operator edited quantity",
            })
