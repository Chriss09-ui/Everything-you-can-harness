"""init_script — write init.sh (Initializer parallel branch 2/5).

Agent: Initializer
Loop:  Session (Sprint 1 init, parallel fan-out)

Reads:
    state["spec"]  — product spec for tech_stack

Writes:
    state["current_phase"]  — "INIT_SCRIPT"

Artifacts:
    harness/init.sh  — startup script (handoff file)

Routes:
    → session_setup  (linear, fan-in to coordinator)
"""
from __future__ import annotations
from ..state import CodingState
from sinan.artifacts import (
    update_run_state, append_progress_log, get_run_dir,
)


def init_script_node(state: CodingState) -> dict:
    update_run_state(state["run_id"], "INIT_SCRIPT")

    spec = state.get("spec") or {}
    tech = spec.get("tech_stack", [])
    harness_dir = get_run_dir(state["run_id"]) / "harness"
    harness_dir.mkdir(parents=True, exist_ok=True)

    lines = ["#!/bin/bash", "set -e", "echo 'Initializing project...'"]
    if "Python" in tech or "python" in tech:
        lines.append("pip install -r requirements.txt 2>/dev/null || true")
    if "Node" in tech or "npm" in str(tech).lower():
        lines.append("npm install 2>/dev/null || true")
    lines.append("echo 'Init complete.'")

    init_path = harness_dir / "init.sh"
    init_path.write_text("\n".join(lines) + "\n")
    init_path.chmod(0o755)

    # NOTE: do NOT write state["current_phase"] — see init_progress.py.
    append_progress_log(state["run_id"], "INIT_SCRIPT", "init.sh created")
    return state
