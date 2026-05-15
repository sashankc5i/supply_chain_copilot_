"""Shared TypedDict state schema for the supply-chain copilot graph.

Per design doc §7.1. Every node receives this state, mutates a subset, and
returns the diff -- LangGraph merges it back into the canonical state. Nested
dict shapes are pinned here so all owners (P3 nodes, P4 tools, P5 dashboard)
speak the same vocabulary.

`total=False` because the graph builds state up incrementally -- detect
populates demand_signals first, retrieve_evidence adds evidence, etc.
"""
from __future__ import annotations

if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from typing import Literal, Optional, TypedDict

Severity       = Literal["HIGH", "MEDIUM", "LOW"]
AnomalyType    = Literal["spike", "drop", "flat_line", "normal"]
CauseType      = Literal["promo_effect", "weather_event", "supplier_delay",
                         "competitor", "data_anomaly"]
ActionType     = Literal["transfer_inventory", "expedite_order",
                         "reduce_promo", "wait_and_watch"]
ApprovalStatus = Literal["pending", "approved", "rejected", "edited", "n/a"]
Verdict        = Literal["approved", "rejected", "flagged"]


class DemandSignal(TypedDict):
    sku_id: str
    store_id: str
    week_start: str            # ISO date "YYYY-MM-DD"
    units_sold: int
    wow_delta_pct: float
    zscore: float
    region: str
    severity: Severity
    anomaly_type: AnomalyType


class EvidenceBlock(TypedDict):
    source: str                # filename or system that produced it
    data: object               # list[dict] or dict; depends on source
    estimated_impact_pct: float
    confidence: float          # 0.0 - 1.0


class RootCauseHypothesis(TypedDict):
    cause_type: CauseType
    confidence: float
    explanation: str
    evidence_sources: list[str]


class Recommendation(TypedDict):
    action_type: ActionType
    params: dict               # action-type-specific: {qty, source_dc, ...}
    cost_usd: float
    confidence: float
    doh_improvement_days: float


class CritiqueResult(TypedDict):
    verdict: Verdict
    top_action: Optional[Recommendation]
    violated_constraint: str   # "" when verdict == "approved"
    reason: str


class SupplyChainState(TypedDict, total=False):
    # Run controls (must be in schema or LangGraph drops them before detect runs)
    week_start:            str                    # ISO Monday "YYYY-MM-DD"
    sku_id:                str                    # optional focal SKU filter
    store_id:              str                    # optional focal store filter
    run_id:                str
    demand_signals:        list[DemandSignal]
    inventory_positions:   dict                   # sku_id -> {location_id: row}
    service_levels:        dict                   # sku_id -> fill_rate float
    evidence:              dict[str, EvidenceBlock]   # 'promo'/'weather'/...
    root_cause_hypotheses: list[RootCauseHypothesis]
    recommendations:       list[Recommendation]
    critique_result:       CritiqueResult
    approval_status:       ApprovalStatus
    exceptions:            list[str]
    retry_count:           int
