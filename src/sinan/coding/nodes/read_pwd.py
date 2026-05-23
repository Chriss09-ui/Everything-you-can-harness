"""read_pwd — get current working directory (Session parallel branch 1/4).

Agent: Initializer
Loop:  Session (parallel fan-out)

Reads:
    state["run_id"]

Writes:
    state["session_context"]["pwd"]  — current working directory (via reducer merge)

Artifacts:
    (none)

Routes:
    → session_setup_exit  (linear, fan-in to coordinator)
"""
from __future__ import annotations
import os
from ..state import CodingState
from sinan.artifacts import (
    update_run_state, get_run_dir,
)


def read_pwd_node(state: CodingState) -> dict:
    update_run_state(state["run_id"], "READ_PWD")

    harness_dir = str(get_run_dir(state["run_id"]) / "harness")
    pwd = os.getcwd() or harness_dir

    return {
        "session_context": {"pwd": pwd},
    }
