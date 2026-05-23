"""architecture_challenge — 逆审 (Nishen) reviews the architecture.

Agent: 逆审 (Nishen)
Layer: 架构层

Reads:
    state["architecture_pack"]   — from zonggong_integrate
    state["user_brief_form"]    — from brief_compile

Writes:
    state["architecture_review"] — critical review with challenge_score
    state["current_phase"]        — "ARCHITECTURE_CHALLENGE"
    state["risk_register"]        — appends arch risks
    state["artifact_versions"]    — records architecture_review version

Artifacts:
    architecture_review.json

Routes:
    → approval_gate  (linear)
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
from .spec_expansion import _parse_json


def architecture_challenge_node(state: HarnessBuilderState) -> dict:
    update_run_state(state["run_id"], "ARCHITECTURE_CHALLENGE")
    append_progress_log(state["run_id"], "ARCHITECTURE_CHALLENGE", "Starting architecture review")

    client = get_llm_client()
    system = get_prompt("nishen")

    arch = state.get("architecture_pack") or {}
    brief = state.get("user_brief_form") or {}

    user = (
        f"Architecture Pack:\n{json.dumps(arch, indent=2, ensure_ascii=False)}\n\n"
        f"User Brief Form:\n{json.dumps(brief, indent=2, ensure_ascii=False)}\n\n"
        f"请批判性审查以上架构设计，找出缺陷。"
    )

    raw = client.generate(system, user)
    review = _parse_json(raw, "architecture_review")

    write_json(state["run_id"], "architecture_review.json", review)
    state["architecture_review"] = review
    state["current_phase"] = "ARCHITECTURE_CHALLENGE"
    state["artifact_versions"]["architecture_review"] = "1.0"

    score = review.get("challenge_score", 0)
    state["risk_register"].extend([
        {"type": "arch_risk", "item": r}
        for r in review.get("over_engineering_flags", [])
    ])
    state["risk_register"].extend([
        {"type": "arch_risk", "item": r}
        for r in review.get("failure_mode_omissions", [])
    ])

    append_progress_log(state["run_id"], "ARCHITECTURE_CHALLENGE", f"Review complete, score={score}")
    append_decision_log(state["run_id"], {
        "phase": "ARCHITECTURE_CHALLENGE",
        "type": "challenge_gate",
        "content": f"Architecture challenge score: {score}/10",
        "rationale": f"Identified {len(review.get('over_engineering_flags', []))} over-engineering flags",
        "risks": review.get("over_engineering_flags", []),
    })
    finalize_phase(state["run_id"])

    return state
