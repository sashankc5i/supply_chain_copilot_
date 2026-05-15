"""HITL approval page -- pending and resolved action log tabs."""
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

st.set_page_config(page_title="HITL Approval", layout="wide")
st.title("HITL Approval Queue")

log_path = DATA_RUN / "action_log.csv"

_HOW_TO = """
**This page fills after you complete a human approval — not from running detect alone.**

1. Open **Command Center** (main app page).
2. Run **Demo 1** or **Demo 2** (HIGH severity) and wait for the pipeline to finish or pause at HITL.
3. Start the API: `uvicorn src.api.main:app --reload --port 8000`
4. On Command Center, click **Approve**, **Reject**, or **Edit** on the recommendation.

Each approve/reject appends a row to `data/runtime/action_log.csv` and shows here under **Resolved**.
"""

if not log_path.exists():
    st.info("No action log file yet.")
    st.markdown(_HOW_TO)
    st.stop()

if action_log_needs_header(log_path):
    st.info("No actions logged yet.")
    st.markdown(_HOW_TO)
    st.stop()

df = pd.read_csv(log_path)
if df.empty:
    st.info("No approvals recorded yet — the log file has only a header row.")
    st.markdown(_HOW_TO)
    st.stop()

pending = st.session_state.get("pending_hitl")
tab_pending, tab_resolved = st.tabs(["Pending (session)", "Resolved (action log)"])

with tab_pending:
    if pending:
        st.json(pending)
        st.caption(f"run_id: `{pending.get('run_id')}` — use Approve/Reject on Command Center (API required).")
    else:
        st.info(
            "No pending HITL in this browser session. "
            "Run a HIGH-severity scenario on **Command Center**; if the graph pauses for HITL, "
            "approve there first."
        )

with tab_resolved:
    st.caption(f"{len(df)} decision(s) logged")
    st.dataframe(
        df.sort_values("timestamp", ascending=False),
        use_container_width=True,
        hide_index=True,
    )
