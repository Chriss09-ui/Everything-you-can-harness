"""planner — expand harness_design_draft into a full product spec with feature list.

Agent: Planner
Loop:  Sprint (entry point)

Reads:
    state["harness_design_draft"]                       — design layer output (preferred)
    runs/<run_id>/harness_design_draft.json (fallback)  — when state is empty,
                                                          enables independent
                                                          coding-layer startup

Writes:
    state["spec"]          — full product spec dict
    state["feature_list"]  — {features: [...], total: N}
    state["current_phase"] — "PLANNER"

Artifacts:
    spec.json  — persisted product spec

Routes:
    → sprint_plan  (linear)
"""
from __future__ import annotations
import json
from ..state import CodingState
from ..prompts import get_coding_prompt
from sinan.validation import parse_and_validate_artifact, validate_artifact
from sinan.llm import get_llm_client
from sinan.artifacts import (
    write_json, update_run_state, append_progress_log,
    append_decision_log, finalize_phase, load_state_or_file,
)


def planner_node(state: CodingState) -> dict:
    update_run_state(state["run_id"], "PLANNER")
    append_progress_log(state["run_id"], "PLANNER", "Expanding design draft into product spec")

    # State-or-disk handoff at the design→coding boundary. State is the hot
    # path inside one CLI invocation; disk is the recovery path for
    # `python -m sinan.cli --from-design <run_id>`.
    state_had_draft = bool(state.get("harness_design_draft"))
    draft = load_state_or_file(state, "harness_design_draft")
    if draft and not state_had_draft:
        append_progress_log(state["run_id"], "PLANNER",
            "Loaded harness_design_draft.json from disk")

    # Schema guard at the architecture→coding boundary. Always enforce —
    # the contract is that harness_design_draft carries the required fields
    # (version, use_case, graph, phase_sequence, ...). Tests that pass in a
    # hand-rolled fixture must include those fields; the schema is the codified
    # contract and shouldn't be silently bypassed.
    if draft:
        validate_artifact(draft, "harness_design_draft")

    client = get_llm_client()
    system = get_coding_prompt("coding_planner")
    user = f"请基于以下 harness 架构设计包，生成完整的产品规格说明书：\n\n{json.dumps(draft, indent=2, ensure_ascii=False)}"

    raw = client.generate(system, user)
    spec = parse_and_validate_artifact(raw, "spec")

    write_json(state["run_id"], "spec.json", spec)
    state["spec"] = spec
    state["current_phase"] = "PLANNER"

    features = spec.get("features", [])
    feature_list = {"features": features, "total": len(features)}
    state["feature_list"] = feature_list

    append_progress_log(state["run_id"], "PLANNER",
        f"Product spec generated: {len(features)} features")
    append_decision_log(state["run_id"], {
        "phase": "PLANNER",
        "type": "artifact_generated",
        "content": f"Generated spec with {len(features)} features",
        "rationale": "Expanded design draft into implementable feature list",
    })
    finalize_phase(state["run_id"])

    return state
