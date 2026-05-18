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

from dashboard.components.hitl_controls import render_hitl_controls


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
        render_hitl_controls(recommendations[0], run_id, key_prefix="rec")
