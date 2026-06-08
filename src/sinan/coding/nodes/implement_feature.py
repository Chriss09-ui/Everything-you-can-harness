"""implement_feature — Generator implements the selected feature.

Agent: Generator (Claude Agent SDK — autonomous tool use)
Loop:  Feature

Reads:
    state["current_feature_id"]  — feature to implement
    state["feature_list"]        — feature registry
    state["spec"]                — product spec
    state["feature_retry_count"] — current retry attempt

Writes:
    state["implement_result"]       — agent's final report {status, files, summary}
    state["current_feature_status"] — "implemented" | "error"
    state["feature_retry_count"]    — incremented
    state["session_progress_count"] — incremented
    state["current_phase"]          — "IMPLEMENT_FEATURE"

Artifacts:
    source files written into harness/ by the Generator agent itself
    (Read/Write/Edit/Bash/Glob/Grep), sandboxed to cwd=harness/ by the
    agent seam's PreToolUse hook — NOT by Python write_text.

Routes:
    → test_feature  (linear)
"""
from __future__ import annotations
import json
from ..state import CodingState
from ..prompts import get_coding_prompt
from sinan.agent import get_agent_runner
from sinan.validation import validate_artifact
from sinan.artifacts import (
    write_json, update_run_state, append_progress_log,
    append_decision_log, finalize_phase, get_run_dir,
)


# JSON-schema for the agent's final structured report. The agent does its work
# via tools, then emits this shape — same contract validate_artifact enforces.
_IMPLEMENT_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string"},
        "files": {"type": "array", "items": {"type": "object"}},
        "summary": {"type": "string"},
    },
    "required": ["status", "files"],
    "additionalProperties": True,
}

# Generator's working tool set: read/write/edit code, run commands, search.
_GENERATOR_TOOLS = ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]


def implement_feature_node(state: CodingState) -> dict:
    feature_id = state.get("current_feature_id")
    update_run_state(state["run_id"], "IMPLEMENT_FEATURE")
    append_progress_log(state["run_id"], "IMPLEMENT_FEATURE",
        f"Implementing feature: {feature_id}")

    runner = get_agent_runner()
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
    harness_dir.mkdir(parents=True, exist_ok=True)  # agent's cwd must exist
    feature_retry = state.get("feature_retry_count", 0)
    user = (
        f"请在当前项目目录中实现以下功能。你可以使用 Read/Write/Edit/Bash/Glob/Grep "
        f"工具直接创建、修改文件并运行命令——所有改动都在当前项目目录内完成。\n\n"
        f"Feature: {json.dumps(feature, indent=2, ensure_ascii=False)}\n\n"
        f"产品规格：\n{json.dumps(spec, indent=2, ensure_ascii=False)}\n\n"
        f"实现完成后，用 JSON 汇报你创建/修改了哪些文件：\n"
        f"{{\"status\": \"implemented\", \"files\": [{{\"path\": \"...\", \"action\": \"create|modify\"}}], \"summary\": \"...\"}}"
    )

    # The agent writes/edits files itself inside harness/ (sandboxed by the
    # seam's cwd + allowed_tools + PreToolUse hook), then returns the report.
    agent_result = runner.run(
        system=system,
        prompt=user,
        cwd=harness_dir,
        allowed_tools=_GENERATOR_TOOLS,
        schema=_IMPLEMENT_RESULT_SCHEMA,
    )
    result = agent_result.parse("implement_result")
    validate_artifact(result, "implement_result")

    state["implement_result"] = result
    state["current_feature_status"] = "implemented"
    state["feature_retry_count"] = feature_retry + 1
    state["session_progress_count"] = state.get("session_progress_count", 0) + 1
    state["current_phase"] = "IMPLEMENT_FEATURE"

    append_progress_log(state["run_id"], "IMPLEMENT_FEATURE",
        f"{feature_id}: {result.get('summary', 'implemented')} "
        f"[agent: {agent_result.num_turns} turns, ${agent_result.total_cost_usd:.4f}]")
    append_decision_log(state["run_id"], {
        "phase": "IMPLEMENT_FEATURE",
        "type": "feature_implemented",
        "content": f"Feature {feature_id} implemented",
        "rationale": result.get("summary", ""),
        "agent_cost_usd": agent_result.total_cost_usd,
        "agent_turns": agent_result.num_turns,
    })
    finalize_phase(state["run_id"])

    return state
