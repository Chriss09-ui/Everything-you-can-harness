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
from concurrent.futures import ThreadPoolExecutor, as_completed
from ..state import HarnessBuilderState
from ..llm import get_llm_client
from ..prompts import get_prompt
from ..artifacts import (
    write_json, update_run_state, append_progress_log,
    append_decision_log, finalize_phase, load_state_or_file,
)
from ..validation import parse_llm_json, parse_and_validate_artifact


# Three independent sub-agents with no shared mutable state — natural
# candidates for a fan-out. Capped at 3 workers because that's exactly
# how many sub-agents exist; adding more would only waste scheduler slots.
_MAX_PARALLEL_WORKERS = 3

_SUBAGENT_CALLS = [
    ("memory",  "记忆模块设计师",   "zonggong_memory"),
    ("handoff", "交接协议设计师", "zonggong_handoff"),
    ("eval",    "评估专家",       "zonggong_eval"),
]


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

    # 子代理并发调用：每个子代理内部 2 次 LLM (design + review) 串行，但
    # 三个子代理之间互不依赖，可以并发。串行下总耗时 ~6×LLM 延迟，并发下
    # 降到 ~2×LLM 延迟（最慢那个子代理的耗时）。
    results_by_name: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=_MAX_PARALLEL_WORKERS) as pool:
        future_to_name = {
            pool.submit(
                _call_subagent, client, brief_text, framework_text,
                name, role, prompt_key,
            ): name
            for name, role, prompt_key in _SUBAGENT_CALLS
        }
        for future in as_completed(future_to_name):
            name = future_to_name[future]
            try:
                results_by_name[name] = future.result()
            except Exception as exc:
                raise RuntimeError(
                    f"subagent '{name}' failed during review"
                ) from exc

    # 顺序保持稳定（memory / handoff / eval），避免每次 run 因并发完成顺序
    # 不同而产出 JSON diff 抖动。
    reviews = {name: results_by_name[name]["review"] for name, _, _ in _SUBAGENT_CALLS}
    subagent_outputs = {name: results_by_name[name]["design"] for name, _, _ in _SUBAGENT_CALLS}

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
        f"Sub-agent reviews complete (parallel): {total_incompat} incompatibilities, "
        f"{total_missing} missing elements, {total_endorsed} endorsed elements"
    )
    append_decision_log(state["run_id"], {
        "phase": "SUBAGENT_REVIEW",
        "type": "review_complete",
        "content": f"3 sub-agents reviewed framework in parallel",
        "rationale": f"memory/handoff/eval each produced design + review concurrently",
        "incompatibilities": total_incompat,
        "missing_elements": total_missing,
    })
    finalize_phase(state["run_id"])

    return state


def _call_subagent(client, brief_text: str, framework_text: str, name: str, role: str, prompt_key: str) -> dict:
    """调用子代理：先生成详细设计，再评审 framework。

    在并发上下文下执行（每个子代理独立线程），所以不能依赖 / 写入任何
    共享可变状态——只通过返回值传出结果。
    """
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
