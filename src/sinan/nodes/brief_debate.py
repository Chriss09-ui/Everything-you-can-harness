"""brief_debate — 拓谱与诘问辩论对齐，输出共同问题清单供用户填写。

Agent: 拓谱 + 诘问 (辩论)
Layer: 需求层

Reads:
    state["requirement_pack"]  — from spec_expansion
    state["spec_review"]      — from spec_challenge

Writes:
    state["brief_debate"]     — debate result with aligned_points, remaining_disagreements, user_questions
    state["current_phase"]     — "BRIEF_DEBATE"
    state["artifact_versions"] — records brief_debate version

Artifacts:
    brief_debate.json  — debate outcome

Routes:
    → sinan_debrief  (linear)
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


def brief_debate_node(state: HarnessBuilderState) -> dict:
    update_run_state(state["run_id"], "BRIEF_DEBATE")
    append_progress_log(state["run_id"], "BRIEF_DEBATE", "Starting Tuopu-Jiewen debate")

    client = get_llm_client()
    system = get_prompt("brief_debate")

    rp = load_state_or_file(state, "requirement_pack")
    review = load_state_or_file(state, "spec_review")

    user = (
        f"【拓谱的需求扩展】\n{json.dumps(rp, indent=2, ensure_ascii=False)}\n\n"
        f"【诘问的审查发现】\n{json.dumps(review, indent=2, ensure_ascii=False)}\n\n"
        "请主持辩论并输出结果。"
    )

    raw = client.generate(system, user)
    debate_result = parse_and_validate_artifact(raw, "brief_debate")

    write_json(state["run_id"], "brief_debate.json", debate_result)
    state["brief_debate"] = debate_result
    state["current_phase"] = "BRIEF_DEBATE"
    state["artifact_versions"]["brief_debate"] = "1.0"

    user_questions = debate_result.get("user_questions", [])
    aligned_points = debate_result.get("aligned_points", [])
    remaining = debate_result.get("remaining_disagreements", [])

    append_progress_log(
        state["run_id"], "BRIEF_DEBATE",
        f"Debate complete: {len(aligned_points)} aligned, "
        f"{len(remaining)} disagreements, {len(user_questions)} user questions"
    )
    append_decision_log(state["run_id"], {
        "phase": "BRIEF_DEBATE",
        "type": "debate",
        "content": f"Tuopu-Jiewen debate: {len(aligned_points)} aligned, {len(remaining)} disagreements",
        "rationale": "辩论必须在进入架构设计前完成，确保需求共识",
        "risks": remaining,
    })
    finalize_phase(state["run_id"])

    return state
