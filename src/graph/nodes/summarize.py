"""Summarize node -- short LLM summary for LOW/MEDIUM severity and data glitches."""
from __future__ import annotations

if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from langchain_core.messages import HumanMessage, SystemMessage

from src.graph.llm import get_llm
from src.graph.state import SupplyChainState
from src.graph.tracing import log_node


@log_node("summarize")
def summarize(state: SupplyChainState) -> dict:
    """Produce a brief operator-facing summary; no recommendations or HITL."""
    signals = state.get("demand_signals") or []
    critique = state.get("critique_result") or {}
    exceptions = list(state.get("exceptions", []))

    if critique.get("verdict") == "rejected" and state.get("retry_count", 0) >= 1:
        msg = (
            f"Recommendations rejected after retry: "
            f"{critique.get('violated_constraint')} — {critique.get('reason')}"
        )
        exceptions.append(msg)
        return {"exceptions": exceptions, "approval_status": "n/a"}

    if not signals:
        exceptions.append("No anomalies detected for the selected week.")
        return {"exceptions": exceptions, "approval_status": "n/a"}

    focal = _focal_signal(signals, state)
    flat_line = any(s.get("anomaly_type") == "flat_line" for s in signals)

    try:
        llm = get_llm(temperature=0)
        prompt = (
            "Summarize this supply-chain alert in 2 sentences for an operator. "
            "No action required unless severity is HIGH.\n"
            f"Signal: {focal}\n"
            f"Data glitch (flat_line): {flat_line}\n"
            f"Critique: {critique or 'n/a'}"
        )
        text = llm.invoke([
            SystemMessage(content="You are a concise supply-chain analyst."),
            HumanMessage(content=prompt),
        ]).content
        summary = text if isinstance(text, str) else str(text)
    except Exception as exc:
        summary = (
            f"{focal['sku_id']} @ {focal['store_id']}: {focal['severity']} severity "
            f"{focal['anomaly_type']} (z={focal['zscore']:+.2f}). "
            f"Monitor; no HITL required."
        )
        if flat_line:
            summary += " Possible data-quality issue (zero units)."

    exceptions.append(summary.strip())
    return {"exceptions": exceptions, "approval_status": "n/a"}


def _focal_signal(signals: list[dict], state: SupplyChainState) -> dict:
    """Prefer caller-provided sku_id, else highest |z-score|."""
    target_sku = state.get("sku_id")
    if target_sku:
        sku_hits = [s for s in signals if s.get("sku_id") == target_sku]
        if sku_hits:
            return max(sku_hits, key=lambda s: abs(s.get("zscore", 0.0)))
    return max(signals, key=lambda s: abs(s.get("zscore", 0.0)))
