"""commit_feature — mark feature passes=true, git commit, update progress.

Agent: Generator
Loop:  Feature

Reads:
    state["current_feature_id"]  — feature to commit
    state["feature_list"]        — feature registry

Writes:
    state["feature_list"]           — updated (feature.passes=true)
    state["current_feature_id"]     — reset to None
    state["current_feature_status"] — "committed"
    state["last_good_commit"]       — current HEAD
    state["current_phase"]          — "COMMIT_FEATURE"

Artifacts (handoff files):
    feature_list.json     — marks feature as passes=true
    claude-progress.txt   — appends completion entry
    git commit            — saves checkpoint

Routes:
    → pick_feature      when more sprint-scoped features remain
    → generator_review  when all sprint features done
"""
from __future__ import annotations
import json
from ..state import CodingState
from ..git import git_commit, git_save_good_commit
from sinan.artifacts import (
    write_json, update_run_state, append_progress_log,
    append_decision_log, finalize_phase, get_run_dir,
)


def commit_feature_node(state: CodingState) -> dict:
    feature_id = state.get("current_feature_id")
    update_run_state(state["run_id"], "COMMIT_FEATURE")
    append_progress_log(state["run_id"], "COMMIT_FEATURE", f"Committing feature: {feature_id}")

    run_id = state["run_id"]
    harness_dir = get_run_dir(run_id) / "harness"

    # Mark feature as passed in feature_list.json
    fl_path = harness_dir / "feature_list.json"
    if fl_path.exists():
        with open(fl_path) as f:
            feature_list = json.load(f)
        for f_item in feature_list.get("features", []):
            if f_item.get("id") == feature_id:
                f_item["passes"] = True
        with open(fl_path, "w") as f:
            json.dump(feature_list, f, indent=2, ensure_ascii=False)
        state["feature_list"] = feature_list
    else:
        append_progress_log(state["run_id"], "COMMIT_FEATURE", "feature_list.json not found")

    # Update claude-progress.txt
    progress_path = harness_dir / "claude-progress.txt"
    if progress_path.exists():
        with open(progress_path) as f:
            content = f.read()
        content += f"\n- [{feature_id}] PASS\n"
        with open(progress_path, "w") as f:
            f.write(content)

    # Git commit
    commit_msg = f"feat({feature_id}): {state.get('current_feature_status', 'implemented')}"
    git_commit(run_id, commit_msg)
    git_save_good_commit(run_id, state)

    state["current_feature_id"] = None
    state["current_feature_status"] = "committed"
    state["current_phase"] = "COMMIT_FEATURE"

    append_decision_log(state["run_id"], {
        "phase": "COMMIT_FEATURE",
        "type": "feature_committed",
        "content": f"Feature {feature_id} marked as passing and committed",
    })
    finalize_phase(state["run_id"])

    return state
