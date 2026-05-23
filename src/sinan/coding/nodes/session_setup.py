"""session_setup — fan-out parallel context reads, then run init.sh.

session_setup is split into two parts:
  - session_setup_entry: fans out to 4 parallel reads (pwd / progress / feature_list / git_log)
  - session_setup_exit:  fans in and runs init.sh

Agent: Initializer
Loop:  Session

Reads (parallel, via session_context reducer):
    harness/claude-progress.txt
    harness/feature_list.json
    harness/.git/ (git log)

Writes:
    state["session_context"]   — merged from 4 parallel reads
    state["messages"]         — appends git history to messages
    state["current_phase"]    — "SESSION_SETUP"

Artifacts:
    (reads 4 handoff files; executes init.sh)

Routes:
    → READ_PARALLEL  (4-node fan-out)
    → sanity_check  after fan-in + init.sh
"""
from __future__ import annotations
import subprocess
from ..state import CodingState
from sinan.artifacts import (
    update_run_state, append_progress_log,
    append_decision_log, finalize_phase, get_run_dir,
)


def session_setup_entry_node(state: CodingState) -> dict:
    """Entry: just set phase, the fan-out is handled by graph routing."""
    update_run_state(state["run_id"], "SESSION_SETUP")
    state["current_phase"] = "SESSION_SETUP"
    append_progress_log(state["run_id"], "SESSION_SETUP",
        f"Session {state.get('session_number', 1)}: delegating to 4 parallel context reads")
    return state


def session_setup_exit_node(state: CodingState) -> dict:
    """Exit: merge session_context, run init.sh, route to sanity_check."""
    session = state.get("session_number", 1)
    update_run_state(state["run_id"], "SESSION_SETUP_EXIT")
    append_progress_log(state["run_id"], "SESSION_SETUP_EXIT",
        f"Session {session}: 4 context reads complete")

    # Append git history to messages for Generator/Evaluator context
    git_history = state.get("session_context", {}).get("git_history", "")
    state["messages"] = state.get("messages", [])
    state["messages"].append({
        "role": "system",
        "content": f"Git history:\n{git_history}" if git_history else "No git history yet",
    })

    # Run init.sh
    harness_dir = get_run_dir(state["run_id"]) / "harness"
    init_sh = harness_dir / "init.sh"
    if init_sh.exists():
        try:
            subprocess.run(
                ["bash", str(init_sh)],
                cwd=harness_dir,
                capture_output=True,
                text=True,
                timeout=60,
            )
            append_progress_log(state["run_id"], "SESSION_SETUP_EXIT",
                "init.sh executed successfully")
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            append_progress_log(state["run_id"], "SESSION_SETUP_EXIT",
                f"init.sh warning: {e}")

    state["current_phase"] = "SESSION_SETUP_EXIT"
    append_decision_log(state["run_id"], {
        "phase": "SESSION_SETUP",
        "type": "session_ready",
        "content": f"Session {session} context loaded, project ready",
    })
    finalize_phase(state["run_id"])

    return state
