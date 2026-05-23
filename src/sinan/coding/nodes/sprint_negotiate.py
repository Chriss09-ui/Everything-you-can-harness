"""sprint_negotiate — Evaluator reviews sprint proposal, negotiate until agreement.

Agent: Evaluator
Loop:  Sprint (negotiation, ≤3 rounds)

Reads:
    state["sprint_contract"]  — draft contract from sprint_plan
    state["negotiate_round"]   — current negotiation round

Writes:
    state["sprint_contract"]  — updates agreed flag + negotiation_history
    state["negotiate_round"]  — incremented
    state["current_phase"]    — "SPRINT_NEGOTIATE"

Artifacts:
    sprint_contract.json  — versioned

Routes:
    → sprint_setup   when agreed=true or round>3
    → sprint_plan    when disagreed
"""
from __future__ import annotations
import json
from ..state import CodingState
from ..prompts import get_coding_prompt
from ..parse_json import _parse_json
from sinan.llm import get_llm_client
from sinan.artifacts import (
    write_json, update_run_state, append_progress_log,
    append_decision_log, finalize_phase,
)


def sprint_negotiate_node(state: CodingState) -> dict:
    round_num = state.get("negotiate_round", 1)
    update_run_state(state["run_id"], "SPRINT_NEGOTIATE")
    append_progress_log(state["run_id"], "SPRINT_NEGOTIATE",
        f"Evaluator reviewing sprint proposal (round {round_num})")

    client = get_llm_client()
    system = get_coding_prompt("coding_negotiator")
    contract = state.get("sprint_contract") or {}

    user = f"请审核以下 Sprint 目标提案：\n\n{json.dumps(contract, indent=2, ensure_ascii=False)}"
    raw = client.generate(system, user)
    review = _parse_json(raw, "sprint_negotiate")

    agreed = review.get("agreed", False)
    contract["agreed"] = agreed
    contract["negotiation_history"] = contract.get("negotiation_history", [])
    contract["negotiation_history"].append({
        "round": round_num,
        "review": review,
    })

    write_json(state["run_id"], "sprint_contract.json", contract, versioned=True)
    state["sprint_contract"] = contract
    state["negotiate_round"] = round_num + 1
    state["current_phase"] = "SPRINT_NEGOTIATE"

    append_decision_log(state["run_id"], {
        "phase": "SPRINT_NEGOTIATE",
        "type": "negotiate_result",
        "content": f"Round {round_num}: {'agreed' if agreed else 'needs revision'}",
    })
    finalize_phase(state["run_id"])

    return state
