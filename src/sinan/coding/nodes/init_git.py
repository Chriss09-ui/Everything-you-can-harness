"""init_git — initialize git repository (Initializer parallel branch 4/5).

Agent: Initializer
Loop:  Session (Sprint 1 init, parallel fan-out)

Reads:
    state["run_id"]

Writes:
    state["current_phase"]  — "INIT_GIT"

Artifacts:
    harness/.git/  — git repository (handoff file)
    harness/src/   — source root

Routes:
    → session_setup  (linear, fan-in to coordinator)
"""
from __future__ import annotations
from ..state import CodingState
from ..git import git_init
from sinan.artifacts import (
    update_run_state, append_progress_log, get_run_dir,
)


def init_git_node(state: CodingState) -> dict:
    update_run_state(state["run_id"], "INIT_GIT")

    run_id = state["run_id"]
    harness_dir = get_run_dir(run_id) / "harness"
    harness_dir.mkdir(parents=True, exist_ok=True)

    git_init(run_id)
    (harness_dir / "src").mkdir(parents=True, exist_ok=True)

    # NOTE: do NOT write state["current_phase"] — see init_progress.py.
    append_progress_log(run_id, "INIT_GIT", "git repository initialized")
    # Returning {} keeps this a side-effect-only step; see init_progress.py.
    return {}
