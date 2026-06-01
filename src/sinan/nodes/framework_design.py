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
from ..validation import parse_and_validate_artifact, validate_artifact


def framework_design_node(state: HarnessBuilderState) -> dict:
    update_run_state(state["run_id"], "FRAMEWORK_DESIGN")
    append_progress_log(state["run_id"], "FRAMEWORK_DESIGN",
        "Starting framework design")

    client = get_llm_client()
    brief = load_state_or_file(state, "user_brief_form")
    # user_brief_form is the only valid requirement→architecture handoff.
    # brief_compile enriches it with requirement_pack fields, so downstream
    # nodes can read either set of keys off this single artifact.
    if not brief:
        raise RuntimeError(
            "framework_design requires user_brief_form. "
            "Run the requirement layer first, or pass --from-brief <run_id> "
            "with a runs/<run_id>/user_brief_form.json on disk."
        )
    validate_artifact(brief, "user_brief_form")
    brief_text = json.dumps(brief, indent=2, ensure_ascii=False)

    revision_context = _build_revision_context(state)
    is_revision = bool(revision_context)
    # Round-1 prompt: ask for an initial framework from scratch.
    # Revision-round prompt: drop the misleading "第一轮" framing — the
    # revision_context block above already says "第 N 轮修复指令", and the
    # previous „【第一轮】请设计…‟ suffix confused the LLM into re-generating
    # from scratch instead of editing the prior design per the revision brief.
    if is_revision:
        round_suffix = "请按上述修复指令调整 framework，输出调整后的完整 framework。"
    else:
        round_suffix = "【第一轮】请设计 harness 的整体框架结构。只输出初始方案即可。"

    system = get_prompt("zonggong_framework")
    user = f"User Brief Form:\n{brief_text}\n{revision_context}\n\n{round_suffix}"

    raw = client.generate(system, user)
    framework = parse_and_validate_artifact(raw, "framework_design")

    write_json(state["run_id"], "framework_design.json", framework, versioned=True)
    state["framework_design"] = framework
    state["current_phase"] = "FRAMEWORK_DESIGN"
    state["artifact_versions"]["framework_design"] = "1.0"

    append_progress_log(
        state["run_id"], "FRAMEWORK_DESIGN",
        f"{'Revision' if is_revision else 'Initial'} framework generated: "
        f"{len(framework.get('nodes', []))} nodes, "
        f"{len(framework.get('phase_sequence', []))} phases"
    )
    append_decision_log(state["run_id"], {
        "phase": "FRAMEWORK_DESIGN",
        "type": "artifact_generated",
        "content": f"{'Revision round' if is_revision else 'Round 1'}: "
                   f"Framework design generated",
        "rationale": "Framework agent produced "
                     f"{'revised' if is_revision else 'initial'} "
                     "architecture based on user brief",
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
