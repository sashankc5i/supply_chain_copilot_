"""POST /approval/{run_id} -- resume LangGraph after HITL decision."""
from __future__ import annotations

from typing import Any, Literal, Optional

from fastapi import APIRouter, HTTPException
from langgraph.types import Command
from pydantic import BaseModel, Field

from src.graph.graph import app as graph_app

router = APIRouter()


class ApprovalRequest(BaseModel):
    decision: Literal["approve", "reject", "edit"]
    params: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""
    approver: str = "operator@command-center"


class ApprovalResponse(BaseModel):
    run_id: str
    status: Literal["resumed", "completed", "error"]
    next_node: Optional[str] = None
    message: str = ""


def _thread_config(run_id: str) -> dict:
    return {"configurable": {"thread_id": run_id}}


@router.post("/approval/{run_id}", response_model=ApprovalResponse)
def post_approval(run_id: str, body: ApprovalRequest) -> ApprovalResponse:
    config = _thread_config(run_id)
    snapshot = graph_app.get_state(config)

    if not snapshot or not snapshot.tasks:
        raise HTTPException(
            status_code=404,
            detail=f"No interrupted run found for run_id={run_id}. Start the graph first.",
        )

    if body.decision in ("reject", "edit") and not body.reason:
        raise HTTPException(status_code=400, detail="reason is required for reject/edit")

    resume_payload = {
        "decision": body.decision,
        "params": body.params,
        "reason": body.reason,
        "approver": body.approver,
    }

    try:
        result = graph_app.invoke(Command(resume=resume_payload), config)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    values = result if isinstance(result, dict) else getattr(result, "values", result)
    critique = (values or {}).get("critique_result") or {}
    top = critique.get("top_action") or {}
    signals = (values or {}).get("demand_signals") or []
    high = [s for s in signals if s.get("severity") == "HIGH"]
    focal = max(high, key=lambda s: abs(s.get("zscore", 0.0))) if high else {}
    sku_id = focal.get("sku_id", "")

    approval_status = (values or {}).get("approval_status", "")
    if body.decision == "approve" and approval_status == "approved":
        return ApprovalResponse(
            run_id=run_id,
            status="completed",
            next_node="END",
            message="Action approved and logged.",
        )

    if body.decision == "reject":
        return ApprovalResponse(
            run_id=run_id,
            status="completed",
            next_node="END",
            message="Action rejected and logged.",
        )

    if body.decision == "edit":
        return ApprovalResponse(
            run_id=run_id,
            status="resumed",
            next_node="critique",
            message="Params updated; graph re-routed to critique.",
        )

    return ApprovalResponse(
        run_id=run_id,
        status="resumed",
        next_node=None,
        message=f"Graph resumed; approval_status={approval_status}.",
    )
