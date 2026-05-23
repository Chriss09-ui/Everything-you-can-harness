"""session_init — coordinator: route to parallel init (Sprint 1) or skip (subsequent sprints).

Agent: Initializer
Loop:  Session (entry point)

Reads:
    state["sprint_number"]   — current sprint
    state["session_number"]  — current session

Writes:
    state["current_phase"]           — "SESSION_INIT"
    state["session_progress_count"]  — reset to 0

Artifacts:
    (none — delegation only)

Routes:
    → init_parallel  when sprint=1 and session=1 (5-node fan-out)
    → session_setup  when subsequent sprint/session
"""
from __future__ import annotations
from ..state import CodingState
from sinan.artifacts import (
    update_run_state, append_progress_log, finalize_phase,
)


def session_init_node(state: CodingState) -> dict:
    sprint = state.get("sprint_number", 1)
    session = state.get("session_number", 1)

    update_run_state(state["run_id"], "SESSION_INIT")

    if sprint == 1 and session == 1:
        append_progress_log(state["run_id"], "SESSION_INIT",
            "Sprint 1, Session 1: delegating to 5 parallel init branches")
        state["_is_first_init"] = True
    else:
        append_progress_log(state["run_id"], "SESSION_INIT",
            f"Sprint {sprint}: skipping parallel init, using existing artifacts")
        state["_is_first_init"] = False

    state["current_phase"] = "SESSION_INIT"
    state["session_progress_count"] = 0
    finalize_phase(state["run_id"])

    return state
