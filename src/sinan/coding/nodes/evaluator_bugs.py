"""evaluator_bugs — output detailed bug report for Generator to fix.

Agent: Evaluator
Loop:  Fix

Reads:
    state["evaluator_grade"]  — QA result with bugs[]
    state["sprint_number"]    — current sprint

Writes:
    state["bug_report"]     — {bugs, total_bugs, critical_count, ...}
    state["fix_loop_count"] — incremented
    state["current_phase"]  — "EVALUATOR_BUGS"

Artifacts:
    bug_report.json  — versioned bug report

Routes:
    → generator_fix  (always)
"""
from __future__ import annotations
import json
from ..state import CodingState
from sinan.artifacts import (
    write_json, update_run_state, append_progress_log,
    append_decision_log, finalize_phase,
)
from sinan.validation import validate_artifact


def evaluator_bugs_node(state: CodingState) -> dict:
    sprint = state.get("sprint_number", 1)
    update_run_state(state["run_id"], "EVALUATOR_BUGS")
    append_progress_log(state["run_id"], "EVALUATOR_BUGS",
        f"Sprint {sprint}: Generating bug report")

    grade = state.get("evaluator_grade") or {}
    bugs = grade.get("bugs", [])

    bug_report = {
        "sprint_number": sprint,
        "bugs": bugs,
        "total_bugs": len(bugs),
        "critical_count": len([b for b in bugs if b.get("severity") == "critical"]),
        "major_count": len([b for b in bugs if b.get("severity") == "major"]),
        "minor_count": len([b for b in bugs if b.get("severity") == "minor"]),
    }

    validate_artifact(bug_report, "bug_report")
    write_json(state["run_id"], "bug_report.json", bug_report, versioned=True)
    state["bug_report"] = bug_report
    # fix_loop_count is incremented by generator_fix_node per fix attempt.
    state["current_phase"] = "EVALUATOR_BUGS"

    append_progress_log(state["run_id"], "EVALUATOR_BUGS",
        f"Bug report: {len(bugs)} bugs ({bug_report['critical_count']} critical)")
    append_decision_log(state["run_id"], {
        "phase": "EVALUATOR_BUGS",
        "type": "bug_report",
        "content": f"Sprint {sprint} failed QA with {len(bugs)} bugs",
        "risks": [f"{b.get('severity')}: {b.get('description', '')}" for b in bugs],
    })
    finalize_phase(state["run_id"])

    return state
