"""init_feature_list — write feature_list.json (Initializer parallel branch 3/5).

Agent: Initializer
Loop:  Session (Sprint 1 init, parallel fan-out)

Reads:
    state["spec"]  — product spec for features

Writes:
    state["feature_list"]   — in-memory view
    state["current_phase"]  — "INIT_FEATURE_LIST"

Artifacts:
    harness/feature_list.json  — feature registry (handoff file)

Routes:
    → session_setup  (linear, fan-in to coordinator)
"""
from __future__ import annotations
import json
from ..state import CodingState
from sinan.artifacts import (
    update_run_state, append_progress_log, get_run_dir,
)


def init_feature_list_node(state: CodingState) -> dict:
    update_run_state(state["run_id"], "INIT_FEATURE_LIST")

    spec = state.get("spec") or {}
    features = spec.get("features", [])
    harness_dir = get_run_dir(state["run_id"]) / "harness"
    harness_dir.mkdir(parents=True, exist_ok=True)

    feature_list = {"features": features, "total": len(features)}
    fl_path = harness_dir / "feature_list.json"
    fl_path.write_text(json.dumps(feature_list, indent=2, ensure_ascii=False))

    state["feature_list"] = feature_list
    state["current_phase"] = "INIT_FEATURE_LIST"
    append_progress_log(state["run_id"], "INIT_FEATURE_LIST",
        f"feature_list.json created with {len(features)} features")
    return state
