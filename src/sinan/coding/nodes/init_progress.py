"""init_progress — write claude-progress.txt (Initializer parallel branch 1/5).

Agent: Initializer
Loop:  Session (Sprint 1 init, parallel fan-out)

Reads:
    state["spec"]  — product spec for feature count

Writes:
    state["current_phase"]  — "INIT_PROGRESS"

Artifacts:
    harness/claude-progress.txt  — Coding progress tracker (handoff file)

Routes:
    → session_setup  (linear, fan-in to coordinator)
"""
from __future__ import annotations
from ..state import CodingState
from sinan.artifacts import (
    update_run_state, append_progress_log, get_run_dir,
)


def init_progress_node(state: CodingState) -> dict:
    update_run_state(state["run_id"], "INIT_PROGRESS")

    spec = state.get("spec") or {}
    features = spec.get("features", [])
    harness_dir = get_run_dir(state["run_id"]) / "harness"
    harness_dir.mkdir(parents=True, exist_ok=True)

    content = (
        "# Coding Progress\n\n"
        "## Completed Features\n\n"
        "(none yet)\n\n"
        "## Current Sprint\n\n"
        f"Sprint 1: {len(features)} features planned\n"
    )
    (harness_dir / "claude-progress.txt").write_text(content)

    # NOTE: do NOT write state["current_phase"] here. This node runs inside a
    # Send() fan-out with 4 siblings, all of which would race on the default
    # last-writer-wins reducer. The phase is set by session_setup_entry after
    # the fan-in completes.
    append_progress_log(state["run_id"], "INIT_PROGRESS", "claude-progress.txt created")
    # Returning {} (not state) keeps this node a pure side-effect step. The
    # Send() fan-out siblings all share the default LastValue reducer on every
    # state field — returning the full state would re-write every key from each
    # parallel branch and trip InvalidUpdateError.
    return {}
