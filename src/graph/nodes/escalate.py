"""Escalate node -- HITL interrupt for human approval of the top action."""
from __future__ import annotations

if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from langgraph.types import interrupt

from src.api.action_log import append_action_log
from src.graph.state import SupplyChainState


def escalate(state: SupplyChainState) -> dict:
    """Pause for human approval; resume with approve/reject/edit decision."""
    critique = state.get("critique_result") or {}
    top = critique.get("top_action") or {}
    signals = state.get("demand_signals") or []
    high = [s for s in signals if s.get("severity") == "HIGH"]
    focal = max(high, key=lambda s: abs(s.get("zscore", 0.0))) if high else {}

    payload = {
        "run_id": state.get("run_id", ""),
        "sku_id": focal.get("sku_id", ""),
        "store_id": focal.get("store_id", ""),
        "top_action": top,
        "cost_usd": top.get("cost_usd", 0),
        "message": "Human approval required for recommended action.",
    }

    decision_payload = interrupt(payload)
    if not isinstance(decision_payload, dict):
        decision_payload = {"decision": str(decision_payload)}

    decision = decision_payload.get("decision", "reject")
    reason = decision_payload.get("reason", "")
    approver = decision_payload.get("approver", "operator@command-center")
    params_override = decision_payload.get("params") or {}

    if decision == "approve":
        _log_decision(state, focal, top, "approved", approver, reason)
        return {"approval_status": "approved"}

    if decision == "reject":
        _log_decision(state, focal, top, "rejected", approver, reason)
        return {"approval_status": "rejected"}

    if decision == "edit":
        recs = list(state.get("recommendations") or [])
        if recs:
            merged = {**recs[0].get("params", {}), **params_override}
            recs[0] = {**recs[0], "params": merged}
        return {
            "approval_status": "edited",
            "recommendations": recs,
        }

    return {"approval_status": "rejected"}


def _log_decision(
    state: SupplyChainState,
    focal: dict,
    recommendation: dict,
    approval_status: str,
    approver: str,
    rejection_reason: str,
) -> None:
    append_action_log(
        run_id=state.get("run_id", ""),
        sku_id=focal.get("sku_id", ""),
        action_type=recommendation.get("action_type", "unknown"),
        recommendation=recommendation,
        approval_status=approval_status,
        approver=approver,
        rejection_reason=rejection_reason or "",
    )
