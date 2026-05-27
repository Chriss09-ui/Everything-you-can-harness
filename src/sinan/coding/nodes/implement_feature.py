"""implement_feature — Generator implements the selected feature.

Agent: Generator
Loop:  Feature

Reads:
    state["current_feature_id"]  — feature to implement
    state["feature_list"]        — feature registry
    state["spec"]                — product spec
    state["feature_retry_count"] — current retry attempt

Writes:
    state["implement_result"]       — LLM response {status, files, summary}
    state["current_feature_status"] — "implemented" | "error"
    state["feature_retry_count"]    — incremented
    state["session_progress_count"] — incremented
    state["current_phase"]          — "IMPLEMENT_FEATURE"

Artifacts:
    writes source files to harness/ per LLM output

Routes:
    → test_feature  (linear)
"""
from __future__ import annotations
import json
from ..state import CodingState
from ..prompts import get_coding_prompt
from sinan.llm import get_llm_client
from sinan.validation import parse_and_validate_artifact
from sinan.artifacts import (
    write_json, update_run_state, append_progress_log,
    append_decision_log, finalize_phase, get_run_dir,
)


def implement_feature_node(state: CodingState) -> dict:
    feature_id = state.get("current_feature_id")
    update_run_state(state["run_id"], "IMPLEMENT_FEATURE")
    append_progress_log(state["run_id"], "IMPLEMENT_FEATURE",
        f"Implementing feature: {feature_id}")

    client = get_llm_client()
    system = get_coding_prompt("coding_generator")

    feature_list = state.get("feature_list") or {}
    features = feature_list.get("features", [])
    feature = next((f for f in features if f.get("id") == feature_id), None)
    spec = state.get("spec") or {}

    if not feature:
        # Fail fast — silently returning leaves test_feature to operate on
        # a missing feature, which produces a confusing "passed/failed"
        # report downstream. Better to surface the routing/feature_list
        # corruption here.
        available = [f.get("id") for f in features]
        raise RuntimeError(
            f"implement_feature: feature '{feature_id}' not found in "
            f"feature_list (have {available}). pick_feature misrouted or "
            f"feature_list got corrupted."
        )

    harness_dir = get_run_dir(state["run_id"]) / "harness"
    feature_retry = state.get("feature_retry_count", 0)
    user = (
        f"请实现以下功能：\n\n"
        f"Feature: {json.dumps(feature, indent=2, ensure_ascii=False)}\n\n"
        f"产品规格：\n{json.dumps(spec, indent=2, ensure_ascii=False)}\n\n"
        f"项目目录：{harness_dir}\n\n"
        f"输出 JSON：{{\"status\": \"implemented\", \"files\": [{{\"path\": \"...\", \"content\": \"...\", \"action\": \"create\"}}], \"summary\": \"...\"}}"
    )

    raw = client.generate(system, user)
    result = parse_and_validate_artifact(raw, "implement_result")

    for f in result.get("files", []):
        target = harness_dir / f["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f["content"])

    state["implement_result"] = result
    state["current_feature_status"] = "implemented"
    state["feature_retry_count"] = feature_retry + 1
    state["session_progress_count"] = state.get("session_progress_count", 0) + 1
    state["current_phase"] = "IMPLEMENT_FEATURE"

    append_progress_log(state["run_id"], "IMPLEMENT_FEATURE",
        f"{feature_id}: {result.get('summary', 'implemented')}")
    append_decision_log(state["run_id"], {
        "phase": "IMPLEMENT_FEATURE",
        "type": "feature_implemented",
        "content": f"Feature {feature_id} implemented",
        "rationale": result.get("summary", ""),
    })
    finalize_phase(state["run_id"])

    return state
