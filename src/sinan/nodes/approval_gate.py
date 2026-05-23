"""approval_gate — 守门 (Shoumen) evaluates architecture and routes based on risk_level.

Agent: 守门 (Shoumen)
Layer: 架构层

Reads:
    state["architecture_pack"]    — from zonggong_integrate
    state["architecture_review"] — from architecture_challenge
    state["gate_flags"]          — current gate flags

Writes:
    state["gate_flags"]["risk_level"]         — "low" | "high"
    state["gate_flags"]["needs_user_approval"] — bool
    state["gate_flags"]["shoumen_reasoning"]  — reasoning text
    state["gate_flags"]["key_concerns"]      — list of concerns
    state["gate_flags"]["checklist"]         — checklist result
    state["pending_interrupt"]  — set to "user_approval" if high risk
    state["current_phase"]      — "APPROVAL_GATE"

Artifacts:
    (none)

Routes:
    → final_spec       when risk_level == "low"
    → sinan_approval   when risk_level != "low"
"""
from __future__ import annotations
import json
from ..state import HarnessBuilderState
from ..llm import get_llm_client
from ..prompts import get_prompt
from ..artifacts import (
    update_run_state, append_progress_log, append_decision_log,
    finalize_phase,
)
from .spec_expansion import _parse_json


def approval_gate_node(state: HarnessBuilderState) -> dict:
    update_run_state(state["run_id"], "APPROVAL_GATE")
    append_progress_log(state["run_id"], "APPROVAL_GATE", "Shoumen evaluating architecture review")

    review = state.get("architecture_review") or {}
    arch = state.get("architecture_pack") or {}
    brief = state.get("user_brief_form") or {}

    client = get_llm_client()
    system = get_prompt("approval_gate")

    user = (
        f"【逆审（Nishen）审查结果】\n"
        f"challenge_score: {review.get('challenge_score', '?')}/10\n"
        f"recommendation: {review.get('recommendation', '?')}\n\n"
        f"over_engineering_flags（过度设计，可忽略）:\n"
        + "\n".join(f"  - {f}" for f in review.get("over_engineering_flags", []) or ["无"]) + "\n\n"
        f"handoff_gaps（交接缺口，严重）:\n"
        + "\n".join(f"  - {g}" for g in review.get("handoff_gaps", []) or ["无"]) + "\n\n"
        f"eval_gaps（评估缺口，严重）:\n"
        + "\n".join(f"  - {e}" for e in review.get("eval_gaps", []) or ["无"]) + "\n\n"
        f"failure_mode_omissions（未覆盖失败模式，严重）:\n"
        + "\n".join(f"  - {f}" for f in review.get("failure_mode_omissions", []) or ["无"]) + "\n\n"
        f"cost_complexity_concerns（复杂度问题）:\n"
        + "\n".join(f"  - {c}" for c in review.get("cost_complexity_concerns", []) or ["无"]) + "\n\n"
        f"【架构设计摘要】\n"
        f"阶段序列: {', '.join(arch.get('phase_sequence', []))}\n"
        f"审批闸门: {', '.join(arch.get('approval_gates', [])) or '无'}\n"
        f"失败恢复策略: {arch.get('failure_recovery', '未定义')}\n\n"
        f"【用户需求契约】\n"
        f"核心目标: {brief.get('primary_goal', '未定义')}\n\n"
        f"请评估以上信息。"
    )

    raw = client.generate(system, user)
    judgment = _parse_json(raw, "shoumen_judgment")

    risk_level = judgment.get("risk_level", "unknown")
    reasoning = judgment.get("reasoning", "")
    key_concerns = judgment.get("key_concerns", [])
    checklist = judgment.get("checklist", {})

    state["gate_flags"]["needs_user_approval"] = risk_level != "low"
    state["gate_flags"]["risk_level"] = risk_level
    state["gate_flags"]["shoumen_reasoning"] = reasoning
    state["gate_flags"]["key_concerns"] = key_concerns
    state["gate_flags"]["checklist"] = checklist
    state["gate_flags"]["flagged_risks"] = key_concerns
    state["pending_interrupt"] = "user_approval" if risk_level != "low" else None
    state["current_phase"] = "APPROVAL_GATE"

    append_progress_log(
        state["run_id"], "APPROVAL_GATE",
        f"Gate: risk_level={risk_level}, needs_approval={risk_level != 'low'}"
    )
    append_decision_log(state["run_id"], {
        "phase": "APPROVAL_GATE",
        "type": "gate_decision",
        "content": f"Shoumen evaluated — risk_level={risk_level}",
        "rationale": reasoning,
        "risk_level": risk_level,
        "key_concerns": key_concerns,
        "checklist": checklist,
        "challenge_score": review.get("challenge_score"),
        "nishen_recommendation": review.get("recommendation"),
    })
    finalize_phase(state["run_id"])
    return state
