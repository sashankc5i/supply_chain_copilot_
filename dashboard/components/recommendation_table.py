"""Ranked recommendation table with HITL Approve / Reject / Edit actions."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

import streamlit as st

API_BASE = "http://127.0.0.1:8000"


def render_recommendation_table(
    recommendations: list[dict],
    critique: dict | None,
    run_id: str,
    *,
    api_base: str = API_BASE,
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
        _render_hitl_controls(recommendations[0], run_id, api_base=api_base)


def _render_hitl_controls(top_action: dict, run_id: str, *, api_base: str) -> None:
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Approve", type="primary", key=f"hitl-approve-{run_id}"):
            _post_approval(api_base, run_id, {"decision": "approve"})
    with c2:
        reject_reason = st.text_input("Reject reason", key=f"hitl-reject-reason-{run_id}")
        if st.button("Reject", key=f"hitl-reject-{run_id}"):
            _post_approval(api_base, run_id, {
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
        if st.button("Edit & re-critique", key=f"hitl-edit-{run_id}"):
            _post_approval(api_base, run_id, {
                "decision": "edit",
                "params": {"qty_units": int(edit_qty)},
                "reason": edit_reason or "Operator edited quantity",
            })


def _post_approval(api_base: str, run_id: str, payload: dict) -> None:
    url = f"{api_base}/approval/{run_id}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read().decode())
        st.success(body.get("message", "Approval submitted."))
        if body.get("next_node"):
            st.caption(f"Next node: {body['next_node']}")
    except urllib.error.URLError as exc:
        st.error(
            f"Could not reach API at {api_base}. "
            f"Start FastAPI: `uvicorn src.api.main:app --reload --port 8000`\n\n{exc}"
        )
