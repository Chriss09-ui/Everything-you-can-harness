"""spec_expansion — 拓谱 (Tuopu) generates Requirement Pack.

Agent: 拓谱 (Tuopu)
Layer: 需求层

Reads:
    state["user_raw_input"]  — raw user input

Writes:
    state["requirement_pack"]  — expanded requirement pack dict
    state["current_phase"]     — "SPEC_EXPANSION"
    state["artifact_versions"]  — records requirement_pack version

Artifacts:
    requirement_pack.json  — structured requirements

Routes:
    → spec_challenge  (linear)
"""
from __future__ import annotations
from ..state import HarnessBuilderState
from ..llm import get_llm_client
from ..node_roles import lookup as _node_role
from ..prompts import get_prompt
from ..artifacts import (
    write_json, update_run_state, append_progress_log,
    append_decision_log, finalize_phase,
)
from ..validation import parse_and_validate_artifact


def spec_expansion_node(state: HarnessBuilderState) -> dict:
    raw_input = state.get("user_raw_input", "")
    if not raw_input:
        raise RuntimeError(
            "spec_expansion requires non-empty user_raw_input. "
            "Run intake_node first, or check CLI entry — empty input should "
            "be rejected at the boundary."
        )

    update_run_state(state["run_id"], "SPEC_EXPANSION", started_at=state["started_at"])
    append_progress_log(state["run_id"], "SPEC_EXPANSION", "Starting requirement expansion")

    client = get_llm_client()
    system = get_prompt("tuopu")
    user = f"用户原始输入如下。请生成结构化 Requirement Pack:\n\n{raw_input}"

    raw = client.generate(
        system, user,
        run_id=state["run_id"],
        agent_role=f'{_node_role("spec_expansion")["role"]}|{_node_role("spec_expansion")["layer"]}|spec_expansion',
    )
    rp = parse_and_validate_artifact(raw, "requirement_pack")

    write_json(state["run_id"], "requirement_pack.json", rp)
    state["requirement_pack"] = rp
    state["current_phase"] = "SPEC_EXPANSION"
    state["artifact_versions"]["requirement_pack"] = "1.0"

    append_progress_log(state["run_id"], "SPEC_EXPANSION", "Requirement Pack generated")
    append_decision_log(state["run_id"], {
        "phase": "SPEC_EXPANSION",
        "type": "artifact_generated",
        "content": "Generated Requirement Pack",
        "rationale": "Used Tuopu (Spec Expander) LLM agent",
    })
    finalize_phase(state["run_id"])

    return state
