"""Reusable Streamlit component -- one row for a demand_signal."""
from __future__ import annotations

import streamlit as st

SEVERITY_BADGE = {
    "HIGH":   ("🔴", "#ff5d6c"),
    "MEDIUM": ("🟡", "#ffb648"),
    "LOW":    ("🟢", "#5bd1a3"),
}


def render_alert_card(signal: dict, *, highlight: bool = False) -> None:
    """Render one demand_signal as a compact card."""
    icon, _color = SEVERITY_BADGE.get(signal["severity"], ("⚪", "#888"))
    with st.container(border=True):
        if highlight:
            st.caption("⭐ Demo focal SKU")
        cols = st.columns([0.5, 2.2, 1.0, 1.0, 1.0])
        cols[0].markdown(f"### {icon}")
        cols[1].markdown(f"**{signal['sku_id']}**")
        cols[1].caption(
            f"{signal['store_id']} · {signal['region']} · {signal['anomaly_type']}"
        )
        cols[2].metric(label="z", value=f"{signal['zscore']:+.2f}", label_visibility="visible")
        cols[3].metric(label="units", value=signal["units_sold"])
        cols[4].markdown(f"**{signal['severity']}**")
        cols[4].caption(signal["week_start"])
