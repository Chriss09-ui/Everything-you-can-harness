"""architecture_challenge — 逆审 (Nishen) reviews the architecture.

Agent: 逆审 (Nishen)
Layer: 架构层

Reads:
    state["architecture_pack"]   — from zonggong_integrate
    state["user_brief_form"]    — from brief_compile

Writes:
    state["architecture_review"] — critical review with challenge_score
    state["current_phase"]        — "ARCHITECTURE_CHALLENGE"
    state["risk_register"]        — appends arch risks onto the existing list
                                     (no reducer; node builds the full next
                                     list). On revision loops, drops any
                                     prior ``type=arch_risk`` entries first
                                     so fixed risks don't accumulate across
                                     rounds.
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
    append_decision_log, finalize_phase, load_state_or_file,
)
from ..validation import parse_and_validate_artifact


def architecture_challenge_node(state: HarnessBuilderState) -> dict:
    update_run_state(state["run_id"], "ARCHITECTURE_CHALLENGE")
    append_progress_log(state["run_id"], "ARCHITECTURE_CHALLENGE", "Starting architecture review")

    client = get_llm_client()
    system = get_prompt("nishen")

    arch = load_state_or_file(state, "architecture_pack")
    brief = load_state_or_file(state, "user_brief_form")

    # ``zonggong_integrate`` embeds ``subagent_outputs``, ``framework_design``
    # and ``design_evolution`` into the architecture_pack for traceability
    # — but those ~3x the token cost when fed verbatim to the reviewer LLM
    # and are not what the reviewer is supposed to be challenging. Strip the
    # embedded trace fields before composing the Nishen prompt; the on-disk
    # ``architecture_pack.json`` and the state value are unchanged.
    arch_for_prompt = {
        k: v for k, v in arch.items()
        if k not in ("subagent_outputs", "framework_design", "design_evolution")
    }

    user = (
        f"Architecture Pack:\n{json.dumps(arch_for_prompt, indent=2, ensure_ascii=False)}\n\n"
        f"User Brief Form:\n{json.dumps(brief, indent=2, ensure_ascii=False)}\n\n"
        f"请批判性审查以上架构设计，找出缺陷。"
    )

    raw = client.generate(system, user)
    review = parse_and_validate_artifact(raw, "architecture_review")

    # versioned=True: architecture_challenge reruns every revision loop round
    # (after arch_revise → framework_design rebuilds the architecture_pack that
    # this node reviews). Without versioned write, each round silently wipes
    # the prior review, losing the audit trail of how the architect's thinking
    # evolved across revisions.
    write_json(state["run_id"], "architecture_review.json", review, versioned=True)

    score = review.get("challenge_score", 0)
    new_risks = [
        {"type": "arch_risk", "item": r}
        for r in review.get("over_engineering_flags", [])
    ] + [
        {"type": "arch_risk", "item": r}
        for r in review.get("failure_mode_omissions", [])
    ]

    append_progress_log(state["run_id"], "ARCHITECTURE_CHALLENGE", f"Review complete, score={score}")
    append_decision_log(state["run_id"], {
        "phase": "ARCHITECTURE_CHALLENGE",
        "type": "challenge_gate",
        "content": f"Architecture challenge score: {score}/10",
        "rationale": f"Identified {len(review.get('over_engineering_flags', []))} over-engineering flags",
        "risks": review.get("over_engineering_flags", []),
    })
    finalize_phase(state["run_id"])

    # Append this round's arch risks to the running register.
    # ``risk_register`` is plain list now (no reducer, see state.py).
    #
    # Revision-loop hygiene: arch_challenge reruns every reject round, and
    # each round produces a fresh list of risks against the newest
    # architecture_pack. If we just concat onto the prior register, risks
    # that the architect actually fixed in this round stay in the register
    # as stale entries — and sinan_approval / harness_design_draft will
    # surface them to the user as if they still applied. So we drop any
    # prior ``arch_risk`` entries (this node's tag) before appending the
    # new ones. Other risk sources (spec_challenge's ``ambiguity``) are
    # untouched.
    prior = [r for r in state.get("risk_register", []) if r.get("type") != "arch_risk"]
    state["architecture_review"] = review
    state["current_phase"] = "ARCHITECTURE_CHALLENGE"
    state["artifact_versions"] = {**state.get("artifact_versions", {}),
                                  "architecture_review": "1.0"}
    state["risk_register"] = prior + new_risks
    return state
