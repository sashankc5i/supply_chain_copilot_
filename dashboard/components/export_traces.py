"""Download helpers for action_log and node_latency CSVs."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
ACTION_LOG = ROOT / "data" / "runtime" / "action_log.csv"
NODE_LATENCY = ROOT / "data" / "runtime" / "node_latency.csv"


def render_export_buttons(run_id: str | None = None) -> None:
    """Offer CSV downloads for audit log and optional per-run trace."""
    c1, c2 = st.columns(2)
    with c1:
        if ACTION_LOG.exists() and ACTION_LOG.stat().st_size > 1:
            df = pd.read_csv(ACTION_LOG)
            st.download_button(
                "Download action_log.csv",
                data=df.to_csv(index=False),
                file_name="action_log.csv",
                mime="text/csv",
                use_container_width=True,
            )
        else:
            st.caption("action_log empty")
    with c2:
        if NODE_LATENCY.exists() and run_id:
            df = pd.read_csv(NODE_LATENCY, dtype=str)
            if "run_id" in df.columns:
                sub = df[df["run_id"] == run_id]
                if not sub.empty:
                    st.download_button(
                        f"Download trace ({len(sub)} rows)",
                        data=sub.to_csv(index=False),
                        file_name=f"node_latency_{run_id}.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )
                    return
        if NODE_LATENCY.exists():
            df = pd.read_csv(NODE_LATENCY)
            st.download_button(
                "Download full node_latency.csv",
                data=df.to_csv(index=False),
                file_name="node_latency.csv",
                mime="text/csv",
                use_container_width=True,
            )
        else:
            st.caption("No trace file yet")
