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
from src.graph.tracing import log_node

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


@log_node("diagnose")
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
# Smoke test: detect -> retrieve_evidence -> diagnose, end-to-end.
# Uses the real retrieve_evidence node (task 4), not inlined tool calls.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import time

    from src.graph.nodes.detect import detect as detect_node
    from src.graph.nodes.retrieve_evidence import retrieve_evidence

    def run_scenario(label: str, week_start: str) -> None:
        print(f"\n{'=' * 72}\nSCENARIO  {label}\n{'=' * 72}")
        state: dict = {"run_id": f"diagnose-{label}", "week_start": week_start}

        t_d = time.perf_counter()
        state.update(detect_node(state))
        t_d = (time.perf_counter() - t_d) * 1000

        high = [s for s in state["demand_signals"] if s["severity"] == "HIGH"]
        if not high:
            print(f"detect: {t_d:.0f}ms  no HIGH signals -- skipping")
            return

        focal = max(high, key=lambda s: abs(s["zscore"]))
        print(f"detect:           {t_d:>6.0f} ms   focal={focal['sku_id']} @ "
              f"{focal['store_id']} ({focal['region']})  z={focal['zscore']:+.2f}  "
              f"type={focal['anomaly_type']}")

        t_r = time.perf_counter()
        state.update(retrieve_evidence(state))
        t_r = (time.perf_counter() - t_r) * 1000
        ev = state.get("evidence", {})
        print(f"retrieve_evidence:{t_r:>6.0f} ms   sources={list(ev.keys())}")

        t_dg = time.perf_counter()
        out = diagnose(state)
        t_dg = (time.perf_counter() - t_dg) * 1000

        hypos = out["root_cause_hypotheses"]
        print(f"diagnose:         {t_dg:>6.0f} ms   hypotheses={len(hypos)}\n")
        for i, h in enumerate(hypos, 1):
            print(f"  [{i}] {h['cause_type']:18}  conf={h['confidence']:.2f}  "
                  f"sources={h['evidence_sources']}")
            print(f"      {h['explanation']}")

    run_scenario("Demo-1 SKU-1042 / West / Wk87 (promo + heatwave spike)", "2026-01-12")
    run_scenario("Demo-2 SKU-0217 / South / Wk89 (supplier delay)",        "2026-01-26")
