"""read_feature_list — read feature_list.json (Session parallel branch 3/4).

Agent: Initializer
Loop:  Session (parallel fan-out)

Reads:
    state["run_id"]

Writes:
    state["feature_list"]                — in-memory view (set here)
    state["session_context"]["feature_list"]  — file content snapshot (via reducer merge)

Artifacts:
    (reads harness/feature_list.json)

Routes:
    → session_setup_exit  (linear, fan-in to coordinator)
"""
from __future__ import annotations
import json
from ..state import CodingState
from sinan.artifacts import (
    update_run_state, get_run_dir,
)


def read_feature_list_node(state: CodingState) -> dict:
    update_run_state(state["run_id"], "READ_FEATURE_LIST")

    harness_dir = get_run_dir(state["run_id"]) / "harness"
    fl_path = harness_dir / "feature_list.json"

    if fl_path.exists():
        with open(fl_path) as f:
            feature_list = json.load(f)
    else:
        feature_list = {"features": [], "total": 0}

    return {
        "feature_list": feature_list,
        "session_context": {"feature_list": feature_list},
    }
