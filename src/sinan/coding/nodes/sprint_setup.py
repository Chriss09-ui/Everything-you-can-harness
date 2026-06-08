"""sprint_setup — Generator announces execution plan after negotiation.

Agent: Generator (Claude Agent SDK — pure reasoning, zero tools)
Loop:  Sprint

Reads:
    state["sprint_contract"]  — agreed contract
    state["spec"]             — product spec
    state["sprint_number"]    — current sprint

Writes:
    state["sprint_contract"]  — adds execution_plan field
    state["current_phase"]    — "SPRINT_SETUP"
    state["fix_loop_count"]   — reset to 0

Artifacts:
    sprint_contract.json  — versioned (with execution_plan)

Routes:
    → session_init  (linear)
"""
from __future__ import annotations
import json
from ..state import CodingState
from ..prompts import get_coding_prompt
from sinan.validation import validate_artifact
from sinan.agent import get_agent_runner
from sinan.artifacts import (
    write_json, update_run_state, append_progress_log,
    append_decision_log, finalize_phase, get_run_dir,
)


_EXECUTION_PLAN_SCHEMA = {
    "type": "object",
    "properties": {"execution_order": {"type": "array"}},
    "required": ["execution_order"],
    "additionalProperties": True,
}


def sprint_setup_node(state: CodingState) -> dict:
    sprint = state.get("sprint_number", 1)
    update_run_state(state["run_id"], "SPRINT_SETUP")
    append_progress_log(state["run_id"], "SPRINT_SETUP",
        f"Sprint {sprint}: Generator announcing execution plan")

    runner = get_agent_runner()
    system = get_coding_prompt("coding_sprint_planner")
    contract = state.get("sprint_contract") or {}
    spec = state.get("spec") or {}

    user = (
        f"Sprint 目标已确认：\n{json.dumps(contract, indent=2, ensure_ascii=False)}\n\n"
        f"产品规格：\n{json.dumps(spec, indent=2, ensure_ascii=False)}\n\n"
        f"请宣读你的执行方案，列出你将按什么顺序实现哪些功能，以及你的实现策略。\n"
        f"输出 JSON: {{\"execution_order\": [...], \"strategy\": \"...\"}}"
    )

    agent_result = runner.run(
        system=system, prompt=user, cwd=get_run_dir(state["run_id"]),
        allowed_tools=[], schema=_EXECUTION_PLAN_SCHEMA,
    )
    plan = agent_result.parse("execution_plan")
    validate_artifact(plan, "execution_plan")

    contract["execution_plan"] = plan
    write_json(state["run_id"], "sprint_contract.json", contract, versioned=True)
    state["sprint_contract"] = contract
    state["current_phase"] = "SPRINT_SETUP"
    state["fix_loop_count"] = 0

    append_decision_log(state["run_id"], {
        "phase": "SPRINT_SETUP",
        "type": "execution_plan",
        "content": f"Sprint {sprint} execution plan confirmed",
    })
    finalize_phase(state["run_id"])

    return state
