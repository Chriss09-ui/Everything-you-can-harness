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
    # Pass started_at forward so run_state.yaml's started_at is consistent
    # from the very first phase, not set later by spec_expansion.
    update_run_state(state["run_id"], "INTAKE", started_at=state.get("started_at", ""))

    append_progress_log(state["run_id"], "INTAKE", f"Received user input: {user_input[:80]}...")
    append_decision_log(state["run_id"], {
        "phase": "INTAKE",
        "type": "intake",
        "content": f"User submitted raw input ({len(user_input)} chars)",
    })

    # intake is called externally (cli.py, tests) BEFORE graph.invoke, so we
    # must return the full state, not a partial — graph.invoke needs run_id,
    # started_at, etc. to be present. The in-graph nodes downstream of
    # intake don't run (it's not even registered as a graph node), so the
    # reducer pattern doesn't apply here; safe to mutate in place.
    state["user_raw_input"] = user_input
    state["current_phase"] = "INTAKE"
    state.setdefault("messages", []).append({"role": "user", "content": user_input})
    return state
