"""What-if simulation page -- interactive DOH / stockout projection panel.

Provides sliders for qty_adjust and promo_shift_days, calls the FastAPI
/whatif endpoint, and renders a side-by-side baseline-vs-projected bar chart.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

# Page config — must be first Streamlit call when run as a standalone page
st.set_page_config(
    page_title="What-If Simulator",
    page_icon="🔬",
    layout="wide",
)

import requests

_API_BASE = "http://localhost:8000"

st.title("🔬 What-If Simulator")
st.caption(
    "Adjust order quantity or promo timing to see the projected impact on "
    "Days-on-Hand and Stockout Probability."
)

# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------
with st.form("whatif_form"):
    c1, c2 = st.columns(2)
    with c1:
        sku_id = st.text_input("SKU ID", value="SKU-1042")
        store_id = st.text_input("Store ID", value="ST-004")
    with c2:
        qty_adjust = st.slider(
            "Qty Adjust (units)",
            min_value=-1000,
            max_value=2000,
            value=0,
            step=50,
            help="Additional units added to (or subtracted from) the planned order.",
        )
        promo_shift_days = st.slider(
            "Promo Shift (days)",
            min_value=-14,
            max_value=14,
            value=0,
            step=1,
            help="Shift the active promotion by N days. Positive = later start.",
        )
    submitted = st.form_submit_button("▶ Run Simulation", type="primary", use_container_width=True)

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if submitted:
    payload = {
        "sku_id": sku_id.strip(),
        "store_id": store_id.strip(),
        "qty_adjust": qty_adjust,
        "promo_shift_days": promo_shift_days,
    }

    with st.spinner("Running simulation..."):
        try:
            resp = requests.post(f"{_API_BASE}/whatif", json=payload, timeout=10)
            resp.raise_for_status()
            result = resp.json()
        except requests.exceptions.ConnectionError:
            st.error(
                "Cannot connect to FastAPI (http://localhost:8000). "
                "Start it with: `uvicorn src.api.main:app --reload --port 8000`"
            )
            st.stop()
        except requests.exceptions.HTTPError as exc:
            st.error(f"API error {exc.response.status_code}: {exc.response.text}")
            st.stop()
        except Exception as exc:
            st.error(f"Unexpected error: {exc}")
            st.stop()

    # -----------------------------------------------------------------------
    # Results
    # -----------------------------------------------------------------------
    st.divider()
    st.subheader("Simulation Results")

    baseline_doh = float(result.get("baseline_doh", 0))
    projected_doh = float(result.get("projected_doh", 0))
    baseline_sp = float(result.get("baseline_stockout_prob", 0))
    projected_sp = float(result.get("projected_stockout_prob", 0))
    delta_units = int(result.get("delta_units", qty_adjust))
    notes = result.get("notes", "")

    # KPI metrics
    m1, m2, m3, m4 = st.columns(4)
    doh_delta = projected_doh - baseline_doh
    sp_delta = projected_sp - baseline_sp
    m1.metric("Baseline DOH", f"{baseline_doh:.1f} d")
    m2.metric("Projected DOH", f"{projected_doh:.1f} d", delta=f"{doh_delta:+.1f} d")
    m3.metric("Baseline Stockout P", f"{baseline_sp:.1%}")
    m4.metric("Projected Stockout P", f"{projected_sp:.1%}", delta=f"{sp_delta:+.1%}")

    if notes:
        st.caption(f"ℹ️ {notes}")

    # Side-by-side bar chart
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
                x=alt.X("Scenario:N", axis=alt.Axis(labelAngle=0)),
                y=alt.Y("Value:Q", title="Value"),
                color=alt.Color(
                    "Scenario:N",
                    scale=alt.Scale(
                        domain=["Baseline", "Projected"],
                        range=["#4e79a7", "#f28e2b"],
                    ),
                ),
                column=alt.Column("Metric:N", title=None),
                tooltip=["Scenario", "Metric", alt.Tooltip("Value:Q", format=".2f")],
            )
            .properties(width=200)
        )
        st.altair_chart(chart, use_container_width=False)
        st.caption("Stockout Prob displayed ×10 for visual scale alongside DOH.")

    except ImportError:
        # Altair not available — fallback to native st.bar_chart
        import pandas as pd

        bar_df = pd.DataFrame(
            {"Baseline": [baseline_doh, baseline_sp * 100],
             "Projected": [projected_doh, projected_sp * 100]},
            index=["Days-on-Hand", "Stockout Prob (%)"],
        )
        st.bar_chart(bar_df)

    # Raw payload expander
    with st.expander("Raw API response"):
        st.json(result)
