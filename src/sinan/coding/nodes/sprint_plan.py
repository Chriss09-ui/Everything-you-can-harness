"""sprint_plan — Generator proposes sprint goals with priority and dependencies.

Agent: Generator
Loop:  Sprint

Reads:
    state["feature_list"]      — current feature registry
    state["bug_report"]        — previous sprint bug report (if any)
    state["sprint_number"]     — current sprint number
    state["sprint_contract"]   — existing contract (skip if already agreed)

Writes:
    state["sprint_contract"]   — draft contract with sprint_goals
    state["current_phase"]     — "SPRINT_PLAN"

Artifacts:
    sprint_contract.json  — versioned draft

Routes:
    → sprint_negotiate  (linear)
"""
from __future__ import annotations
import json
from ..state import CodingState
from ..prompts import get_coding_prompt
from sinan.validation import parse_and_validate_artifact
from sinan.llm import get_llm_client
from sinan.artifacts import (
    write_json, update_run_state, append_progress_log,
    append_decision_log, finalize_phase,
)


def sprint_plan_node(state: CodingState) -> dict:
    sprint = state.get("sprint_number", 1)
    update_run_state(state["run_id"], "SPRINT_PLAN")
    append_progress_log(state["run_id"], "SPRINT_PLAN", f"Sprint {sprint}: Generator proposing goals")

    client = get_llm_client()
    system = get_coding_prompt("coding_generator")

    feature_list = state.get("feature_list") or {}
    features = feature_list.get("features", [])
    unfinished = [f for f in features if not f.get("passes")]
    prev_bugs = state.get("bug_report")

    user_parts = [
        f"Sprint {sprint}: 请提出本轮 Sprint 目标。",
        f"\n未完成功能：\n{json.dumps(unfinished, indent=2, ensure_ascii=False)}",
    ]
    if prev_bugs:
        user_parts.append(f"\n上一轮 bug 报告：\n{json.dumps(prev_bugs, indent=2, ensure_ascii=False)}")
    user_parts.append("\n输出 JSON：{\"sprint_goals\": [{\"feature_id\": ..., \"acceptance_criteria\": [...]}], \"priority_order\": [...], \"estimated_sessions\": N}")
    user = "\n".join(user_parts)

    raw = client.generate(system, user)
    contract_draft = parse_and_validate_artifact(raw, "sprint_contract")

    existing = state.get("sprint_contract") or {}
    if existing.get("agreed"):
        # Re-use agreed contract instead of overwriting with a new draft
        state["sprint_contract"] = existing
        state["current_phase"] = "SPRINT_PLAN"
        finalize_phase(state["run_id"])
        return state

    contract_draft["sprint_number"] = sprint
    contract_draft["agreed"] = False

    write_json(state["run_id"], "sprint_contract.json", contract_draft, versioned=True)
    state["sprint_contract"] = contract_draft
    state["current_phase"] = "SPRINT_PLAN"

    append_decision_log(state["run_id"], {
        "phase": "SPRINT_PLAN",
        "type": "sprint_proposed",
        "content": f"Sprint {sprint} proposal: {len(contract_draft.get('sprint_goals', []))} features",
    })
    finalize_phase(state["run_id"])

    return state
