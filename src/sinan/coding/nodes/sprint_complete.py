"""sprint_complete — write sprint result, check if spec is fully done.

Agent:  (orchestrator — no LLM call)
Loop:  Sprint (exit)

Reads:
    state["feature_list"]   — all features with pass/fail
    state["evaluator_grade"] — QA grades
    state["sprint_number"]  — current sprint

Writes:
    state["sprint_result"] — {completion_pct, spec_complete, qa_grades, ...}
    state["current_phase"] — "SPRINT_COMPLETE"
    (also resets: sprint_number++, session_number=1, negotiate_round=1,
     fix_loop_count=0, feature_retry_count=0, sanity_retry_count=0,
     sprint_contract=None, evaluator_grade=None, fix_result=None,
     current_feature_id=None, current_feature_status=None, test_result=None,
     implement_result=None, triage_result=None, _is_first_init=False.
     bug_report is intentionally NOT reset — sprint_plan consumes it as
     "previous sprint bugs" context to prioritize the next sprint.)

Artifacts:
    sprint_result.json  — versioned sprint summary

Routes:
    → END            when spec_complete=true (all features pass)
    → sprint_plan    when more sprints needed (sprint_number++)
"""
from __future__ import annotations
import json
from ..state import CodingState
from sinan.artifacts import (
    write_json, update_run_state, append_progress_log,
    append_decision_log, finalize_phase,
)
from sinan.validation import validate_artifact


def sprint_complete_node(state: CodingState) -> dict:
    sprint = state.get("sprint_number", 1)
    update_run_state(state["run_id"], "SPRINT_COMPLETE")
    append_progress_log(state["run_id"], "SPRINT_COMPLETE",
        f"Sprint {sprint}: Sprint complete")

    feature_list = state.get("feature_list") or {}
    features = feature_list.get("features", [])
    passing = [f for f in features if f.get("passes")]
    blocked = [f for f in features if f.get("blocked")]
    total = len(features)

    grade = state.get("evaluator_grade") or {}

    # completion_pct counts passing features only. blocked features are NOT
    # counted as done — they're an explicit "gave up after retry cap" signal.
    # spec_complete fires only when no feature is left unblocked/unpassed.
    sprint_result = {
        "sprint_number": sprint,
        "total_features": total,
        "completed_features": len(passing),
        "blocked_features": len(blocked),
        "completion_pct": int(len(passing) / total * 100) if total > 0 else 0,
        "spec_complete": len(passing) + len(blocked) == total and len(blocked) == 0,
        "qa_grades": {
            "functionality": grade.get("functionality"),
            "product_depth": grade.get("product_depth"),
            "visual_quality": grade.get("visual_quality"),
            "code_quality": grade.get("code_quality"),
        },
        "overall_pass": grade.get("overall_pass", True),
    }

    validate_artifact(sprint_result, "sprint_result")
    write_json(state["run_id"], "sprint_result.json", sprint_result, versioned=True)

    # Reset per-sprint counters here (not in the router) — LangGraph only
    # propagates values a node RETURNS, so router-side mutations are dropped.
    # sprint_contract MUST also be cleared so sprint_plan re-plans the next
    # sprint instead of reusing sprint 1's agreed contract.
    # bug_report is intentionally NOT cleared: sprint_plan needs the previous
    # sprint's bug context to inform the next sprint's priorities. evaluator_bugs
    # will overwrite it once the new sprint produces its own bugs.
    # _is_first_init MUST be flipped to False so sprint 2's session_init
    # skips the 5 init branches (otherwise they re-write feature_list.json,
    # claude-progress.txt, and re-run git init, nuking sprint 1's work).
    next_sprint = sprint + 1
    updates = {
        "sprint_result": sprint_result,
        "current_phase": "SPRINT_COMPLETE",
        "sprint_number": next_sprint,
        "session_number": 1,
        "negotiate_round": 1,
        "fix_loop_count": 0,
        "feature_retry_count": 0,
        "sanity_retry_count": 0,
        "sprint_contract": None,
        "evaluator_grade": None,
        "fix_result": None,
        "current_feature_id": None,
        "current_feature_status": None,
        "test_result": None,
        "implement_result": None,
        "triage_result": None,
        "_is_first_init": False,
    }

    append_progress_log(state["run_id"], "SPRINT_COMPLETE",
        f"Sprint {sprint}: {len(passing)}/{total} features done, {'SPEC COMPLETE' if sprint_result['spec_complete'] else 'more sprints needed'}")
    append_decision_log(state["run_id"], {
        "phase": "SPRINT_COMPLETE",
        "type": "sprint_complete",
        "content": f"Sprint {sprint} complete: {sprint_result['completion_pct']}% features done",
        "rationale": f"Sprint passed QA. Spec {'fully complete' if sprint_result['spec_complete'] else 'remaining features for next sprint'}",
    })
    finalize_phase(state["run_id"])

    state.update(updates)
    return state
