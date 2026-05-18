"""Tests for conditional routing functions."""
from __future__ import annotations

from src.graph.graph import route_after_critique, route_after_detect, route_after_escalate


def test_route_after_detect_high_goes_evidence():
    state = {
        "demand_signals": [
            {"severity": "HIGH", "anomaly_type": "spike"},
            {"severity": "LOW", "anomaly_type": "flat_line"},
        ],
        "run_id": "t",
    }
    assert route_after_detect(state) == "retrieve_evidence"


def test_route_after_detect_no_high_goes_summarize():
    state = {
        "demand_signals": [{"severity": "LOW", "anomaly_type": "spike"}],
        "run_id": "t",
    }
    assert route_after_detect(state) == "summarize"


def test_route_after_detect_all_flat_line_summarize():
    state = {
        "demand_signals": [
            {"severity": "MEDIUM", "anomaly_type": "flat_line"},
            {"severity": "LOW", "anomaly_type": "flat_line"},
        ],
        "run_id": "t",
    }
    assert route_after_detect(state) == "summarize"


def test_route_after_critique_approved_escalate():
    state = {
        "critique_result": {"verdict": "approved"},
        "retry_count": 0,
        "run_id": "t",
    }
    assert route_after_critique(state) == "escalate"


def test_route_after_critique_rejected_retry_recommend():
    state = {
        "critique_result": {"verdict": "rejected"},
        "retry_count": 0,
        "run_id": "t",
    }
    assert route_after_critique(state) == "recommend"


def test_route_after_critique_rejected_after_retry_summarize():
    state = {
        "critique_result": {"verdict": "rejected"},
        "retry_count": 1,
        "run_id": "t",
    }
    assert route_after_critique(state) == "summarize"


def test_route_after_escalate_edited_critique():
    state = {"approval_status": "edited", "run_id": "t"}
    assert route_after_escalate(state) == "critique"
