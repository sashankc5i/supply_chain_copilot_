"""Eval rubric -- LLM-as-judge scorer for recommendation quality.

`score_recommendation` invokes Azure OpenAI gpt-4o-mini with a structured
rubric prompt and parses a 1-5 integer score.

Score guide:
  5 -- correct action type, reasonable params, plausible explanation
  4 -- correct action type, minor param issues
  3 -- partially correct (right family, wrong specifics)
  2 -- plausible but wrong action type
  1 -- irrelevant or harmful recommendation
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import json
import re

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage

load_dotenv()

from src.graph.llm import get_llm

_SYSTEM = """\
You are a supply-chain operations evaluator. Score the quality of an AI
recommendation given the ground-truth root cause. Reply ONLY with a JSON
object: {"score": <int 1-5>, "reason": "<one sentence>"}.

Scoring rubric:
  5 = Correct action type AND reasonable parameters AND plausible explanation
  4 = Correct action type, minor parameter issues
  3 = Partially correct (right supply-chain family, wrong specifics)
  2 = Plausible but wrong action type for the cause
  1 = Irrelevant, harmful, or no recommendation produced
"""


def score_recommendation(
    recommendations: list[dict],
    hypotheses: list[dict],
    ground_truth_cause: str,
) -> int:
    """Return a 1-5 LLM judge score for the top recommendation.

    Falls back to a heuristic score if the LLM call fails.
    """
    if not recommendations:
        return 1

    payload = {
        "top_recommendation": recommendations[0],
        "all_recommendations": recommendations[:3],
        "top_hypothesis": hypotheses[0] if hypotheses else None,
        "ground_truth_cause": ground_truth_cause,
    }

    try:
        llm = get_llm(temperature=0).bind(response_format={"type": "json_object"})
        resp = llm.invoke([
            SystemMessage(content=_SYSTEM),
            HumanMessage(content=json.dumps(payload, indent=2, default=str)),
        ])
        raw = resp.content if isinstance(resp.content, str) else str(resp.content)
        data = json.loads(raw)
        score = int(data.get("score", 3))
        return max(1, min(5, score))
    except Exception:
        # Heuristic fallback: match action_type to ground_truth
        top_action = recommendations[0].get("action_type", "")
        cause_to_actions = {
            "supplier_delay": {"expedite_order", "transfer_inventory"},
            "promo_effect": {"reduce_promo", "transfer_inventory"},
            "weather_event": {"transfer_inventory", "expedite_order"},
            "competitor": {"reduce_promo", "wait_and_watch"},
            "data_anomaly": {"wait_and_watch"},
            "noise": {"wait_and_watch"},
            "unknown": {"transfer_inventory", "expedite_order"},
        }
        expected = cause_to_actions.get(ground_truth_cause, set())
        return 4 if top_action in expected else 2
