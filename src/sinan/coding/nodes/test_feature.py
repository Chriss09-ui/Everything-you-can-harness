"""test_feature — run E2E test for the implemented feature.

Agent: Evaluator
Loop:  Feature

Reads:
    state["run_id"]           — run identifier
    state["current_feature_id"] — feature being tested

Writes:
    state["test_result"]   — TestResult dict
    state["current_phase"] — "TEST_FEATURE"

Artifacts:
    (none)

Routes:
    → commit_feature    when passed or retry≥2
    → implement_feature when failed and retry<2
"""
from __future__ import annotations

__test__ = False

from ..state import CodingState
from ..testing import run_e2e_test
from sinan.artifacts import (
    write_json, update_run_state, append_progress_log,
    append_decision_log, finalize_phase,
)


def test_feature_node(state: CodingState) -> dict:
    feature_id = state.get("current_feature_id")
    update_run_state(state["run_id"], "TEST_FEATURE")
    append_progress_log(state["run_id"], "TEST_FEATURE", f"Testing feature: {feature_id}")

    result = run_e2e_test(state["run_id"], feature_id)

    state["test_result"] = result.to_dict()
    state["current_phase"] = "TEST_FEATURE"

    if result.passed:
        append_progress_log(state["run_id"], "TEST_FEATURE",
            f"{feature_id}: PASS")
        append_decision_log(state["run_id"], {
            "phase": "TEST_FEATURE",
            "type": "feature_test_pass",
            "content": f"Feature {feature_id} test passed",
        })
    else:
        append_progress_log(state["run_id"], "TEST_FEATURE",
            f"{feature_id}: FAIL - {result.errors}")
        append_decision_log(state["run_id"], {
            "phase": "TEST_FEATURE",
            "type": "feature_test_fail",
            "content": f"Feature {feature_id} test failed: {result.errors}",
            "risks": result.errors,
        })

    finalize_phase(state["run_id"])
    return state
