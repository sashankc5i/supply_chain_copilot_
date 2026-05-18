"""Evaluation harness for the supply-chain copilot.

Runs every test case in eval/test_cases.json through the LangGraph pipeline,
computes alert precision/recall and recommendation quality, and writes
eval/eval_results.json.

Usage:
    python eval/run_evals.py

Targets (per BUILD_GUIDE.md Phase 4):
    Alert precision  >= 0.85
    Alert recall     >= 0.90
    Avg rec score    >= 3.5 / 5
    Avg latency      < 45s / run
"""
from __future__ import annotations

import sys
import time
import json
import uuid
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv()

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from src.graph.graph import build_graph
from eval.rubric import score_recommendation

_EVAL_DIR = Path(__file__).resolve().parent
_TEST_CASES_PATH = _EVAL_DIR / "test_cases.json"
_RESULTS_PATH = _EVAL_DIR / "eval_results.json"

# Severity labels considered "anomaly-positive"
POSITIVE_SEVERITIES = {"HIGH", "MEDIUM"}


def _load_test_cases() -> list[dict]:
    with open(_TEST_CASES_PATH, encoding="utf-8") as f:
        return json.load(f)


def _invoke_graph(test_case: dict) -> tuple[dict, float]:
    """Invoke the graph for one test case; auto-approve any HITL interrupt.

    Returns (final_state, elapsed_seconds).
    """
    run_id = f"eval-{uuid.uuid4().hex[:10]}"
    checkpointer = MemorySaver()
    app = build_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": run_id}}

    inputs = {
        "run_id": run_id,
        "week_start": test_case["week_start"],
        "sku_id": test_case["sku_id"],
        "store_id": test_case["store_id"],
    }

    t0 = time.perf_counter()

    # First invoke — may pause at escalate interrupt
    state = app.invoke(inputs, config=config)

    # If graph paused at escalate, auto-approve and resume
    snap = app.get_state(config)
    if snap and snap.tasks:
        state = app.invoke(
            Command(resume={
                "decision": "approve",
                "reason": "eval-auto-approve",
                "approver": "eval-harness",
            }),
            config=config,
        )

    elapsed = time.perf_counter() - t0
    if not isinstance(state, dict):
        state = dict(state)
    return state, elapsed


def _detected_severity(state: dict, sku_id: str, store_id: str) -> str | None:
    """Return the severity the graph assigned to the focal (sku, store) pair."""
    for sig in state.get("demand_signals") or []:
        if sig.get("sku_id") == sku_id and sig.get("store_id") == store_id:
            return sig.get("severity")
    # Possibly detected a different store — return the max severity found
    severities = [s.get("severity") for s in (state.get("demand_signals") or [])]
    sev_rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    if severities:
        return min(severities, key=lambda s: sev_rank.get(s, 99))
    return None


def run_evals() -> dict:
    test_cases = _load_test_cases()
    results = []

    tp = fp = fn = tn = 0
    rec_scores: list[int] = []
    latencies: list[float] = []

    for tc in test_cases:
        tc_id = tc["id"]
        gt_severity = tc["ground_truth_severity"]
        gt_cause = tc["ground_truth_cause"]
        gt_positive = gt_severity in POSITIVE_SEVERITIES

        print(f"[{tc_id}] Running {tc['sku_id']} @ {tc['store_id']} {tc['week_start']} ...", flush=True)

        try:
            state, elapsed = _invoke_graph(tc)
        except Exception as exc:
            print(f"  ERROR: {exc}", flush=True)
            traceback.print_exc()
            results.append({
                "id": tc_id,
                "error": str(exc),
                "latency_s": None,
            })
            # Count as FN if ground truth is positive, FP handled below
            if gt_positive:
                fn += 1
            else:
                tn += 1
            continue

        detected_sev = _detected_severity(state, tc["sku_id"], tc["store_id"])
        pred_positive = detected_sev in POSITIVE_SEVERITIES if detected_sev else False

        # Confusion matrix update
        if gt_positive and pred_positive:
            tp += 1
        elif not gt_positive and pred_positive:
            fp += 1
        elif gt_positive and not pred_positive:
            fn += 1
        else:
            tn += 1

        # Recommendation score (only for predicted-positive cases)
        rec_score = None
        if pred_positive:
            recs = state.get("recommendations") or []
            hyps = state.get("root_cause_hypotheses") or []
            rec_score = score_recommendation(recs, hyps, gt_cause)
            rec_scores.append(rec_score)

        latencies.append(elapsed)

        result_row = {
            "id": tc_id,
            "sku_id": tc["sku_id"],
            "store_id": tc["store_id"],
            "week_start": tc["week_start"],
            "ground_truth_severity": gt_severity,
            "detected_severity": detected_sev,
            "ground_truth_cause": gt_cause,
            "predicted_cause": (
                (state.get("root_cause_hypotheses") or [{}])[0].get("cause_type")
            ),
            "recommendation_score": rec_score,
            "latency_s": round(elapsed, 2),
            "approval_status": state.get("approval_status"),
            "exceptions": state.get("exceptions") or [],
        }
        results.append(result_row)

        score_str = f"rec_score={rec_score}" if rec_score is not None else "no recs"
        print(
            f"  detected={detected_sev} gt={gt_severity} "
            f"{score_str} latency={elapsed:.1f}s",
            flush=True,
        )

    # Aggregate metrics
    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    avg_rec_score = sum(rec_scores) / len(rec_scores) if rec_scores else 0.0
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

    summary = {
        "total_cases": len(test_cases),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "avg_recommendation_score": round(avg_rec_score, 3),
        "avg_latency_s": round(avg_latency, 2),
        "targets": {
            "precision_pass": precision >= 0.85,
            "recall_pass": recall >= 0.90,
            "rec_score_pass": avg_rec_score >= 3.5,
            "latency_pass": avg_latency < 45.0,
        },
        "per_case": results,
    }

    _RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)

    print("\n=== EVAL RESULTS ===")
    print(f"  Precision : {precision:.3f}  (target >=0.85 -> {'PASS' if precision >= 0.85 else 'FAIL'})")
    print(f"  Recall    : {recall:.3f}  (target >=0.90 -> {'PASS' if recall >= 0.90 else 'FAIL'})")
    print(f"  Rec score : {avg_rec_score:.2f}/5  (target >=3.5 -> {'PASS' if avg_rec_score >= 3.5 else 'FAIL'})")
    print(f"  Latency   : {avg_latency:.1f}s avg  (target <45s -> {'PASS' if avg_latency < 45.0 else 'FAIL'})")
    print(f"\n  Results written to: {_RESULTS_PATH}")

    return summary


if __name__ == "__main__":
    run_evals()
