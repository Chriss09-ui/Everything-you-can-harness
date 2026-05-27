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
        git_revert(state["run_id"], last_good)
        # After revert, check whether the working tree actually got cleaned.
        # If git_revert succeeded (diff empty now), the sanity failure was
        # almost certainly a transient caused by the now-discarded changes —
        # we treat it as "recovered" and DON'T burn a retry slot. Only if
        # revert failed (something is still dirty) do we count this as a
        # real sanity_retry.
        post_revert_diff = git_diff(state["run_id"])
        recovered = not post_revert_diff
        triage_result["revert_performed"] = True
        triage_result["revert_cleaned_diff"] = recovered
        if recovered:
            append_progress_log(state["run_id"], "BUG_TRIAGE",
                f"Reverted to last good commit {last_good[:7]} and working tree clean — not burning retry slot")
        else:
            append_progress_log(state["run_id"], "BUG_TRIAGE",
                f"Reverted to {last_good[:7]} but diff remains — this is a real bug, burning retry slot")
            state["sanity_retry_count"] = state.get("sanity_retry_count", 0) + 1
    elif diff:
        triage_result["revert_decision"] = "manual_review_needed"
        # No last_good_commit available but diff exists — generator wrote bad
        # code and we can't revert. Burn a retry slot.
        state["sanity_retry_count"] = state.get("sanity_retry_count", 0) + 1
        append_progress_log(state["run_id"], "BUG_TRIAGE",
            f"Uncommitted changes + no last_good_commit — burning retry slot; manual review needed")
    else:
        triage_result["revert_decision"] = "no_changes"
        # No diff at all — sanity failed on a clean tree, treat as real bug.
        state["sanity_retry_count"] = state.get("sanity_retry_count", 0) + 1
        append_progress_log(state["run_id"], "BUG_TRIAGE",
            "Sanity failed on clean tree — burning retry slot (real bug)")

    state["triage_result"] = triage_result
    state["current_phase"] = "BUG_TRIAGE"

    append_decision_log(state["run_id"], {
        "phase": "BUG_TRIAGE",
        "type": "triage_complete",
        "content": f"Triage decision: {triage_result['revert_decision']}",
    })
    finalize_phase(state["run_id"])

    return state
