"""subagent_review — 子代理 (Memory/Handoff/Eval) 评审 framework (四步辩论 Step 2)。

Agent: Memory + Handoff + Eval 子代理
Layer: 架构层

Reads:
    state["framework_design"]  — from framework_design
    state["user_brief_form"]   — from brief_compile

Writes:
    state["subagent_reviews"]  — {memory, handoff, eval} review reports
    state["subagent_outputs"]  — {memory, handoff, eval} detailed module designs
    state["current_phase"]      — "SUBAGENT_REVIEW"
    state["artifact_versions"]  — records subagent_reviews/outputs versions

Artifacts:
    subagent_reviews.json  (versioned)
    subagent_outputs.json  (versioned)

Routes:
    → framework_adjust  (linear)
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
from ..validation import parse_llm_json, parse_and_validate_artifact


def subagent_review_node(state: HarnessBuilderState) -> dict:
    update_run_state(state["run_id"], "SUBAGENT_REVIEW")
    append_progress_log(state["run_id"], "SUBAGENT_REVIEW", "Starting sub-agent reviews of framework")

    client = get_llm_client()
    brief = (
        load_state_or_file(state, "user_brief_form")
        or load_state_or_file(state, "requirement_pack")
        or {}
    )
    framework = load_state_or_file(state, "framework_design")

    brief_text = json.dumps(brief, indent=2, ensure_ascii=False)
    framework_text = json.dumps(framework, indent=2, ensure_ascii=False)

    # 子代理各自出详细设计 + 评审 framework
    memory_result = _call_subagent(client, brief_text, framework_text, "memory", "记忆模块设计师", "zonggong_memory")
    handoff_result = _call_subagent(client, brief_text, framework_text, "handoff", "交接协议设计师", "zonggong_handoff")
    eval_result = _call_subagent(client, brief_text, framework_text, "eval", "评估专家", "zonggong_eval")

    # 评审报告（用于反馈给 framework）
    memory_review = memory_result["review"]
    handoff_review = handoff_result["review"]
    eval_review = eval_result["review"]

    reviews = {
        "memory": memory_review,
        "handoff": handoff_review,
        "eval": eval_review,
    }

    subagent_outputs = {
        "memory": memory_result["design"],
        "handoff": handoff_result["design"],
        "eval": eval_result["design"],
    }

    write_json(state["run_id"], "subagent_reviews.json", reviews, versioned=True)
    write_json(state["run_id"], "subagent_outputs.json", subagent_outputs, versioned=True)

    state["subagent_reviews"] = reviews
    state["subagent_outputs"] = subagent_outputs
    state["current_phase"] = "SUBAGENT_REVIEW"
    state["artifact_versions"]["subagent_reviews"] = "1.0"
    state["artifact_versions"]["subagent_outputs"] = "1.0"

    total_incompat = sum(len(r.get("incompatibilities", [])) for r in reviews.values())
    total_missing = sum(len(r.get("missing_elements", [])) for r in reviews.values())
    total_endorsed = sum(len(r.get("endorsed_elements", [])) for r in reviews.values())

    append_progress_log(
        state["run_id"], "SUBAGENT_REVIEW",
        f"Sub-agent reviews complete: {total_incompat} incompatibilities, "
        f"{total_missing} missing elements, {total_endorsed} endorsed elements"
    )
    append_decision_log(state["run_id"], {
        "phase": "SUBAGENT_REVIEW",
        "type": "review_complete",
        "content": f"3 sub-agents reviewed framework",
        "rationale": f"memory/handoff/eval each produced design + review",
        "incompatibilities": total_incompat,
        "missing_elements": total_missing,
    })
    finalize_phase(state["run_id"])

    return state


def _call_subagent(client, brief_text: str, framework_text: str, name: str, role: str, prompt_key: str) -> dict:
    """调用子代理：先生成详细设计，再评审 framework。"""
    # Step 1: 子代理出详细设计
    system = get_prompt(prompt_key)
    design_user = (
        f"User Brief Form:\n{brief_text}\n\n"
        f"Framework Design:\n{framework_text}\n\n"
        f"请基于以上信息，设计你的模块。"
    )
    raw_design = client.generate(system, design_user)
    # detailed design shapes differ per sub-agent (memory/handoff/eval),
    # so we only parse; schema is enforced on the wrapped subagent_outputs.
    design = parse_llm_json(raw_design, f"zonggong_{name}")

    # Step 2: 子代理评审 framework
    review_prompt = get_prompt("subagent_review")
    review_system = review_prompt.format(agent_role=role, agent_name=name)
    review_user = (
        f"User Brief Form:\n{brief_text}\n\n"
        f"Framework Design:\n{framework_text}\n\n"
        f"Your Module Design (for reference):\n{json.dumps(design, indent=2, ensure_ascii=False)}\n\n"
        f"请以 {name} 专家的视角，评审上述 framework 设计。"
    )
    raw_review = client.generate(review_system, review_user)
    review = parse_and_validate_artifact(raw_review, "subagent_review_item")

    return {"design": design, "review": review}
