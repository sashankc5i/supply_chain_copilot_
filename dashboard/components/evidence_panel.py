"""Reusable Streamlit component -- evidence dict rendered as 4 cards."""
from __future__ import annotations

import streamlit as st

SOURCE_ICONS = {
    "promo":    "🎯",
    "weather":  "🌦️",
    "supplier": "🚚",
    "demand":   "📈",
}


def render_evidence_panel(evidence: dict) -> None:
    """Render each evidence block as one card in a row of equal-width columns."""
    if not evidence:
        st.info("No evidence retrieved.")
        return
    keys = list(evidence.keys())
    cols = st.columns(len(keys))
    for col, key in zip(cols, keys):
        block = evidence[key]
        icon = SOURCE_ICONS.get(key, "📋")
        data = block.get("data")
        n_records = len(data) if isinstance(data, list) else ("1" if data else "0")
        conf = float(block.get("confidence") or 0.0)
        impact = float(block.get("estimated_impact_pct") or 0.0)
        with col:
            with st.container(border=True):
                st.markdown(f"{icon} **{key}**")
                st.caption(block.get("source", ""))
                st.metric("records", n_records)
                st.progress(min(max(conf, 0.0), 1.0), text=f"confidence {conf:.2f}")
                st.caption(f"impact: {impact:+.1f}%")
