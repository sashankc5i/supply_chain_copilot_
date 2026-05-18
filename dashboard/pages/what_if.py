"""What-if simulation page -- interactive DOH / stockout projection panel."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

st.set_page_config(
    page_title="What-If Simulator",
    page_icon="🔬",
    layout="wide",
)

import requests

from src.tools.what_if_sim import what_if_sim

_API_BASE = "http://localhost:8000"


def _run_whatif(payload: dict) -> tuple[dict, str]:
    """Try FastAPI first; fall back to in-process tool."""
    try:
        resp = requests.get(f"{_API_BASE}/health", timeout=2)
        if resp.ok:
            r = requests.post(f"{_API_BASE}/whatif", json=payload, timeout=10)
            r.raise_for_status()
            return r.json(), "FastAPI"
    except Exception:
        pass
    fn = what_if_sim
    if hasattr(fn, "invoke"):
        return fn.invoke(payload), "local tool"
    return fn(**payload), "local tool"


st.title("🔬 What-If Simulator")
st.caption(
    "Adjust order quantity or promo timing to see projected DOH and stockout probability."
)

with st.form("whatif_form"):
    c1, c2 = st.columns(2)
    with c1:
        sku_id = st.text_input("SKU ID", value="SKU-1042")
        store_id = st.text_input("Store ID", value="ST-004")
    with c2:
        qty_adjust = st.slider("Qty Adjust (units)", -1000, 2000, 0, 50)
        promo_shift_days = st.slider("Promo Shift (days)", -14, 14, 0, 1)
    submitted = st.form_submit_button("▶ Run Simulation", type="primary", use_container_width=True)

if submitted:
    payload = {
        "sku_id": sku_id.strip(),
        "store_id": store_id.strip(),
        "qty_adjust": qty_adjust,
        "promo_shift_days": promo_shift_days,
    }
    with st.spinner("Running simulation..."):
        try:
            result, source = _run_whatif(payload)
        except Exception as exc:
            st.error(f"Simulation failed: {exc}")
            st.stop()

    st.info(f"Source: **{source}**" + (
        " — start `uvicorn src.api.main:app --port 8000` to use the API."
        if source == "local tool"
        else ""
    ))

    st.divider()
    st.subheader("Simulation Results")

    baseline_doh = float(result.get("baseline_doh", 0))
    projected_doh = float(result.get("projected_doh", 0))
    baseline_sp = float(result.get("baseline_stockout_prob", 0))
    projected_sp = float(result.get("projected_stockout_prob", 0))

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Baseline DOH", f"{baseline_doh:.1f} d")
    m2.metric("Projected DOH", f"{projected_doh:.1f} d", delta=f"{projected_doh - baseline_doh:+.1f} d")
    m3.metric("Baseline Stockout P", f"{baseline_sp:.1%}")
    m4.metric("Projected Stockout P", f"{projected_sp:.1%}", delta=f"{projected_sp - baseline_sp:+.1%}")

    notes = result.get("notes", "")
    if notes:
        st.caption(f"ℹ️ {notes}")

    try:
        import altair as alt
        import pandas as pd

        chart_df = pd.DataFrame({
            "Scenario": ["Baseline", "Projected", "Baseline", "Projected"],
            "Metric": ["Days-on-Hand", "Days-on-Hand", "Stockout Prob ×10", "Stockout Prob ×10"],
            "Value": [baseline_doh, projected_doh, baseline_sp * 10, projected_sp * 10],
        })
        chart = (
            alt.Chart(chart_df)
            .mark_bar()
            .encode(
                x="Scenario:N",
                y="Value:Q",
                color=alt.Color("Scenario:N", scale=alt.Scale(
                    domain=["Baseline", "Projected"],
                    range=["#4e79a7", "#f28e2b"],
                )),
                column=alt.Column("Metric:N", title=None),
            )
            .properties(width=200)
        )
        st.altair_chart(chart, use_container_width=False)
    except ImportError:
        import pandas as pd
        bar_df = pd.DataFrame(
            {"Baseline": [baseline_doh, baseline_sp * 100],
             "Projected": [projected_doh, projected_sp * 100]},
            index=["Days-on-Hand", "Stockout Prob (%)"],
        )
        st.bar_chart(bar_df)

    with st.expander("Raw response"):
        st.json(result)
