"""framework_adjust — Framework 基于子代理评审报告进行调整 (四步辩论 Step 3)。

Agent: 总工框架设计师
Layer: 架构层

Reads:
    state["framework_design"]   — from framework_design
    state["subagent_reviews"]  — from subagent_review

Writes:
    state["framework_design"]  — overwritten with adjusted version
    state["framework_adjustments"] — feedback responses and preserved elements
    state["current_phase"]       — "FRAMEWORK_ADJUST"
    state["artifact_versions"]   — records framework_design v2, framework_adjustment v1

Artifacts:
    framework_adjustment.json  (versioned)
    framework_design_v2.json  (versioned)

Routes:
    → zonggong_integrate  (linear)
"""
from __future__ import annotations
import json
from ..state import HarnessBuilderState
from ..llm import get_llm_client
from ..prompts import get_prompt
from ..artifacts import (
    write_json, update_run_state, append_progress_log,
    append_decision_log, finalize_phase, load_state_or_file,
)
from ..validation import parse_and_validate_artifact


def framework_adjust_node(state: HarnessBuilderState) -> dict:
    update_run_state(state["run_id"], "FRAMEWORK_ADJUST")
    append_progress_log(state["run_id"], "FRAMEWORK_ADJUST", "Framework agent adjusting based on sub-agent reviews")

    client = get_llm_client()
    brief = (
        load_state_or_file(state, "user_brief_form")
        or load_state_or_file(state, "requirement_pack")
        or {}
    )
    framework = load_state_or_file(state, "framework_design")
    reviews = load_state_or_file(state, "subagent_reviews")

    brief_text = json.dumps(brief, indent=2, ensure_ascii=False)
    framework_text = json.dumps(framework, indent=2, ensure_ascii=False)
    reviews_text = json.dumps(reviews, indent=2, ensure_ascii=False)

    system = get_prompt("zonggong_framework")
    user = (
        f"User Brief Form:\n{brief_text}\n\n"
        f"【当前 Framework 设计】\n{framework_text}\n\n"
        f"【子代理评审报告】\n{reviews_text}\n\n"
        f"请仔细阅读三个子代理的评审报告，逐条回应并调整 framework。"
        f"格式要求：接受合理的 feedback 并修改 framework；"
        f"对不合理的 feedback 说明拒绝理由。输出调整后的完整 framework。"
    )

    raw = client.generate(system, user)
    result = parse_and_validate_artifact(raw, "framework_adjustment")

    # 支持两种格式：新版带 feedback_responses，或者旧版直接是调整后的 framework
    adjusted = result.get("adjusted_framework", result)

    write_json(state["run_id"], "framework_adjustment.json", result, versioned=True)
    write_json(state["run_id"], "framework_design_v2.json", adjusted, versioned=True)

    state["framework_design"] = adjusted
    state["framework_adjustments"] = result
    state["current_phase"] = "FRAMEWORK_ADJUST"
    state["artifact_versions"]["framework_design"] = "2.0"
    state["artifact_versions"]["framework_adjustment"] = "1.0"

    responses = result.get("feedback_responses", [])
    accepted = sum(1 for r in responses if r.get("response") == "accepted")
    rejected = sum(1 for r in responses if r.get("response") == "rejected")
    preserved = result.get("preserved_elements", [])

    append_progress_log(
        state["run_id"], "FRAMEWORK_ADJUST",
        f"Framework adjusted: {accepted} accepted, {rejected} rejected, "
        f"{len(preserved)} preserved elements"
    )
    append_decision_log(state["run_id"], {
        "phase": "FRAMEWORK_ADJUST",
        "type": "framework_adjusted",
        "content": f"Framework adjusted based on sub-agent reviews: {accepted} changes accepted",
        "feedback_count": len(responses),
        "preserved": preserved,
    })
    finalize_phase(state["run_id"])

    return state
