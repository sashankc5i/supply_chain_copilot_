"""Supply Chain Command Center -- Streamlit entry.

Run from project root:
    streamlit run dashboard/app.py

Phase 3: full graph pipeline + recommendations + critique + HITL (via FastAPI).
"""
from __future__ import annotations

import sys
import time
import uuid
from datetime import date
from pathlib import Path

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

from dashboard.components.alert_card import render_alert_card
from dashboard.components.evidence_panel import render_evidence_panel
from dashboard.components.recommendation_table import render_recommendation_table
from dashboard.components.run_breakdown import render_run_breakdown
from src.api.routes.alerts import set_latest_alerts
from src.graph.graph import app as graph_app


def _thread_config(run_id: str) -> dict:
    return {"configurable": {"thread_id": run_id}}


def _is_interrupted(run_id: str) -> bool:
    snap = graph_app.get_state(_thread_config(run_id))
    return bool(snap and snap.tasks)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.title("Pipeline Run")

SCENARIOS = {
    "Demo 1 — SKU-1042 spike (West, Wk87)":      "2026-01-12",
    "Demo 2 — SKU-0217 drop  (South, Wk89)":     "2026-01-26",
    "Demo 3 — SKU-0089 borderline (East, Wk91)": "2026-02-09",
    "Latest week (anchor, Wk104)":               "2026-05-11",
    "Custom":                                    None,
}
DEMO_SKU = {
    "Demo 1 — SKU-1042 spike (West, Wk87)": "SKU-1042",
    "Demo 2 — SKU-0217 drop  (South, Wk89)": "SKU-0217",
    "Demo 3 — SKU-0089 borderline (East, Wk91)": "SKU-0089",
}

choice = st.sidebar.radio("Scenario", list(SCENARIOS.keys()))
preset_week = SCENARIOS[choice]
if preset_week:
    week_start = preset_week
    st.sidebar.caption(f"Week start: {week_start}")
else:
    chosen_date = st.sidebar.date_input("Week start (Monday)", value=date(2026, 1, 12))
    week_start = chosen_date.isoformat()

run = st.sidebar.button("▶ Run pipeline", type="primary", use_container_width=True)

st.sidebar.divider()
st.sidebar.caption(
    "Pipeline: detect → [evidence → diagnose → recommend → critique → escalate] "
    "or summarize. Start FastAPI for HITL buttons."
)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "state" not in st.session_state:
    st.session_state.state = None
    st.session_state.run_id = None
    st.session_state.week_start = None
    st.session_state.timings = {}
    st.session_state.interrupted = False

if run:
    run_id = f"st-{uuid.uuid4().hex[:12]}"
    timings: dict[str, float] = {}
    config = _thread_config(run_id)
    inputs: dict = {"run_id": run_id, "week_start": week_start}
    demo_sku = DEMO_SKU.get(choice)
    if demo_sku:
        inputs["sku_id"] = demo_sku

    t0 = time.perf_counter()
    try:
        with st.spinner("Running LangGraph pipeline..."):
            result = graph_app.invoke(inputs, config=config)
        timings["pipeline_ms"] = (time.perf_counter() - t0) * 1000
        interrupted = _is_interrupted(run_id)
        state = result if isinstance(result, dict) else dict(result)
        set_latest_alerts(run_id, state.get("demand_signals", []))
        st.session_state.state = state
        st.session_state.run_id = run_id
        st.session_state.week_start = week_start
        st.session_state.timings = timings
        st.session_state.interrupted = interrupted
        if interrupted:
            st.session_state.pending_hitl = {
                "run_id": run_id,
                "critique": state.get("critique_result"),
                "top_action": (state.get("critique_result") or {}).get("top_action"),
            }
    except Exception as exc:
        st.error(f"Pipeline failed: {exc}")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
st.title("📦 Supply Chain Command Center")
st.caption("LangGraph Copilot · Phase 4 · gpt-4o-mini")

if (
    st.session_state.state is not None
    and st.session_state.week_start
    and st.session_state.week_start != week_start
):
    st.warning(
        f"Sidebar week is **{week_start}** but results are from "
        f"**{st.session_state.week_start}**. Click **Run pipeline** to refresh."
    )

if st.session_state.state is None:
    st.info("👈 Pick a scenario in the sidebar and click ▶ Run pipeline.")
    st.stop()

state = st.session_state.state
run_id = st.session_state.run_id or ""
signals = state.get("demand_signals", [])
evidence = state.get("evidence", {})
hypotheses = state.get("root_cause_hypotheses", [])
recommendations = state.get("recommendations", [])
critique = state.get("critique_result")
timings = st.session_state.timings
interrupted = st.session_state.interrupted

if interrupted:
    st.warning(
        f"⏸ **HITL pending** — graph paused at escalate. "
        f"Use Approve / Reject / Edit below (requires FastAPI on port 8000). "
        f"run_id=`{run_id}`"
    )

# KPIs
k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Alerts", len(signals))
k2.metric("HIGH", sum(1 for s in signals if s["severity"] == "HIGH"))
k3.metric("MEDIUM", sum(1 for s in signals if s["severity"] == "MEDIUM"))
k4.metric("LOW", sum(1 for s in signals if s["severity"] == "LOW"))
k5.metric("Recs", len(recommendations))
total_ms = timings.get("pipeline_ms", sum(timings.values()))
k6.metric("Latency", f"{total_ms:.0f} ms" if total_ms else "—")

ran_week = state.get("week_start") or st.session_state.week_start
if ran_week:
    st.caption(f"Pipeline week: **{ran_week}** · run_id `{run_id}`")

if state.get("exceptions"):
    for msg in state["exceptions"]:
        st.info(msg)

st.divider()

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

with right:
    st.subheader("Focal Alert · Diagnosis & Actions")
    high = [s for s in signals if s["severity"] == "HIGH"]
    if not high and not state.get("exceptions"):
        st.info("No HIGH-severity alerts — summarize path only.")
    else:
        if high:
            focal = max(high, key=lambda s: abs(s["zscore"]))
            st.markdown(f"**{focal['sku_id']}** · {focal['store_id']} · {focal['region']}")

        if evidence:
            st.markdown("**Evidence**")
            render_evidence_panel(evidence)

        if hypotheses:
            st.markdown("**Root-cause hypotheses**")
            for i, h in enumerate(hypotheses, 1):
                with st.container(border=True):
                    st.markdown(f"**[{i}] `{h['cause_type']}`** — conf {h['confidence']:.2f}")
                    st.write(h["explanation"])

        if recommendations or critique:
            st.markdown("**Recommendations**")
            render_recommendation_table(
                recommendations, critique, run_id if interrupted else "",
            )

        if state.get("approval_status") and state["approval_status"] != "n/a":
            status = state["approval_status"]
            if status == "approved":
                st.success(f"✅ Action **{status}** — logged to action_log.csv.")
            elif status == "rejected":
                st.warning(f"🚫 Action **{status}** — logged to action_log.csv.")
            elif status == "edited":
                st.info(f"✏️ Action **{status}** — re-critiqued with new params.")
            else:
                st.info(f"Approval status: **{status}**")

with st.expander("Pipeline metadata"):
    st.json({
        "run_id": run_id,
        "week_start": st.session_state.week_start,
        "interrupted": interrupted,
        "approval_status": state.get("approval_status"),
        "retry_count": state.get("retry_count", 0),
        "n_signals": len(signals),
        "timings_ms": timings,
    })

st.divider()
with st.expander("🔍 Run breakdown (node trace)", expanded=False):
    if run_id:
        render_run_breakdown(run_id)
    else:
        st.info("Run a pipeline first to see the node trace.")
