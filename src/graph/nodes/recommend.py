"""Recommend node -- LLM-generated ranked supply-chain actions.

Reads root_cause_hypotheses, evidence, demand_signals, inventory_positions.
Writes recommendations (2-3 ranked actions with cost, confidence, DOH delta).
"""
from __future__ import annotations

if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import json
from pathlib import Path as _Path
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, ValidationError

from src.graph.llm import get_llm
from src.graph.state import SupplyChainState

ActionType = Literal[
    "transfer_inventory", "expedite_order", "reduce_promo", "wait_and_watch"
]

PROMPT_PATH = _Path(__file__).resolve().parents[1] / "prompts" / "recommend_prompt.txt"


class _Recommendation(BaseModel):
    action_type: ActionType
    params: dict = Field(default_factory=dict)
    cost_usd: float = Field(ge=0)
    confidence: float = Field(ge=0.0, le=1.0)
    doh_improvement_days: float = Field(ge=0)


class _RecommendOutput(BaseModel):
    recommendations: list[_Recommendation]


def recommend(state: SupplyChainState) -> dict:
    """Generate ranked recommendations for the focal HIGH-severity signal."""
    updates: dict = {}
    if (state.get("critique_result") or {}).get("verdict") == "rejected":
        updates["retry_count"] = state.get("retry_count", 0) + 1

    signals = state.get("demand_signals") or []
    high = [s for s in signals if s.get("severity") == "HIGH"]
    if not high:
        return {**updates, "recommendations": []}

    focal = max(high, key=lambda s: abs(s.get("zscore", 0.0)))
    hypotheses = state.get("root_cause_hypotheses") or []
    evidence = state.get("evidence") or {}
    inventory = state.get("inventory_positions") or {}
    critique = state.get("critique_result") or {}

    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
    payload = {
        "demand_signal": focal,
        "top_hypothesis": hypotheses[0] if hypotheses else None,
        "all_hypotheses": hypotheses[:3],
        "evidence_summary": _summarize_evidence(evidence),
        "inventory_at_sku": inventory.get(focal["sku_id"], {}),
        "prior_critique": {
            "verdict": critique.get("verdict"),
            "violated_constraint": critique.get("violated_constraint"),
            "reason": critique.get("reason"),
        } if critique.get("verdict") == "rejected" else None,
        "retry_count": state.get("retry_count", 0),
    }
    human_message = (
        "Generate ranked recommendations for this anomaly:\n\n"
        + json.dumps(payload, indent=2, default=str)
    )

    try:
        llm = get_llm(temperature=0).bind(response_format={"type": "json_object"})
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_message),
        ])
        raw = response.content if isinstance(response.content, str) else json.dumps(response.content)
        result = _RecommendOutput.model_validate_json(raw)
        recs = [r.model_dump() for r in result.recommendations]
    except (ValidationError, Exception) as exc:
        recs = [_fallback_recommendation(focal, hypotheses, str(exc))]

    return {**updates, "recommendations": recs}


def _fallback_recommendation(focal: dict, hypotheses: list, err: str) -> dict:
    """Deterministic fallback when the LLM call fails."""
    cause = hypotheses[0]["cause_type"] if hypotheses else "data_anomaly"
    if cause in ("promo_effect", "weather_event"):
        action_type = "transfer_inventory"
        params = {
            "qty_units": 300,
            "source_locations": ["DC-001"],
            "destination_location_id": focal["store_id"],
            "timeline_days": 3,
        }
    elif cause == "supplier_delay":
        action_type = "expedite_order"
        params = {"qty_units": 500, "supplier_id": "SUP-PRIMARY", "timeline_days": 5}
    else:
        action_type = "wait_and_watch"
        params = {"review_days": 7}
    return {
        "action_type": action_type,
        "params": params,
        "cost_usd": 1200.0,
        "confidence": 0.5,
        "doh_improvement_days": 3.0,
    }


def _summarize_evidence(evidence: dict) -> dict:
    out: dict = {}
    for key, block in evidence.items():
        if not isinstance(block, dict):
            continue
        data = block.get("data")
        if key == "supplier" and isinstance(data, list):
            out[key] = data[:3]
        elif key == "demand" and isinstance(data, dict):
            out[key] = {
                k: data.get(k)
                for k in ("latest_wow_delta_pct", "zscore", "trailing_mean", "moq_units")
                if k in data or key == "supplier"
            }
        else:
            out[key] = data[:2] if isinstance(data, list) else data
    return out
