"""zonggong_integrate — 总工整合所有子模块输出为完整架构包 (四步辩论 Step 4)。

Agent: 总工 (Zonggong)
Layer: 架构层

Reads:
    state["framework_design"]       — adjusted framework
    state["subagent_reviews"]       — sub-agent review reports
    state["framework_adjustments"] — adjustment records
    state["arch_revision_brief"]   — revision context (if revision loop)

Writes:
    state["architecture_pack"]   — complete architecture package
    state["current_phase"]        — "ZONGGONG_INTEGRATE"
    state["artifact_versions"]    — records architecture_pack version

Artifacts:
    architecture_pack.json  (versioned)

Routes:
    → architecture_challenge  (linear)
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


def zonggong_integrate_node(state: HarnessBuilderState) -> dict:
    update_run_state(state["run_id"], "ZONGGONG_INTEGRATE")
    append_progress_log(state["run_id"], "ZONGGONG_INTEGRATE", "Zonggong integrating all sub-agent outputs")

    client = get_llm_client()
    brief = state.get("user_brief_form") or state.get("requirement_pack") or {}
    brief_text = json.dumps(brief, indent=2, ensure_ascii=False)

    framework = state.get("framework_design") or {}
    subagent_outputs = _load_subagent_outputs(state)

    revision_context = ""
    revision_brief = state.get("arch_revision_brief")
    if revision_brief:
        revision_context = (
            f"\n\n【本轮修复重点】\n"
            + "\n".join(
                f"- 修复 {i.get('issue', '')}: {i.get('fix_instruction', '')}"
                for i in revision_brief.get("specific_issues", [])
            )
        )

    system = get_prompt("zonggong")
    user = f"""User Brief Form:
{brief_text}
{revision_context}

【调整后的 Framework】
{json.dumps(framework, indent=2, ensure_ascii=False)}

【子模块详细设计】
Memory Module:
{json.dumps(subagent_outputs.get("memory", {}), indent=2, ensure_ascii=False)}

Handoff Protocol:
{json.dumps(subagent_outputs.get("handoff", {}), indent=2, ensure_ascii=False)}

Eval Placements:
{json.dumps(subagent_outputs.get("eval", {}), indent=2, ensure_ascii=False)}

请整合以上所有输出，生成完整的 Harness 架构包。
"""

    raw = client.generate(system, user)
    arch = _parse_json(raw, "architecture_pack")

    # 加入完整上下文便于追溯
    arch["subagent_outputs"] = subagent_outputs
    arch["framework_design"] = framework
    arch["design_evolution"] = {
        "initial_framework": state.get("framework_design"),
        "subagent_reviews": state.get("subagent_reviews"),
        "framework_adjustments": state.get("framework_adjustments"),
    }

    # Versioned write
    revision_round = revision_brief.get("revision_round", "?") if revision_brief else None
    version_note = f"Archived before round {revision_round} revision" if revision_round else ""
    write_json(state["run_id"], "architecture_pack.json", arch, versioned=True, version_note=version_note)

    state["architecture_pack"] = arch
    state["current_phase"] = "ZONGGONG_INTEGRATE"
    state["artifact_versions"]["architecture_pack"] = "1.0"

    append_progress_log(
        state["run_id"], "ZONGGONG_INTEGRATE",
        f"Architecture Pack integrated with {len(arch.get('phase_sequence', []))} phases"
    )
    append_decision_log(state["run_id"], {
        "phase": "ZONGGONG_INTEGRATE",
        "type": "artifact_generated",
        "content": "Generated Architecture Pack via 4-step sub-agent collaboration",
        "sub_agents": ["framework", "memory", "handoff", "eval"],
        "rationale": "Zonggong integrated outputs after framework debate + adjustment",
    })
    finalize_phase(state["run_id"])

    return state


def _load_subagent_outputs(state: HarnessBuilderState) -> dict:
    """从 state 或 artifact 文件加载子代理输出。"""
    # 优先从 state 加载（如果 subagent_review 节点已经执行）
    outputs = state.get("subagent_outputs", {})
    if outputs:
        return outputs

    # 否则从 artifact 文件加载
    from ..artifacts import get_current_artifact
    run_id = state["run_id"]
    saved = get_current_artifact(run_id, "subagent_outputs")
    return saved or {}
