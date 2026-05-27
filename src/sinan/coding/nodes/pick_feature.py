"""pick_feature — select highest-priority ready feature (dependencies met).

Agent: Generator
Loop:  Feature (entry point)

Reads:
    state["feature_list"]    — {features: [...], total: N}
    state["sprint_contract"] — {sprint_goals: [...]}

Writes:
    state["current_feature_id"]     — selected feature id or None
    state["current_feature_status"] — "selected" | "blocked"
    state["feature_retry_count"]    — reset to 0 on selection
    state["current_phase"]          — "PICK_FEATURE"

Artifacts:
    (none)

Routes:
    → implement_feature  when current_feature_id is set
    → evaluator_qa       when no feature selected (sprint scope done)
"""
from __future__ import annotations
import json
from ..state import CodingState
from sinan.artifacts import (
    write_json, update_run_state, append_progress_log,
    append_decision_log, finalize_phase, get_run_dir,
)


def pick_feature_node(state: CodingState) -> dict:
    update_run_state(state["run_id"], "PICK_FEATURE")
    append_progress_log(state["run_id"], "PICK_FEATURE", "Selecting next feature")

    feature_list = state.get("feature_list") or {}
    features = feature_list.get("features", [])
    sprint_contract = state.get("sprint_contract") or {}
    sprint_goals = sprint_contract.get("sprint_goals", [])

    # Filter to sprint-scoped features
    sprint_feature_ids = {g.get("feature_id") for g in sprint_goals if g.get("feature_id")}
    sprint_features = [f for f in features if f.get("id") in sprint_feature_ids]

    # Get passing feature IDs
    passing_ids = {f["id"] for f in features if f.get("passes")}

    # Select ready feature: not done, not blocked, dependencies met, highest priority
    ready = []
    for f in sprint_features:
        if f.get("passes"):
            continue
        if f.get("blocked"):
            # Hit retry cap in a previous attempt — skip, do not keep
            # re-selecting something we've already given up on this sprint.
            continue
        deps = f.get("depends_on", [])
        if all(dep in passing_ids for dep in deps):
            ready.append(f)

    if not ready:
        # No ready features in sprint scope — check if all done/blocked or stuck
        unfinished = [f for f in sprint_features if not f.get("passes") and not f.get("blocked")]
        if not unfinished:
            blocked = [f for f in sprint_features if f.get("blocked")]
            if blocked:
                append_progress_log(state["run_id"], "PICK_FEATURE",
                    f"All sprint features done or blocked ({len(blocked)} blocked)")
            else:
                append_progress_log(state["run_id"], "PICK_FEATURE", "All sprint features completed")
        else:
            append_progress_log(state["run_id"], "PICK_FEATURE",
                f"Blocked: dependencies not met for {len(unfinished)} features")
        state["current_feature_id"] = None
        state["current_feature_status"] = "blocked"
        finalize_phase(state["run_id"])
        return state

    # Pick highest priority (lowest number = highest priority)
    chosen = min(ready, key=lambda f: f.get("priority", 999))

    state["current_feature_id"] = chosen["id"]
    state["current_feature_status"] = "selected"
    state["feature_retry_count"] = 0
    state["current_phase"] = "PICK_FEATURE"

    append_progress_log(state["run_id"], "PICK_FEATURE",
        f"Selected: {chosen['id']} (priority {chosen.get('priority', '?')})")
    append_decision_log(state["run_id"], {
        "phase": "PICK_FEATURE",
        "type": "feature_selected",
        "content": f"Selected feature {chosen['id']} for implementation",
    })
    finalize_phase(state["run_id"])

    return state
