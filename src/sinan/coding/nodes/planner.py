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
    append_decision_log, finalize_phase, get_run_dir,
)


def planner_node(state: CodingState) -> dict:
    update_run_state(state["run_id"], "PLANNER")
    append_progress_log(state["run_id"], "PLANNER", "Expanding design draft into product spec")

    # Prefer state; fall back to disk so the coding layer can run independently
    # (e.g. via `python -m sinan.cli --from-design <run_id>`).
    draft = state.get("harness_design_draft") or {}
    if not draft:
        draft_path = get_run_dir(state["run_id"]) / "harness_design_draft.json"
        if draft_path.exists():
            with open(draft_path, encoding="utf-8") as f:
                draft = json.load(f)
            append_progress_log(state["run_id"], "PLANNER",
                f"Loaded harness_design_draft.json from {draft_path}")

    # Schema guard at the architecture→coding boundary. We only enforce when
    # the draft carries final_spec's version marker — otherwise it's a hand-
    # rolled fixture (e.g. coding-layer-only test), and strict validation
    # would just impede local development.
    if draft and draft.get("version"):
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
