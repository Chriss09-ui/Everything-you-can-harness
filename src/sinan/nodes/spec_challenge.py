"""spec_challenge — 诘问 (Jiewen) reviews Requirement Pack.

Agent: 诘问 (Jiewen)
Layer: 需求层

Reads:
    state["requirement_pack"]  — from spec_expansion

Writes:
    state["spec_review"]       — critical review with challenge_score
    state["current_phase"]     — "SPEC_CHALLENGE"
    state["risk_register"]     — appends ambiguity risks onto the existing
                                  list (no reducer; node builds the full next
                                  list)
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
from ..node_roles import lookup as _node_role
from ..prompts import get_prompt
from ..artifacts import (
    write_json, update_run_state, append_progress_log,
    append_decision_log, finalize_phase, load_state_or_file,
)
from ..validation import parse_and_validate_artifact


def spec_challenge_node(state: HarnessBuilderState) -> dict:
    update_run_state(state["run_id"], "SPEC_CHALLENGE")
    append_progress_log(state["run_id"], "SPEC_CHALLENGE", "Starting spec review")

    client = get_llm_client()
    system = get_prompt("jiewen")
    rp = load_state_or_file(state, "requirement_pack")
    rp_json = json.dumps(rp, indent=2, ensure_ascii=False)
    user = f"以下是 Requirement Pack，请进行批判性审查:\n\n{rp_json}"

    raw = client.generate(
        system, user,
        run_id=state["run_id"],
        agent_role=f'{_node_role("spec_challenge")["role"]}|{_node_role("spec_challenge")["layer"]}|spec_challenge',
    )
    review = parse_and_validate_artifact(raw, "spec_review")

    write_json(state["run_id"], "spec_review.json", review)

    score = review.get("challenge_score", 0)
    ambiguities = review.get("ambiguities", []) or []
    # Tolerate malformed entries: top-level schema doesn't enforce inner shape,
    # so an LLM may produce an ambiguity dict without the "item" field.
    flagged = [a.get("item", "") for a in ambiguities if isinstance(a, dict)]
    new_risks = [
        {
            "type": "ambiguity",
            "item": a.get("item", ""),
            "risk": a.get("risk_if_unaddressed", ""),
        }
        for a in ambiguities if isinstance(a, dict)
    ]

    append_progress_log(state["run_id"], "SPEC_CHALLENGE", f"Review complete, score={score}")
    append_decision_log(state["run_id"], {
        "phase": "SPEC_CHALLENGE",
        "type": "challenge_gate",
        "content": f"Spec challenge score: {score}/10",
        "rationale": f"Identified {len(flagged)} ambiguities",
        "risks": flagged,
    })
    finalize_phase(state["run_id"])

    # Append this node's new risks to the running register. ``risk_register``
    # used to be a reducer-managed field where returning only the new entries
    # would concat them onto the running list; the reducer has been removed
    # (see state.py for why), so the node now builds the full next-state list
    # explicitly — matching the rest of the codebase's ``mutate + return
    # state`` convention.
    state["spec_review"] = review
    state["current_phase"] = "SPEC_CHALLENGE"
    state["artifact_versions"] = {**state.get("artifact_versions", {}),
                                  "spec_review": "1.0"}
    state["risk_register"] = state.get("risk_register", []) + new_risks
    return state
