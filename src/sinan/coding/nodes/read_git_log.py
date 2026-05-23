"""read_git_log — read git commit history (Session parallel branch 4/4).

Agent: Initializer
Loop:  Session (parallel fan-out)

Reads:
    state["run_id"]

Writes:
    state["messages"]                           — appends git history message
    state["session_context"]["git_history"]  — history string (via reducer merge)

Artifacts:
    (reads from harness/.git/)

Routes:
    → session_setup_exit  (linear, fan-in to coordinator)
"""
from __future__ import annotations
from ..state import CodingState
from ..git import git_log
from sinan.artifacts import update_run_state


def read_git_log_node(state: CodingState) -> dict:
    update_run_state(state["run_id"], "READ_GIT_LOG")

    git_history = git_log(state["run_id"])

    return {
        "session_context": {"git_history": git_history or "No git history yet"},
    }
