"""sanity_check — run E2E regression on all passing features.

Agent: Evaluator
Loop:  Session

Reads:
    state["run_id"]  — run identifier

Writes:
    state["sanity_pass"]    — bool pass/fail
    state["test_result"]    — TestResult dict
    state["current_phase"]  — "SANITY_CHECK"

Artifacts:
    (none)

Routes:
    → pick_feature  when sanity_pass=true
    → bug_triage    when sanity_pass=false
"""
from __future__ import annotations
from ..state import CodingState
from ..testing import run_sanity_check
from sinan.artifacts import (
    write_json, update_run_state, append_progress_log,
    append_decision_log, finalize_phase, get_run_dir,
)


def sanity_check_node(state: CodingState) -> dict:
    update_run_state(state["run_id"], "SANITY_CHECK")
    append_progress_log(state["run_id"], "SANITY_CHECK", "Running sanity check on passing features")

    result = run_sanity_check(state["run_id"])

    state["sanity_pass"] = result.passed
    state["test_result"] = result.to_dict()
    state["current_phase"] = "SANITY_CHECK"

    if result.passed:
        state["last_good_commit"] = state.get("last_good_commit")
        append_decision_log(state["run_id"], {
            "phase": "SANITY_CHECK",
            "type": "sanity_pass",
            "content": "All passing features regression check passed",
        })
    else:
        append_decision_log(state["run_id"], {
            "phase": "SANITY_CHECK",
            "type": "sanity_fail",
            "content": f"Sanity check failed: {result.errors}",
            "risks": result.errors,
        })

    finalize_phase(state["run_id"])
    return state
