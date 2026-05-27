"""commit_feature — mark feature status, git commit, update progress.

Status rules:
  - test_result.passed=True  → feature.passes=True, feature.blocked=False
  - test_result.passed=False → feature.passes=False, feature.blocked=True
    (retry cap reached — code is committed to preserve progress, but the
    feature is excluded from sprint_complete's "done" count and from
    pick_feature's "ready" pool so the sprint can move on.)

Agent: Generator
Loop:  Feature

Reads:
    state["current_feature_id"]  — feature to commit
    state["feature_list"]        — feature registry
    state["test_result"]         — last test_result (passed: bool)

Writes:
    state["feature_list"]           — updated (passes / blocked flag)
    state["current_feature_id"]     — reset to None
    state["current_feature_status"] — "committed" | "blocked"
    state["last_good_commit"]       — current HEAD (only when passed)
    state["current_phase"]          — "COMMIT_FEATURE"

Artifacts (handoff files):
    feature_list.json     — marks feature status
    claude-progress.txt   — appends PASS / BLOCKED entry
    git commit            — saves checkpoint

Routes:
    → pick_feature   when more sprint-scoped features remain
    → evaluator_qa   when all sprint features done or blocked
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

    # test_result is set by test_feature_node. Default to True only when
    # missing in the very first happy-path mock scenarios — production runs
    # always have it populated.
    test_result = state.get("test_result") or {}
    test_passed = bool(test_result.get("passed"))

    # Mark feature as passed/blocked in feature_list.json. Fail-fast if the
    # file is missing — without it the next sprint's pick_feature would
    # re-read a stale version and re-pick the same feature forever.
    fl_path = harness_dir / "feature_list.json"
    if not fl_path.exists():
        raise RuntimeError(
            f"commit_feature: feature_list.json missing at {fl_path}. "
            f"This usually means init_feature_list was skipped or generator "
            f"wiped the file. Refusing to silently drop feature.passes=True; "
            f"recover manually or rerun from a previous checkpoint."
        )
    with open(fl_path) as f:
        feature_list = json.load(f)
    for f_item in feature_list.get("features", []):
        if f_item.get("id") == feature_id:
            if test_passed:
                f_item["passes"] = True
                f_item["blocked"] = False
            else:
                # Failed twice → code committed as a checkpoint, but the
                # feature is NOT done. Mark blocked so sprint_complete /
                # pick_feature skip it and the sprint can advance.
                f_item["passes"] = False
                f_item["blocked"] = True
    with open(fl_path, "w") as f:
        json.dump(feature_list, f, indent=2, ensure_ascii=False)
    state["feature_list"] = feature_list

    # Update claude-progress.txt
    progress_path = harness_dir / "claude-progress.txt"
    if progress_path.exists():
        with open(progress_path) as f:
            content = f.read()
        tag = "PASS" if test_passed else "BLOCKED (retry cap reached)"
        content += f"\n- [{feature_id}] {tag}\n"
        with open(progress_path, "w") as f:
            f.write(content)

    # Git commit (always — preserving progress even on block)
    status_label = "implemented" if test_passed else "blocked"
    commit_msg = f"feat({feature_id}): {status_label}"
    git_commit(run_id, commit_msg)
    # Only advance last_good_commit on real passes; a blocked commit is a
    # checkpoint, not a state we'd want to revert to as "known good".
    if test_passed:
        git_save_good_commit(run_id, state)

    state["current_feature_id"] = None
    state["current_feature_status"] = "committed" if test_passed else "blocked"
    state["current_phase"] = "COMMIT_FEATURE"

    append_decision_log(state["run_id"], {
        "phase": "COMMIT_FEATURE",
        "type": "feature_committed" if test_passed else "feature_blocked",
        "content": f"Feature {feature_id} {'passed' if test_passed else 'blocked (retry cap)'} and committed",
    })
    finalize_phase(state["run_id"])

    return state
