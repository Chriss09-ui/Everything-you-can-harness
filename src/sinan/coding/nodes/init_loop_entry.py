"""init_loop_entry — mark entry into Coding Loop (Initializer parallel branch 5/5).

Agent: Initializer
Loop:  Session (Sprint 1 init, parallel fan-out)

Reads:
    state["run_id"]

Writes:
    state["current_phase"]  — "INIT_LOOP_ENTRY"

Artifacts:
    decision log entry (no file)

Routes:
    → session_setup  (linear, fan-in to coordinator)
"""
from __future__ import annotations
from ..state import CodingState
from sinan.artifacts import (
    update_run_state, append_progress_log, append_decision_log,
)


def init_loop_entry_node(state: CodingState) -> dict:
    update_run_state(state["run_id"], "INIT_LOOP_ENTRY")

    # NOTE: do NOT write state["current_phase"] — see init_progress.py.
    append_progress_log(state["run_id"], "INIT_LOOP_ENTRY", "Entering Coding Agent Loop")
    append_decision_log(state["run_id"], {
        "phase": "INIT_LOOP_ENTRY",
        "type": "loop_entry",
        "content": "Initializer complete — entering Coding Agent Loop",
    })
    return state
