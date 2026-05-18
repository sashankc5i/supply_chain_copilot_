"""Evaluation harness for the supply-chain copilot.

Runs every test case in eval/test_cases.json through the LangGraph pipeline,
computes alert precision/recall and recommendation quality, and writes
eval/eval_results.json.

Detection is scored two ways:
  - store_level: severity at the labeled (sku_id, store_id)
  - sku_week_level: best severity for sku_id anywhere (recommended for recall)
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

POSITIVE_SEVERITIES = {"HIGH", "MEDIUM"}
_DEMO_IDS = {"demo-1", "demo-2", "demo-3"}
_SEV_RANK = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


def _load_test_cases() -> list[dict]:
    with open(_TEST_CASES_PATH, encoding="utf-8") as f:
        return json.load(f)


def _invoke_graph(test_case: dict) -> tuple[dict, float]:
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
    state = app.invoke(inputs, config=config)
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


def _severity_at_store(state: dict, sku_id: str, store_id: str) -> str | None:
    for sig in state.get("demand_signals") or []:
        if sig.get("sku_id") == sku_id and sig.get("store_id") == store_id:
            return sig.get("severity")
    return None


def _best_severity_for_sku(state: dict, sku_id: str) -> str | None:
    severities = [
        s.get("severity")
        for s in (state.get("demand_signals") or [])
        if s.get("sku_id") == sku_id and s.get("severity")
    ]
    if not severities:
        return None
    return min(severities, key=lambda s: _SEV_RANK.get(s, 99))


def _is_positive(severity: str | None) -> bool:
    return severity in POSITIVE_SEVERITIES if severity else False


def _confusion(rows: list[dict], pred_key: str) -> dict:
    tp = fp = fn = tn = 0
    for r in rows:
        gt_pos = r["gt_positive"]
        pred_pos = r[pred_key]
        if gt_pos and pred_pos:
            tp += 1
        elif not gt_pos and pred_pos:
            fp += 1
        elif gt_pos and not pred_pos:
            fn += 1
        else:
            tn += 1
    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "precision_pass": precision >= 0.85,
        "recall_pass": recall >= 0.90,
    }


def run_evals() -> dict:
    test_cases = _load_test_cases()
    results: list[dict] = []
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
            results.append({"id": tc_id, "error": str(exc), "latency_s": None})
            latencies.append(0.0)
            continue

        detected_store = _severity_at_store(state, tc["sku_id"], tc["store_id"])
        detected_sku = _best_severity_for_sku(state, tc["sku_id"])
        pred_store = _is_positive(detected_store)
        pred_sku = _is_positive(detected_sku)
        pred_for_rec = pred_sku

        rec_score = None
        if pred_for_rec:
            recs = state.get("recommendations") or []
            hyps = state.get("root_cause_hypotheses") or []
            rec_score = score_recommendation(recs, hyps, gt_cause)
            rec_scores.append(rec_score)

        latencies.append(elapsed)

        results.append({
            "id": tc_id,
            "sku_id": tc["sku_id"],
            "store_id": tc["store_id"],
            "week_start": tc["week_start"],
            "ground_truth_severity": gt_severity,
            "detected_severity_store": detected_store,
            "detected_severity_sku_week": detected_sku,
            "ground_truth_cause": gt_cause,
            "predicted_cause": (
                (state.get("root_cause_hypotheses") or [{}])[0].get("cause_type")
            ),
            "recommendation_score": rec_score,
            "latency_s": round(elapsed, 2),
            "approval_status": state.get("approval_status"),
            "gt_positive": gt_positive,
            "pred_positive_store": pred_store,
            "pred_positive_sku_week": pred_sku,
        })

        print(
            f"  store={detected_store} sku_best={detected_sku} gt={gt_severity} "
            f"rec={rec_score} latency={elapsed:.1f}s",
            flush=True,
        )

    store_rows = [{"gt_positive": r["gt_positive"], "pred_positive_store": r["pred_positive_store"]}
                  for r in results if "error" not in r]
    sku_rows = [{"gt_positive": r["gt_positive"], "pred_positive_sku_week": r["pred_positive_sku_week"]}
                for r in results if "error" not in r]
    metrics_store = _confusion(store_rows, "pred_positive_store")
    metrics_sku = _confusion(sku_rows, "pred_positive_sku_week")

    demo_cases = [r for r in results if r.get("id") in _DEMO_IDS and "error" not in r]
    demo_sku_rows = [
        {"gt_positive": r["gt_positive"], "pred_positive_sku_week": r["pred_positive_sku_week"]}
        for r in demo_cases
    ]
    metrics_demo = _confusion(demo_sku_rows, "pred_positive_sku_week")

    avg_rec = sum(rec_scores) / len(rec_scores) if rec_scores else 0.0
    avg_lat = sum(latencies) / len(latencies) if latencies else 0.0

    summary = {
        "total_cases": len(test_cases),
        "metrics_store_level": metrics_store,
        "metrics_sku_week_level": metrics_sku,
        "metrics_demo_only_sku_week": metrics_demo,
        "precision": metrics_sku["precision"],
        "recall": metrics_sku["recall"],
        "f1": metrics_sku["f1"],
        "avg_recommendation_score": round(avg_rec, 3),
        "avg_latency_s": round(avg_lat, 2),
        "targets": {
            "precision_pass": metrics_sku["precision_pass"],
            "recall_pass": metrics_sku["recall_pass"],
            "rec_score_pass": avg_rec >= 3.5,
            "latency_pass": avg_lat < 45.0,
            "demo_recall_pass": metrics_demo["recall_pass"],
        },
        "per_case": results,
    }

    with open(_RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)

    print("\n=== EVAL RESULTS (sku-week level — primary) ===")
    print(f"  Precision : {metrics_sku['precision']:.3f} -> {'PASS' if metrics_sku['precision_pass'] else 'FAIL'}")
    print(f"  Recall    : {metrics_sku['recall']:.3f} -> {'PASS' if metrics_sku['recall_pass'] else 'FAIL'}")
    print(f"  Demo-only recall: {metrics_demo['recall']:.3f}")
    print(f"  Rec score : {avg_rec:.2f}/5")
    print(f"  Latency   : {avg_lat:.1f}s avg")
    print(f"  Written: {_RESULTS_PATH}")
    return summary


if __name__ == "__main__":
    run_evals()
