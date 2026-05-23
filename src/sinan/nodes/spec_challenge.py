"""spec_challenge — 诘问 (Jiewen) reviews Requirement Pack.

Agent: 诘问 (Jiewen)
Layer: 需求层

Reads:
    state["requirement_pack"]  — from spec_expansion

Writes:
    state["spec_review"]       — critical review with challenge_score
    state["current_phase"]     — "SPEC_CHALLENGE"
    state["risk_register"]     — appends ambiguity risks
    state["artifact_versions"] — records spec_review version

Artifacts:
    spec_review.json  — review findings

Routes:
    → brief_debate  (linear)
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


def spec_challenge_node(state: HarnessBuilderState) -> dict:
    update_run_state(state["run_id"], "SPEC_CHALLENGE")
    append_progress_log(state["run_id"], "SPEC_CHALLENGE", "Starting spec review")

    client = get_llm_client()
    system = get_prompt("jiewen")
    rp_json = json.dumps(state.get("requirement_pack") or {}, indent=2, ensure_ascii=False)
    user = f"以下是 Requirement Pack，请进行批判性审查:\n\n{rp_json}"

    raw = client.generate(system, user)
    review = parse_and_validate_artifact(raw, "spec_review")

    write_json(state["run_id"], "spec_review.json", review)
    state["spec_review"] = review
    state["current_phase"] = "SPEC_CHALLENGE"
    state["artifact_versions"]["spec_review"] = "1.0"

    score = review.get("challenge_score", 0)
    flagged = [a["item"] for a in review.get("ambiguities", [])]
    state["risk_register"].extend([
        {"type": "ambiguity", "item": a["item"], "risk": a.get("risk_if_unaddressed", "")}
        for a in review.get("ambiguities", [])
    ])

    append_progress_log(state["run_id"], "SPEC_CHALLENGE", f"Review complete, score={score}")
    append_decision_log(state["run_id"], {
        "phase": "SPEC_CHALLENGE",
        "type": "challenge_gate",
        "content": f"Spec challenge score: {score}/10",
        "rationale": f"Identified {len(flagged)} ambiguities",
        "risks": flagged,
    })
    finalize_phase(state["run_id"])

    return state
