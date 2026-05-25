"""framework_design — 总工框架设计师出初始方案 (四步辩论 Step 1)。

Agent: 总工框架设计师
Layer: 架构层

Reads:
    state["user_brief_form"]       — from brief_compile
    state["arch_revision_brief"]   — from arch_revise (if revision loop)

Writes:
    state["framework_design"]   — initial framework dict
    state["current_phase"]       — "FRAMEWORK_DESIGN"
    state["artifact_versions"]   — records framework_design version

Artifacts:
    framework_design.json  (versioned)

Routes:
    → subagent_review  (linear)
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
from .spec_expansion import _parse_json


def framework_design_node(state: HarnessBuilderState) -> dict:
    update_run_state(state["run_id"], "FRAMEWORK_DESIGN")
    append_progress_log(state["run_id"], "FRAMEWORK_DESIGN", "Starting framework design (Round 1)")

    client = get_llm_client()
    brief = (
        load_state_or_file(state, "user_brief_form")
        or load_state_or_file(state, "requirement_pack")
        or {}
    )
    brief_text = json.dumps(brief, indent=2, ensure_ascii=False)

    revision_context = _build_revision_context(state)

    system = get_prompt("zonggong_framework")
    user = f"User Brief Form:\n{brief_text}\n{revision_context}\n\n【第一轮】请设计 harness 的整体框架结构。只输出初始方案即可。"

    raw = client.generate(system, user)
    framework = _parse_json(raw, "framework_design")

    write_json(state["run_id"], "framework_design.json", framework, versioned=True)
    state["framework_design"] = framework
    state["current_phase"] = "FRAMEWORK_DESIGN"
    state["artifact_versions"]["framework_design"] = "1.0"

    append_progress_log(
        state["run_id"], "FRAMEWORK_DESIGN",
        f"Initial framework generated: {len(framework.get('nodes', []))} nodes, "
        f"{len(framework.get('phase_sequence', []))} phases"
    )
    append_decision_log(state["run_id"], {
        "phase": "FRAMEWORK_DESIGN",
        "type": "artifact_generated",
        "content": "Round 1: Initial framework design generated",
        "rationale": "Framework agent produced initial architecture based on user brief",
    })
    finalize_phase(state["run_id"])

    return state


def _build_revision_context(state: HarnessBuilderState) -> str:
    revision_brief = state.get("arch_revision_brief")
    if not revision_brief:
        return ""

    revision_round = revision_brief.get("revision_round", "?")
    preserve = revision_brief.get("preserve_points", [])
    context = (
        f"\n\n【第 {revision_round} 轮修复指令 — 请仔细阅读并针对性修复】\n"
        f"修复概述: {revision_brief.get('revision_summary', '')}\n\n"
        f"需要修复的具体问题:\n"
    )
    for i in revision_brief.get("specific_issues", []):
        context += f"  - 问题: {i.get('issue', '')}\n"
        context += f"    上版体现: {i.get('in_previous_design', '')}\n"
        context += f"    修复指令: {i.get('fix_instruction', '')}\n"

    context += f"\n保持不变的部分:\n"
    if preserve:
        for p in preserve:
            context += f"  - {p}\n"
    else:
        context += "  （无）\n"

    return context
