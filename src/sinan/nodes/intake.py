"""intake — receive raw user input and initialize state.

Agent: — (entrypoint, 不在 graph 中注册)
Layer: 需求层 (前置)

Reads:
    (external parameter: user_input)

Writes:
    state["user_raw_input"]  — raw user input string
    state["current_phase"]    — "INTAKE"
    state["messages"]         — appends user message

Artifacts:
    (none)

Routes:
    (called externally before graph.invoke)
"""
from __future__ import annotations
from ..state import HarnessBuilderState
from ..artifacts import update_run_state, append_progress_log, append_decision_log


def intake_node(state: HarnessBuilderState, user_input: str) -> dict:
    update_run_state(state["run_id"], "INTAKE")
    state["user_raw_input"] = user_input
    state["current_phase"] = "INTAKE"
    state["messages"].append({"role": "user", "content": user_input})

    append_progress_log(state["run_id"], "INTAKE", f"Received user input: {user_input[:80]}...")
    append_decision_log(state["run_id"], {
        "phase": "INTAKE",
        "type": "intake",
        "content": f"User submitted raw input ({len(user_input)} chars)",
    })

    return state
