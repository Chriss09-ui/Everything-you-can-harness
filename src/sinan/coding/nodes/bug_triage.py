"""bug_triage — on sanity failure: check git diff, optionally revert to last good commit.

Agent: Evaluator
Loop:  Session

Reads:
    state["run_id"]          — run identifier
    state["last_good_commit"] — previous good commit ref

Writes:
    state["triage_result"]  — {diff_summary, status_summary, revert_decision, revert_performed}
    state["current_phase"]  — "BUG_TRIAGE"

Artifacts:
    (none)

Routes:
    → session_setup  (linear, re-enter session loop)
"""
from __future__ import annotations
from ..state import CodingState
from ..git import git_diff, git_revert, git_status
from sinan.artifacts import (
    update_run_state, append_progress_log,
    append_decision_log, finalize_phase,
)


def bug_triage_node(state: CodingState) -> dict:
    update_run_state(state["run_id"], "BUG_TRIAGE")
    append_progress_log(state["run_id"], "BUG_TRIAGE", "Triaging sanity check failure")

    diff = git_diff(state["run_id"])
    status = git_status(state["run_id"])
    last_good = state.get("last_good_commit")

    triage_result = {
        "diff_summary": diff,
        "status_summary": status,
        "revert_decision": "none",
        "revert_performed": False,
    }

    # Decide: if diff is large and last good commit exists, suggest revert
    if last_good and diff:
        # Simple heuristic: if there are significant uncommitted changes, revert
        triage_result["revert_decision"] = "suggest_revert"
        triage_result["revert_performed"] = True
        git_revert(state["run_id"], last_good)
        append_progress_log(state["run_id"], "BUG_TRIAGE",
            f"Reverted to last good commit: {last_good[:7]}")
    elif diff:
        triage_result["revert_decision"] = "manual_review_needed"
        append_progress_log(state["run_id"], "BUG_TRIAGE",
            f"Uncommitted changes detected, manual review needed")
    else:
        triage_result["revert_decision"] = "no_changes"
        append_progress_log(state["run_id"], "BUG_TRIAGE", "No uncommitted changes")

    state["triage_result"] = triage_result
    state["sanity_retry_count"] = state.get("sanity_retry_count", 0) + 1
    state["current_phase"] = "BUG_TRIAGE"

    append_decision_log(state["run_id"], {
        "phase": "BUG_TRIAGE",
        "type": "triage_complete",
        "content": f"Triage decision: {triage_result['revert_decision']}",
    })
    finalize_phase(state["run_id"])

    return state
