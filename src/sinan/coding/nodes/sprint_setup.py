"""sprint_setup — Generator announces execution plan after negotiation.

Agent: Generator
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
from sinan.validation import parse_and_validate_artifact
from sinan.llm import get_llm_client
from sinan.artifacts import (
    write_json, update_run_state, append_progress_log,
    append_decision_log, finalize_phase,
)


def sprint_setup_node(state: CodingState) -> dict:
    sprint = state.get("sprint_number", 1)
    update_run_state(state["run_id"], "SPRINT_SETUP")
    append_progress_log(state["run_id"], "SPRINT_SETUP",
        f"Sprint {sprint}: Generator announcing execution plan")

    client = get_llm_client()
    system = get_coding_prompt("coding_generator")
    contract = state.get("sprint_contract") or {}
    spec = state.get("spec") or {}

    user = (
        f"Sprint 目标已确认：\n{json.dumps(contract, indent=2, ensure_ascii=False)}\n\n"
        f"产品规格：\n{json.dumps(spec, indent=2, ensure_ascii=False)}\n\n"
        f"请宣读你的执行方案，列出你将按什么顺序实现哪些功能，以及你的实现策略。\n"
        f"输出 JSON: {{\"execution_order\": [...], \"strategy\": \"...\"}}"
    )

    raw = client.generate(system, user)
    plan = parse_and_validate_artifact(raw, "execution_plan")

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
