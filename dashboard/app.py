"""Supply Chain Command Center -- Streamlit entry.

Run from project root:
    streamlit run dashboard/app.py

Phase 2 scope:
    - Sidebar scenario picker (3 demo scenarios + custom week)
    - Pipeline run: detect -> retrieve_evidence -> diagnose
    - Alert list (filterable by severity)
    - Focal-alert detail panel with evidence cards + ranked hypotheses

Phase 3 will add HITL approval + what-if pages under dashboard/pages/.
"""
from __future__ import annotations

import sys
import time
from datetime import date
from pathlib import Path

# Put project root on sys.path so `src.*` and `dashboard.*` imports resolve
# regardless of how Streamlit is invoked.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="Supply Chain Command Center",
    page_icon="📦",
    layout="wide",
)

# Imports after st.set_page_config + sys.path setup.
from dashboard.components.alert_card import render_alert_card
from dashboard.components.evidence_panel import render_evidence_panel
from src.graph.nodes.detect import detect
from src.graph.nodes.diagnose import diagnose
from src.graph.nodes.retrieve_evidence import retrieve_evidence


# ---------------------------------------------------------------------------
# Sidebar -- scenario selection + pipeline controls
# ---------------------------------------------------------------------------
st.sidebar.title("Pipeline Run")

SCENARIOS = {
    "Demo 1 — SKU-1042 spike (West, Wk87)":      "2026-01-12",
    "Demo 2 — SKU-0217 drop  (South, Wk89)":     "2026-01-26",
    "Demo 3 — SKU-0089 borderline (East, Wk91)": "2026-02-09",
    "Latest week (anchor, Wk104)":               "2026-05-11",
    "Custom":                                    None,
}

choice = st.sidebar.radio("Scenario", list(SCENARIOS.keys()))
preset_week = SCENARIOS[choice]
if preset_week:
    week_start = preset_week
    st.sidebar.caption(f"Week start: {week_start}")
else:
    chosen_date = st.sidebar.date_input("Week start (Monday)", value=date(2026, 1, 12))
    week_start = chosen_date.isoformat()

run_diagnose = st.sidebar.checkbox(
    "Run LLM diagnosis (slower, costs tokens)", value=True,
    help="Toggle off to run only detect (pure pandas) for a fast view of the alert list.",
)

run = st.sidebar.button("▶ Run pipeline", type="primary", use_container_width=True)

st.sidebar.divider()
st.sidebar.caption(
    "**Pipeline:** detect → retrieve_evidence → diagnose. "
    "Recommend, critique, escalate ship in Phase 3."
)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "state" not in st.session_state:
    st.session_state.state = None
    st.session_state.week_start = None
    st.session_state.timings = {}

if run:
    timings: dict[str, float] = {}
    state: dict = {"run_id": f"st-{week_start}-{int(time.time())}", "week_start": week_start}

    with st.spinner("Detecting anomalies..."):
        t0 = time.perf_counter()
        state.update(detect(state))
        timings["detect_ms"] = (time.perf_counter() - t0) * 1000

    high = [s for s in state.get("demand_signals", []) if s["severity"] == "HIGH"]
    if run_diagnose and high:
        with st.spinner("Retrieving evidence (4 tools in parallel)..."):
            t0 = time.perf_counter()
            state.update(retrieve_evidence(state))
            timings["retrieve_evidence_ms"] = (time.perf_counter() - t0) * 1000

        with st.spinner("Diagnosing root cause (gpt-4o-mini)..."):
            t0 = time.perf_counter()
            state.update(diagnose(state))
            timings["diagnose_ms"] = (time.perf_counter() - t0) * 1000

    st.session_state.state = state
    st.session_state.week_start = week_start
    st.session_state.timings = timings


# ---------------------------------------------------------------------------
# Main -- header, KPIs, alert list, focal detail
# ---------------------------------------------------------------------------
st.title("📦 Supply Chain Command Center")
st.caption("LangGraph Copilot · Phase 2 build · gpt-4o-mini")

if st.session_state.state is None:
    st.info("👈 Pick a scenario in the sidebar and click ▶ Run pipeline.")
    st.stop()

state = st.session_state.state
signals = state.get("demand_signals", [])
evidence = state.get("evidence", {})
hypotheses = state.get("root_cause_hypotheses", [])
timings = st.session_state.timings

# KPI row
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total Alerts", len(signals))
k2.metric("HIGH",    sum(1 for s in signals if s["severity"] == "HIGH"))
k3.metric("MEDIUM",  sum(1 for s in signals if s["severity"] == "MEDIUM"))
k4.metric("LOW",     sum(1 for s in signals if s["severity"] == "LOW"))
total_ms = sum(timings.values())
k5.metric("Pipeline latency", f"{total_ms:.0f} ms" if total_ms else "—")

st.caption(
    " · ".join(f"{k}: {v:.0f}ms" for k, v in timings.items()) or
    "(timings populate after a run)"
)

st.divider()

# Two-column body: alert list (left) + focal diagnosis (right)
left, right = st.columns([2, 3])

with left:
    st.subheader("Alerts")
    sev_filter = st.multiselect(
        "Severity",
        options=["HIGH", "MEDIUM", "LOW"],
        default=["HIGH", "MEDIUM"],
    )
    filtered = [s for s in signals if s["severity"] in sev_filter]
    if not filtered:
        st.info("No alerts match the filter.")
    else:
        sev_rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        filtered.sort(key=lambda s: (sev_rank[s["severity"]], -abs(s["zscore"])))
        for s in filtered[:25]:
            render_alert_card(s)
        if len(filtered) > 25:
            st.caption(f"…and {len(filtered) - 25} more (sorted by severity, |z|)")

with right:
    st.subheader("Focal Alert · Diagnosis")
    high = [s for s in signals if s["severity"] == "HIGH"]
    if not high:
        st.info("No HIGH-severity alerts in this run. retrieve_evidence + diagnose only fire for HIGH signals.")
    else:
        focal = max(high, key=lambda s: abs(s["zscore"]))
        focal_cols = st.columns([2, 1, 1, 1])
        focal_cols[0].markdown(f"### {focal['sku_id']}")
        focal_cols[0].caption(f"{focal['store_id']} · {focal['region']} · {focal['week_start']}")
        focal_cols[1].metric("z-score", f"{focal['zscore']:+.2f}")
        focal_cols[2].metric("units", focal["units_sold"])
        focal_cols[3].metric("type", focal["anomaly_type"])

        if evidence:
            st.markdown("**Evidence**")
            render_evidence_panel(evidence)

        if hypotheses:
            st.markdown("**Root-cause hypotheses (ranked)**")
            for i, h in enumerate(hypotheses, 1):
                with st.container(border=True):
                    title_cols = st.columns([3, 1])
                    title_cols[0].markdown(f"**[{i}] `{h['cause_type']}`**")
                    title_cols[1].metric("confidence", f"{h['confidence']:.2f}")
                    st.caption(f"sources: {', '.join(h['evidence_sources']) or '(none cited)'}")
                    st.write(h["explanation"])
        elif evidence:
            st.warning("Diagnose returned no hypotheses.")
        else:
            st.info("Re-run with **Run LLM diagnosis** enabled to see evidence + hypotheses.")

# Coming-in-Phase-3 placeholders
st.divider()
st.subheader("Coming in Phase 3")
ph_cols = st.columns(3)
with ph_cols[0]:
    with st.container(border=True):
        st.markdown("**Recommend**")
        st.caption("Ranked actions with cost, confidence, DOH improvement.")
with ph_cols[1]:
    with st.container(border=True):
        st.markdown("**Critique**")
        st.caption("Deterministic constraint check (safety stock, MOQ, budget).")
with ph_cols[2]:
    with st.container(border=True):
        st.markdown("**HITL**")
        st.caption("Approve / reject / edit with action_log persistence.")

with st.expander("Pipeline metadata"):
    st.json({
        "run_id": state.get("run_id"),
        "week_start": st.session_state.week_start,
        "n_signals": len(signals),
        "n_evidence_sources": len(evidence),
        "n_hypotheses": len(hypotheses),
        "timings_ms": timings,
    })
