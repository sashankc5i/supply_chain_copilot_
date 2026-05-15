"""Diagnose node -- LLM-driven root-cause hypothesis generation.

Reads:
    state["demand_signals"]  -- detect output; only HIGH-severity signals trigger reasoning
    state["evidence"]        -- structured evidence dict from retrieve_evidence
                                (populated by task 4; empty until then -> diagnose
                                falls back to data_anomaly per the prompt rules)

Writes:
    state["root_cause_hypotheses"]  -- ranked list of cause hypotheses
                                       Each: {cause_type, confidence, explanation, evidence_sources}

Calls Azure OpenAI gpt-4o-mini via src.graph.llm.get_llm(temperature=0). We use
the Chat Completions JSON-object response format and validate the response with
Pydantic. This avoids the LangChain `with_structured_output` Pydantic-serialization
warning while keeping the type contract intact.

Graceful degradation: if the LLM call or JSON validation fails, the node emits
a single low-confidence `data_anomaly` hypothesis with the error preserved in
`explanation` -- the graph keeps running and the dashboard surfaces the issue.
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

CauseType = Literal[
    "promo_effect", "weather_event", "supplier_delay", "competitor", "data_anomaly"
]

PROMPT_PATH = _Path(__file__).resolve().parents[1] / "prompts" / "diagnose_prompt.txt"


class _Hypothesis(BaseModel):
    cause_type: CauseType
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str
    evidence_sources: list[str] = Field(default_factory=list)


class _DiagnoseOutput(BaseModel):
    hypotheses: list[_Hypothesis]


def diagnose(state: SupplyChainState) -> dict:
    """Generate ranked root-cause hypotheses for the strongest HIGH-severity signal."""
    signals = state.get("demand_signals") or []
    high_signals = [s for s in signals if s.get("severity") == "HIGH"]
    if not high_signals:
        return {"root_cause_hypotheses": []}

    focal = max(high_signals, key=lambda s: abs(s.get("zscore", 0.0)))
    evidence = state.get("evidence") or {}

    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
    payload = {
        "demand_signal": focal,
        "other_high_signal_count": len(high_signals) - 1,
        "evidence": _summarize_evidence(evidence),
    }
    human_message = (
        "Analyze the following anomaly and return JSON hypotheses per the schema:\n\n"
        + json.dumps(payload, indent=2, default=str)
    )

    try:
        llm = get_llm(temperature=0).bind(response_format={"type": "json_object"})
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_message),
        ])
        raw = response.content if isinstance(response.content, str) else json.dumps(response.content)
        result = _DiagnoseOutput.model_validate_json(raw)
        hypotheses = [h.model_dump() for h in result.hypotheses]
    except (ValidationError, Exception) as exc:
        hypotheses = [{
            "cause_type": "data_anomaly",
            "confidence": 0.2,
            "explanation": f"diagnose LLM call failed: {type(exc).__name__}: {exc}",
            "evidence_sources": [],
        }]

    return {"root_cause_hypotheses": hypotheses}


def _summarize_evidence(evidence: dict) -> dict:
    """Strip evidence down to LLM-context-friendly fields. Empty dict if absent."""
    if not evidence:
        return {}
    out: dict[str, dict] = {}
    for key, block in evidence.items():
        if not isinstance(block, dict):
            out[key] = {"data": str(block)}
            continue
        out[key] = {
            "source": block.get("source", key),
            "data": block.get("data"),
            "confidence": block.get("confidence"),
            "estimated_impact_pct": block.get("estimated_impact_pct"),
        }
    return out


# ---------------------------------------------------------------------------
# Smoke test: detect + manual tool calls (preview of retrieve_evidence in task 4)
# + diagnose, end-to-end against real Azure OpenAI.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import time

    from src.graph.nodes.detect import detect as detect_node
    from src.tools.demand_lookup import demand_lookup
    from src.tools.promo_calendar import promo_calendar
    from src.tools.supplier_delays import supplier_delays
    from src.tools.weather_events import weather_events

    def _call(fn, **kwargs):
        return fn.invoke(kwargs) if hasattr(fn, "invoke") else fn(**kwargs)

    def _avg(xs):
        return sum(xs) / len(xs) if xs else 0.0

    def run_scenario(label: str, week_start: str, target_sku: str | None = None) -> None:
        print(f"\n{'=' * 72}")
        print(f"SCENARIO  {label}")
        print(f"{'=' * 72}")

        state: dict = {"run_id": f"diagnose-{label}", "week_start": week_start}
        state.update(detect_node(state))

        high = [s for s in state["demand_signals"] if s["severity"] == "HIGH"]
        if target_sku:
            high = [s for s in high if s["sku_id"] == target_sku] or high
        if not high:
            print("  no HIGH signals -- skipping")
            return

        focal = max(high, key=lambda s: abs(s["zscore"]))
        print(f"focal:    {focal['sku_id']} @ {focal['store_id']} ({focal['region']})  "
              f"z={focal['zscore']:+.2f}  type={focal['anomaly_type']}  sev={focal['severity']}")

        # Mimic what retrieve_evidence will do: 4 tools in parallel, structured dict.
        promo = _call(promo_calendar,
                      sku_id=focal["sku_id"], region=focal["region"],
                      week_start=focal["week_start"])
        weather = _call(weather_events,
                        region=focal["region"], week_start=focal["week_start"])
        supplier = _call(supplier_delays, sku_id=focal["sku_id"])
        demand = _call(demand_lookup,
                       sku_id=focal["sku_id"], store_id=focal["store_id"],
                       weeks=8, anchor_week=focal["week_start"])

        evidence = {
            "promo": {
                "source": "promotion_calendar.csv",
                "data": promo,
                "confidence": 0.95 if promo else 0.50,
                "estimated_impact_pct": sum(p["demand_lift_pct"] for p in promo),
            },
            "weather": {
                "source": "weather_events.csv",
                "data": weather,
                "confidence": _avg([e["confidence"] for e in weather]) if weather else 0.50,
                "estimated_impact_pct": sum(e["demand_impact_pct"] for e in weather),
            },
            "supplier": {
                "source": "supplier_data.csv",
                "data": supplier,
                "confidence": 0.95,
                "estimated_impact_pct": -5.0 * sum(
                    s["delay_days"] for s in supplier if s["delay_flag"]
                ),
            },
            "demand": {
                "source": "demand_history.csv",
                "data": demand,
                "confidence": 1.00,
                "estimated_impact_pct": demand.get("latest_wow_delta_pct", 0.0),
            },
        }
        state["evidence"] = evidence

        print("evidence:")
        for k, v in evidence.items():
            n = len(v["data"]) if isinstance(v["data"], list) else "dict"
            print(f"  {k:8} records={n!s:>4}  confidence={v['confidence']:.2f}  "
                  f"impact={v['estimated_impact_pct']:+.1f}%")

        t0 = time.perf_counter()
        out = diagnose(state)
        elapsed = time.perf_counter() - t0

        hypos = out["root_cause_hypotheses"]
        print(f"\ndiagnose latency: {elapsed:.2f}s   hypotheses: {len(hypos)}")
        for i, h in enumerate(hypos, 1):
            print(f"\n  [{i}] cause={h['cause_type']:18}  confidence={h['confidence']:.2f}")
            print(f"      sources: {h['evidence_sources']}")
            print(f"      explanation: {h['explanation']}")

    run_scenario("Demo-1 SKU-1042 / West / Wk87 (promo + heatwave spike)",
                 "2026-01-12", target_sku="SKU-1042")
    run_scenario("Demo-2 SKU-0217 / South / Wk89 (supplier delay)",
                 "2026-01-26", target_sku="SKU-0217")
