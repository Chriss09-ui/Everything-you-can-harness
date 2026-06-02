"""zonggong_integrate — 总工整合所有子模块输出为完整架构包 (四步辩论 Step 4)。

Agent: 总工 (Zonggong)
Layer: 架构层

Reads (全部经 ``load_state_or_file``，state 优先 + 磁盘 fallback):
    state["framework_design"]       — adjusted framework
    state["subagent_outputs"]       — memory/handoff/eval 详细设计
    state["subagent_reviews"]       — 子 agent 评审 (嵌入追溯)
    state["framework_adjustments"]  — 调整记录 (嵌入追溯)
    state["arch_revision_brief"]    — 修订上下文 (revision loop 时)
    state["user_brief_form"] / state["requirement_pack"]  — 需求契约

Writes:
    state["architecture_pack"]   — 完整架构包
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
    append_decision_log, finalize_phase, load_state_or_file,
    get_artifact_versions, get_run_dir,
)
from ..validation import parse_and_validate_artifact


def zonggong_integrate_node(state: HarnessBuilderState) -> dict:
    update_run_state(state["run_id"], "ZONGGONG_INTEGRATE")
    append_progress_log(state["run_id"], "ZONGGONG_INTEGRATE", "Zonggong integrating all sub-agent outputs")

    client = get_llm_client()
    # load_state_or_file makes this node re-runnable via --from-brief /
    # --from-design: even if state is empty, we still pick up the disk
    # artifacts from prior nodes.
    brief = (
        load_state_or_file(state, "user_brief_form")
        or load_state_or_file(state, "requirement_pack")
        or {}
    )
    brief_text = json.dumps(brief, indent=2, ensure_ascii=False)

    framework = load_state_or_file(state, "framework_design") or {}
    subagent_outputs = _load_subagent_outputs(state)

    revision_context = ""
    revision_brief = load_state_or_file(state, "arch_revision_brief", default=None)
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
    arch = parse_and_validate_artifact(raw, "architecture_pack")

    # 注入完整上下文便于追溯。注意 design_trace.initial_framework 必须
    # 是真正的 Round-1 框架——framework_adjust 已经把 state["framework_design"]
    # 覆盖为 adjusted 版本，所以不能直接读 state。Round-1 框架在磁盘上
    # 由 framework_adjust 的 versioned-write 自动归档为 framework_design_v1.json。
    #
    # NOTE: this field used to be called ``design_evolution``, but
    # ``harness_design_draft`` carries a different field with the same name
    # whose shape is a *list* (preserved_elements). Renamed to ``design_trace``
    # here so the two artifacts don't share a key with divergent shapes.
    arch["subagent_outputs"] = subagent_outputs
    arch["framework_design"] = framework
    arch["design_trace"] = {
        "initial_framework": _load_initial_framework(state["run_id"], framework),
        "subagent_reviews": load_state_or_file(state, "subagent_reviews"),
        "framework_adjustments": load_state_or_file(
            state, "framework_adjustments", filename="framework_adjustment.json",
        ),
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


def _load_initial_framework(run_id: str, fallback: dict) -> dict:
    """Return the Round-1 framework (archived as framework_design_v1.json).

    If the archive can't be located (e.g. an older run that pre-dates the
    versioned-write fix, or an inconsistent registry), fall back to the
    currently-loaded framework dict so the trace is still populated —
    degraded traceability is preferable to a hard crash here.
    """
    versions = get_artifact_versions(run_id, "framework_design")
    # versions is newest-first; we want the lowest version number, which is
    # the Round-1 framework archived the first time framework_adjust overwrote
    # the live file.
    for entry in reversed(versions):
        if entry.get("version") == 1:
            path = get_run_dir(run_id) / entry["filename"]
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
    return fallback
