"""read_progress — read claude-progress.txt (Session parallel branch 2/4).

Agent: Initializer
Loop:  Session (parallel fan-out)

Reads:
    state["run_id"]

Writes:
    state["session_context"]["progress"]  — progress file content (via reducer merge)

Artifacts:
    (reads harness/claude-progress.txt)

Routes:
    → session_setup_exit  (linear, fan-in to coordinator)
"""
from __future__ import annotations
from ..state import CodingState
from sinan.artifacts import (
    update_run_state, get_run_dir,
)


def read_progress_node(state: CodingState) -> dict:
    update_run_state(state["run_id"], "READ_PROGRESS")

    harness_dir = get_run_dir(state["run_id"]) / "harness"
    progress_path = harness_dir / "claude-progress.txt"

    if progress_path.exists():
        content = progress_path.read_text()
    else:
        content = ""

    return {
        "session_context": {"progress": content},
    }
