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
    total = len(features)

    grade = state.get("evaluator_grade") or {}

    sprint_result = {
        "sprint_number": sprint,
        "total_features": total,
        "completed_features": len(passing),
        "completion_pct": int(len(passing) / total * 100) if total > 0 else 0,
        "spec_complete": len(passing) == total,
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
    state["sprint_result"] = sprint_result
    state["current_phase"] = "SPRINT_COMPLETE"

    append_progress_log(state["run_id"], "SPRINT_COMPLETE",
        f"Sprint {sprint}: {len(passing)}/{total} features done, {'SPEC COMPLETE' if sprint_result['spec_complete'] else 'more sprints needed'}")
    append_decision_log(state["run_id"], {
        "phase": "SPRINT_COMPLETE",
        "type": "sprint_complete",
        "content": f"Sprint {sprint} complete: {sprint_result['completion_pct']}% features done",
        "rationale": f"Sprint passed QA. Spec {'fully complete' if sprint_result['spec_complete'] else 'remaining features for next sprint'}",
    })
    finalize_phase(state["run_id"])

    return state
