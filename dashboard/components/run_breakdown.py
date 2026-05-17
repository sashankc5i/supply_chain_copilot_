"""Streamlit component -- per-run node breakdown panel.

Reads rows from `data/runtime/node_latency.csv` for a given run_id and
renders them as an ordered timeline with timing bars, so evaluators can
see exactly which nodes ran and how long each took (substitute for LangSmith
trace UI).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

_LOG_PATH = ROOT / "data" / "runtime" / "node_latency.csv"

_NODE_ORDER = [
    "detect",
    "retrieve_evidence",
    "diagnose",
    "recommend",
    "critique",
    "escalate",
    "summarize",
]

_NODE_COLOR = {
    "detect":           "#4e79a7",
    "retrieve_evidence":"#f28e2b",
    "diagnose":         "#e15759",
    "recommend":        "#76b7b2",
    "critique":         "#59a14f",
    "escalate":         "#edc948",
    "summarize":        "#b07aa1",
}


def render_run_breakdown(run_id: str) -> None:
    """Render a per-node timing breakdown for the given run_id."""
    if not _LOG_PATH.exists():
        st.info("No trace data yet — run the pipeline first.")
        return

    try:
        df = pd.read_csv(_LOG_PATH, dtype=str)
    except Exception as exc:
        st.warning(f"Could not read trace log: {exc}")
        return

    if df.empty or "run_id" not in df.columns:
        st.info("No trace rows found.")
        return

    rows = df[df["run_id"] == run_id].copy()
    if rows.empty:
        st.caption(f"No trace rows for run_id `{run_id}`.")
        return

    rows["latency_ms"] = pd.to_numeric(rows["latency_ms"], errors="coerce").fillna(0.0)
    total_ms = rows["latency_ms"].sum()

    st.caption(f"run_id `{run_id}` · {len(rows)} node(s) · total {total_ms:.0f} ms")

    # Sort by _NODE_ORDER where possible, then by CSV order
    order_map = {n: i for i, n in enumerate(_NODE_ORDER)}
    rows["_sort"] = rows["node_name"].map(lambda n: order_map.get(n, 99))
    rows = rows.sort_values("_sort").reset_index(drop=True)

    for _, row in rows.iterrows():
        node = row.get("node_name", "?")
        lat = float(row.get("latency_ms", 0))
        out_keys = str(row.get("output_keys", ""))
        color = _NODE_COLOR.get(node, "#aaaaaa")
        pct = min(lat / max(total_ms, 1) * 100, 100)

        with st.container():
            col_label, col_bar, col_ms = st.columns([2, 5, 1])
            with col_label:
                st.markdown(
                    f"<span style='color:{color};font-weight:600'>{node}</span>",
                    unsafe_allow_html=True,
                )
            with col_bar:
                bar_html = (
                    f"<div style='background:#e8e8e8;border-radius:4px;height:14px;margin-top:6px'>"
                    f"<div style='background:{color};width:{pct:.1f}%;height:14px;border-radius:4px'></div>"
                    f"</div>"
                )
                st.markdown(bar_html, unsafe_allow_html=True)
            with col_ms:
                st.caption(f"{lat:.0f} ms")

        if out_keys.strip():
            st.caption(f"  outputs: {out_keys.replace('|', ', ')}")
