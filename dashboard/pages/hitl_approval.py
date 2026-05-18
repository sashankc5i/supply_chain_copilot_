"""HITL approval page -- pending controls + resolved action log."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from src.api.action_log import action_log_needs_header
from src.data.loaders import DATA_RUN
from dashboard.components.hitl_controls import render_hitl_controls
from dashboard.components.export_traces import render_export_buttons

st.set_page_config(page_title="HITL Approval", layout="wide")
st.title("HITL Approval Queue")

st.page_link("app.py", label="Back to Command Center", icon="📦")

log_path = DATA_RUN / "action_log.csv"
pending = st.session_state.get("pending_hitl")
tab_pending, tab_resolved = st.tabs(["Pending (session)", "Resolved (action log)"])

with tab_pending:
    if pending:
        run_id = pending.get("run_id", "")
        top = pending.get("top_action") or {}
        st.caption(f"run_id: `{run_id}`")
        if top:
            st.json(top)
            render_hitl_controls(top, run_id, key_prefix="hitl-page")
        else:
            st.info("No top action in pending payload — open Command Center and re-run a HIGH scenario.")
    else:
        st.info(
            "No pending HITL in this session. Run Demo 1 or Demo 2 on **Command Center** "
            "and wait for the HITL banner before approving here."
        )

with tab_resolved:
    if not log_path.exists() or action_log_needs_header(log_path):
        st.info("No actions logged yet. Approve or reject on Command Center first.")
    else:
        df = pd.read_csv(log_path)
        if df.empty:
            st.info("Action log has only a header — complete an approval to add rows.")
        else:
            st.caption(f"{len(df)} decision(s) logged")
            st.dataframe(
                df.sort_values("timestamp", ascending=False),
                use_container_width=True,
                hide_index=True,
            )
            render_export_buttons(st.session_state.get("run_id"))
