"""generator_review — Generator self-evaluates sprint completion against spec.

Agent: Generator
Loop:  Sprint (review)

Reads:
    state["feature_list"]     — completed features
    state["sprint_contract"] — sprint goals
    state["sprint_number"]   — current sprint

Writes:
    state["generator_self_eval"] — {completion_pct, features_completed, ...}
    state["current_phase"]       — "GENERATOR_REVIEW"

Artifacts:
    (none)

Routes:
    → evaluator_qa  (linear)
"""
from __future__ import annotations
import json
from ..state import CodingState
from ..prompts import get_coding_prompt
from sinan.llm import get_llm_client
from sinan.validation import parse_and_validate_artifact
from sinan.artifacts import (
    write_json, update_run_state, append_progress_log,
    append_decision_log, finalize_phase,
)


def generator_review_node(state: CodingState) -> dict:
    sprint = state.get("sprint_number", 1)
    update_run_state(state["run_id"], "GENERATOR_REVIEW")
    append_progress_log(state["run_id"], "GENERATOR_REVIEW",
        f"Sprint {sprint}: Generator self-review")

    client = get_llm_client()
    system = get_coding_prompt("coding_generator")

    feature_list = state.get("feature_list") or {}
    features = feature_list.get("features", [])
    passing = [f for f in features if f.get("passes")]
    contract = state.get("sprint_contract") or {}
    sprint_goals = contract.get("sprint_goals", [])

    user = (
        f"Sprint {sprint} 自评：\n\n"
        f"已完成 features: {json.dumps(passing, indent=2, ensure_ascii=False)}\n\n"
        f"计划 features: {json.dumps(sprint_goals, indent=2, ensure_ascii=False)}\n\n"
        f"输出 JSON: {{\"completion_pct\": <0-100>, \"features_completed\": [...], \"features_remaining\": [...], \"self_assessment\": \"...\"}}"
    )

    raw = client.generate(system, user)
    review = parse_and_validate_artifact(raw, "generator_self_eval")

    state["generator_self_eval"] = review
    state["current_phase"] = "GENERATOR_REVIEW"

    append_decision_log(state["run_id"], {
        "phase": "GENERATOR_REVIEW",
        "type": "self_review",
        "content": f"Sprint {sprint} self-review: {review.get('completion_pct', 0)}% complete",
        "rationale": review.get("self_assessment", ""),
    })
    finalize_phase(state["run_id"])

    return state
