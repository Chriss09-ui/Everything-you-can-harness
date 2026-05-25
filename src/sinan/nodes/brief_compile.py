"""brief_compile — 契约 (Qiyue) merges supplements into User Brief Form.

Agent: 契约 (Qiyue)
Layer: 需求层 (出口)

Reads:
    state["requirement_pack"]    — from spec_expansion
    state["brief_debate"]        — from brief_debate
    state["user_brief_answers"]  — from sinan_debrief

Writes:
    state["user_brief_form"]    — final requirement contract
    state["current_phase"]       — "BRIEF_COMPILE"
    state["artifact_versions"]   — records user_brief_form version

Artifacts:
    user_brief_form.json  — 需求契约 (需求层→架构层交接物)

Routes:
    → framework_design  (linear, 进入架构层)
"""
from __future__ import annotations
import json
from ..state import HarnessBuilderState
from ..llm import get_llm_client
from ..prompts import get_prompt
from ..artifacts import (
    write_json, update_run_state, append_progress_log,
    append_decision_log, finalize_phase,
)
from ..validation import parse_and_validate_artifact


_REQUIREMENT_CONTRACT_FIELDS = (
    "use_case_summary",
    "primary_goal",
    "stakeholders",
    "scope_inclusions",
    "scope_exclusions",
    "success_criteria",
    "assumptions",
    "known_constraints",
    "persona_qualities",
    "risk_tolerance",
)


def brief_compile_node(state: HarnessBuilderState) -> dict:
    update_run_state(state["run_id"], "BRIEF_COMPILE")
    append_progress_log(state["run_id"], "BRIEF_COMPILE", "Compiling user brief form")

    client = get_llm_client()
    system = get_prompt("qiyue")

    rp = state.get("requirement_pack") or {}
    debate = state.get("brief_debate") or {}
    answers = state.get("user_brief_answers") or []
    questions = debate.get("user_questions", [])

    # 合并问题和答案
    qa_text = "（无问题）"
    if questions and answers:
        pairs = []
        for answer in answers:
            question = answer.get("question", "")
            response = answer.get("answer")
            if response is not None:
                pairs.append(f"Q: {question}\nA: {response}")
            else:
                pairs.append(f"Q: {question}\nA: [用户跳过]")
        qa_text = "\n".join(pairs)
    elif questions:
        qa_text = "\n".join(f"Q: {question}\nA: [未记录]" for question in questions)

    aligned = "\n".join(f"- {p}" for p in debate.get("aligned_points", [])) or "（无）"
    remaining = "\n".join(f"- {d}" for d in debate.get("remaining_disagreements", [])) or "（无）"

    user = (
        f"Requirement Pack:\n{json.dumps(rp, indent=2, ensure_ascii=False)}\n\n"
        f"【拓谱-诘问辩论结论】\n"
        f"已对齐:\n{aligned}\n\n"
        f"仍存在分歧:\n{remaining}\n\n"
        f"【用户对辩论问题的回答】\n{qa_text}\n\n"
        f"请合并以上所有信息，生成最终 User Brief Form。"
    )

    raw = client.generate(system, user)
    brief = parse_and_validate_artifact(raw, "user_brief_form")
    brief = _enrich_user_brief_form(brief, rp)

    write_json(state["run_id"], "user_brief_form.json", brief)
    state["user_brief_form"] = brief
    state["current_phase"] = "BRIEF_COMPILE"
    state["artifact_versions"]["user_brief_form"] = "1.0"

    append_progress_log(state["run_id"], "BRIEF_COMPILE", "User Brief Form compiled")
    append_decision_log(state["run_id"], {
        "phase": "BRIEF_COMPILE",
        "type": "artifact_generated",
        "content": "Generated User Brief Form",
        "rationale": "Merged requirement pack with user clarifications",
    })
    finalize_phase(state["run_id"])

    return state


def _enrich_user_brief_form(brief: dict, requirement_pack: dict) -> dict:
    """Make the requirement-layer exit artifact self-contained."""
    enriched = dict(brief)
    for field in _REQUIREMENT_CONTRACT_FIELDS:
        if field not in enriched and field in requirement_pack:
            enriched[field] = requirement_pack[field]
    return enriched
