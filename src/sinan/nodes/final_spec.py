"""final_spec — 司南 compiles the Harness Design Draft (md + json).

Agent: 司南 (编译者)
Layer: 架构层 (出口前一站)

NOTE: 本节点在 sinan_approval 之前运行，产出的 md + json 是**待审稿**。
用户在 sinan_approval 中直接基于这份 md 决策 approve / reject / request_changes：
- approve → 流程结束
- reject / request_changes → arch_revise → framework_design 重走辩论 → 重新进 final_spec 重生成

所以 final_spec 在一次 run 里可能被调用多次（每次 reject 重生成一份）。

Reads:
    state["architecture_pack"]  — from zonggong_integrate
    state["user_brief_form"]   — from brief_compile
    state["framework_design"]  — adjusted framework
    state["subagent_reviews"]  — sub-agent review reports
    state["subagent_outputs"]  — sub-agent detailed module designs

Writes:
    state["harness_design_draft"] — AI 代码层可直接解析的结构化设计规范
    state["current_phase"]         — "FINAL_SPEC"
    state["artifact_versions"]     — records harness_design_draft version

Artifacts:
    harness_design_draft.json  — 研发层 AI 消费的结构化设计规范（架构层→研发层交接物）
    harness_design_final.md    — 给用户/审核者阅读的完整设计稿（用户审批时看的就是这份）

Routes:
    → sinan_approval  (linear, 强制用户审批)
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from ..state import HarnessBuilderState
from ..artifacts import (
    write_json, write_md, update_run_state, append_progress_log,
    append_decision_log, finalize_phase, get_artifact_summary,
    load_state_or_file,
)
from ..validation import validate_artifact


def final_spec_node(state: HarnessBuilderState) -> dict:
    update_run_state(state["run_id"], "FINAL_SPEC")
    append_progress_log(state["run_id"], "FINAL_SPEC", "Compiling final design draft")

    brief = load_state_or_file(state, "user_brief_form")
    if not brief:
        raise RuntimeError(
            "final_spec requires user_brief_form on disk or in state. "
            "It is the requirement→architecture handoff and brief_compile "
            "is responsible for producing it (enriched with requirement_pack)."
        )
    framework = load_state_or_file(state, "framework_design")
    reviews = load_state_or_file(state, "subagent_reviews")
    adjustments = load_state_or_file(state, "framework_adjustments", filename="framework_adjustment.json")
    arch_review = load_state_or_file(state, "architecture_review")
    arch_pack = load_state_or_file(state, "architecture_pack")
    subagent_outputs = (
        load_state_or_file(state, "subagent_outputs")
        or arch_pack.get("subagent_outputs", {})
        or {}
    )

    draft = _build_ai_draft(
        state, brief, framework, subagent_outputs,
        reviews, adjustments, arch_review, arch_pack,
    )

    # Schema guard: harness_design_draft is the architecture→coding contract.
    # Validate the Python-assembled dict before writing so silent field drift
    # in _build_ai_draft fails fast.
    validate_artifact(draft, "harness_design_draft")
    write_json(state["run_id"], "harness_design_draft.json", draft, versioned=True)
    state["harness_design_draft"] = draft
    state["current_phase"] = "FINAL_SPEC"
    state["artifact_versions"]["harness_design_draft"] = "1.0"

    md = _render_markdown(draft, state)
    write_md(state["run_id"], "harness_design_final.md", md)

    append_progress_log(state["run_id"], "FINAL_SPEC", "Design draft compiled and saved (pending user approval)")
    append_decision_log(state["run_id"], {
        "phase": "FINAL_SPEC",
        "type": "draft_compiled",
        "content": "Harness Design Draft compiled — awaiting user approval in sinan_approval",
    })
    finalize_phase(state["run_id"])

    return state


def _build_ai_draft(
    state, brief, framework, subagent_outputs,
    reviews, adjustments, arch_review, arch_pack,
) -> dict:
    """Assemble the AI-facing JSON design draft from all pipeline artifacts."""
    nodes = framework.get("nodes", [])
    edges = framework.get("edges", [])
    cond_edges = framework.get("conditional_edges", [])
    phases = framework.get("phase_sequence", [])
    entry = framework.get("entry_point", "")
    end_state = framework.get("end_state", "")
    rationale = framework.get("design_rationale", "")

    # Memory / Handoff / Eval from subagents
    memory = subagent_outputs.get("memory", {})
    handoff = subagent_outputs.get("handoff", {})
    eval_design = subagent_outputs.get("eval", {})

    # Risk summary from reviews
    all_incompat = []
    all_missing = []
    all_endorsed = []
    for agent, rev in reviews.items():
        all_incompat.extend(rev.get("incompatibilities", []))
        all_missing.extend(rev.get("missing_elements", []))
        all_endorsed.extend(rev.get("endorsed_elements", []))

    review_summary = {
        "total_incompatibilities": len(all_incompat),
        "total_missing_elements": len(all_missing),
        "total_endorsed_elements": len(all_endorsed),
        "by_agent": {
            name: {
                "incompatibilities": rev.get("incompatibilities", []),
                "missing_elements": rev.get("missing_elements", []),
                "endorsed_elements": rev.get("endorsed_elements", []),
                "summary": rev.get("summary", ""),
            }
            for name, rev in reviews.items()
        },
    }

    arch_challenge_score = arch_review.get("challenge_score", "N/A")
    arch_recommendation = arch_review.get("recommendation", "N/A")

    return {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "run_id": state["run_id"],

        # ── Requirements ──
        # brief is the enriched user_brief_form; all fields below come from
        # brief_compile's _enrich_user_brief_form (requirement_pack keys) or
        # the LLM's own user_brief_form fields. Missing → "未定义"/[]/unknown
        # is a real failure signal, not a fallback.
        "use_case": brief.get("use_case_summary", "未定义"),
        "primary_goal": brief.get("primary_goal", "未定义"),
        "scope": {
            "inclusions": brief.get("scope_inclusions", []),
            "exclusions": brief.get("scope_exclusions", []),
        },
        "success_criteria": brief.get("success_criteria", []),
        "constraints": brief.get("known_constraints", []),
        "assumptions": brief.get("assumptions", []),
        "stakeholders": brief.get("stakeholders", []),
        "persona_qualities": brief.get("persona_qualities", []),
        "risk_tolerance": brief.get("risk_tolerance", "unknown"),

        # ── Agent Graph ──
        "graph": {
            "nodes": nodes,
            "edges": edges,
            "conditional_edges": cond_edges,
            "entry_point": entry,
            "end_state": end_state,
        },

        # ── Phase Sequence ──
        "phase_sequence": phases,

        # ── Detailed Module Designs ──
        "memory_module": memory,
        "handoff_protocol": handoff,
        "eval_placements": eval_design,

        # ── Governance ──
        "approval_gates": arch_pack.get("approval_gates", []),
        "failure_recovery": arch_pack.get("failure_recovery", "未定义"),
        "state_schema": _derive_state_schema(state),

        # ── Design Rationale ──
        "design_rationale": rationale,
        "design_evolution": adjustments.get("preserved_elements", []),

        # ── Reviews ──
        "subagent_review_summary": review_summary,
        "architecture_challenge": {
            "challenge_score": arch_challenge_score,
            "recommendation": arch_recommendation,
            "over_engineering_flags": arch_review.get("over_engineering_flags", []),
            "handoff_gaps": arch_review.get("handoff_gaps", []),
            "eval_gaps": arch_review.get("eval_gaps", []),
            "failure_mode_omissions": arch_review.get("failure_mode_omissions", []),
            "cost_complexity_concerns": arch_review.get("cost_complexity_concerns", []),
        },

        # ── Risks ──
        "risks_identified": arch_pack.get("risks_identified", []),
        "alternative_options": arch_pack.get("alternative_options", []),

        # ── Metadata ──
        "artifact_version_summary": get_artifact_summary(state["run_id"]),
    }


def _derive_state_schema(state: HarnessBuilderState) -> dict:
    """Return the target harness's state schema description.

    Previously this was derived from ``user_brief_form.scope_inclusions``
    (Chinese strings), which was fragile: renaming a scope item in the
    requirement layer silently shrank the schema, and no validator caught it.

    The actual source of truth is ``sinan.state.HarnessBuilderState``. Reflect
    that directly here so the field stays stable across LLM-output drift.
    """
    return {
        "required_fields": [
            # ── Meta ──
            {"name": "run_id", "type": "string", "description": "Run identifier"},
            {"name": "started_at", "type": "string", "description": "ISO-8601 start timestamp"},
            {"name": "current_phase", "type": "string", "description": "Current execution phase"},
            # ── User input ──
            {"name": "user_raw_input", "type": "string", "description": "Raw user input"},
            {"name": "user_supplements", "type": "list", "description": "User answers to debate questions"},
            {"name": "user_brief_answers", "type": "list[dict]", "description": "Structured answer records"},
            # ── Requirement-layer artifacts ──
            {"name": "requirement_pack", "type": "dict", "description": "Tuopu expanded requirements"},
            {"name": "spec_review", "type": "dict", "description": "Jiewen critical review"},
            {"name": "brief_debate", "type": "dict", "description": "Tuopu-Jiewen debate result"},
            {"name": "user_brief_form", "type": "dict", "description": "Final requirement contract"},
            # ── Architecture-layer artifacts ──
            {"name": "framework_design", "type": "dict", "description": "Initial framework draft"},
            {"name": "subagent_reviews", "type": "dict", "description": "Memory/Handoff/Eval per-agent reviews"},
            {"name": "subagent_outputs", "type": "dict", "description": "Memory/Handoff/Eval detailed designs"},
            {"name": "framework_adjustments", "type": "dict", "description": "Round 3 adjustment record"},
            {"name": "architecture_pack", "type": "dict", "description": "Integrated architecture pack"},
            {"name": "architecture_review", "type": "dict", "description": "Nishen red-team review"},
            {"name": "arch_revision_brief", "type": "dict", "description": "Revision brief on reject"},
            {"name": "harness_design_draft", "type": "dict", "description": "Cross-layer design contract"},
            # ── Gatekeeping ──
            {"name": "gate_flags", "type": "dict", "description": "Risk-level, key_concerns, checklist"},
            {"name": "arch_reject_count", "type": "int", "description": "User rejection counter (≤3)"},
            {"name": "risk_register", "type": "list[dict]", "description": "Cross-layer risk tracking"},
            # ── Flow control (interrupt/resume — currently placeholder) ──
            {"name": "pending_interrupt", "type": "string", "description": "Optional[Literal]"},
            {"name": "resume_payload", "type": "dict", "description": "User resume payload"},
            # ── Scribe ──
            {"name": "decision_log", "type": "list[dict]", "description": "Decision history"},
            {"name": "progress_log", "type": "list[dict]", "description": "Progress history"},
            {"name": "artifact_versions", "type": "dict", "description": "Version registry"},
            # ── Messages ──
            {"name": "messages", "type": "list[dict]", "description": "Conversation history raw"},
        ],
    }


def _render_markdown(draft: dict, state: HarnessBuilderState) -> str:
    lines = [
        f"# 司南 Harness 设计稿 v{draft['version']}",
        "",
        f"**Run ID:** `{state['run_id']}`",
        f"**生成时间:** {draft['generated_at']}",
        "",
        "---",
        "",
        "## 一、需求确认",
        "",
        "### 核心目标",
        draft["primary_goal"],
        "",
        "### 干系人",
    ]
    for s in draft.get("stakeholders", []):
        lines.append(f"- {s}")
    lines += ["", "### 范围", "", "**包含:**"]
    for s in draft.get("scope", {}).get("inclusions", []):
        lines.append(f"- {s}")
    lines += ["", "**排除:**"]
    for s in draft.get("scope", {}).get("exclusions", []):
        lines.append(f"- {s}")
    lines += ["", "### 成功标准"]
    for i, s in enumerate(draft.get("success_criteria", []), 1):
        lines.append(f"{i}. {s}")
    lines += ["", "### 约束条件"]
    for c in draft.get("constraints", []):
        lines.append(f"- {c}")
    lines += ["", "### 假设前提"]
    for a in draft.get("assumptions", []):
        lines.append(f"- {a}")

    # ── Agent Graph ──
    graph = draft.get("graph", {})
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    cond_edges = graph.get("conditional_edges", [])

    lines += [
        "",
        "---",
        "",
        "## 二、架构设计",
        "",
        "### Agent Graph",
    ]
    if nodes:
        lines.append("| 节点名称 | 职责 |")
        lines.append("|---------|------|")
        for n in nodes:
            if isinstance(n, dict):
                lines.append(f"| {n.get('name', n)} | {n.get('role', n.get('description', ''))} |")
            else:
                lines.append(f"| {n} |  |")
        lines.append("")
        lines.append(f"**入口节点:** `{graph.get('entry_point', '')}`")
        lines.append(f"**终止状态:** `{graph.get('end_state', '')}`")
    else:
        lines.append("（节点信息待填充）")

    lines += ["", "### 节点连线"]
    if edges:
        lines.append("| 起点 | 终点 |")
        lines.append("|------|------|")
        for e in edges:
            if isinstance(e, dict):
                lines.append(f"| {e.get('from', '')} | {e.get('to', '')} |")
            else:
                lines.append(f"| {e} |  |")
    else:
        lines.append("（边信息待填充）")

    if cond_edges:
        lines += ["", "### 条件路由"]
        lines.append("| 条件 | 路由 |")
        lines.append("|------|------|")
        for ce in cond_edges:
            if isinstance(ce, dict):
                lines.append(f"| {ce.get('condition', '')} | {ce.get('routes', '')} |")

    lines += ["", "### 阶段序列"]
    phases = draft.get("phase_sequence", [])
    if phases:
        for i, p in enumerate(phases, 1):
            lines.append(f"{i}. {p}")
    else:
        lines.append("（阶段序列待填充）")

    lines += ["", "### 状态 Schema"]
    schema = draft.get("state_schema", {})
    schema_fields = schema.get("required_fields", [])
    if schema_fields:
        lines.append(f"共 {len(schema_fields)} 个字段：")
        lines.append("")
        lines.append("| 字段名 | 类型 | 描述 |")
        lines.append("|--------|------|------|")
        for f in schema_fields:
            lines.append(f"| {f.get('name', '')} | {f.get('type', '')} | {f.get('description', '')} |")
    else:
        lines.append("（状态 Schema 待填充）")

    # ── Module Designs ──
    lines += [
        "",
        "---",
        "",
        "## 三、核心模块设计",
    ]

    # Memory
    memory = draft.get("memory_module", {})
    lines += ["", "### 记忆模块"]
    if memory:
        for k, v in memory.items():
            lines.append(f"**{k}:** {v}")
    else:
        lines.append("（记忆模块设计待填充）")

    # Handoff
    handoff = draft.get("handoff_protocol", {})
    lines += ["", "### 交接协议"]
    if handoff:
        for k, v in handoff.items():
            lines.append(f"**{k}:** {v}")
    else:
        lines.append("（交接协议设计待填充）")

    # Eval
    eval_d = draft.get("eval_placements", {})
    lines += ["", "### 评估机制"]
    if eval_d:
        for k, v in eval_d.items():
            lines.append(f"**{k}:** {v}")
    else:
        lines.append("（评估机制设计待填充）")

    # ── Governance ──
    lines += [
        "",
        "---",
        "",
        "## 四、治理与安全",
        "",
        "### 审批闸门",
    ]
    gates = draft.get("approval_gates", [])
    if gates:
        for g in gates:
            lines.append(f"- {g}")
    else:
        lines.append("无")

    lines += ["", "### 失败恢复策略"]
    failure = draft.get("failure_recovery", "未定义")
    if isinstance(failure, str):
        lines.append(failure)
    else:
        lines.append(json.dumps(failure, indent=2, ensure_ascii=False))

    # ── Design Rationale ──
    rationale = draft.get("design_rationale", "")
    if rationale:
        lines += ["", "---", "", "## 五、设计理念"]
        lines.append(rationale)

    # ── Reviews ──
    lines += [
        "",
        "---",
        "",
        "## 六、审查摘要",
    ]

    review_sum = draft.get("subagent_review_summary", {})
    if review_sum:
        by_agent = review_sum.get("by_agent", {})
        lines.append("")
        lines.append("| 子代理 | 评审摘要 | 不兼容 | 缺失 | 认可 |")
        lines.append("|--------|----------|--------|------|------|")
        for name, info in by_agent.items():
            lines.append(
                f"| {name} | {info.get('summary', '')} | "
                f"{len(info.get('incompatibilities', []))} | "
                f"{len(info.get('missing_elements', []))} | "
                f"{len(info.get('endorsed_elements', []))} |"
            )

    arch_ch = draft.get("architecture_challenge", {})
    score = arch_ch.get("challenge_score", "N/A")
    rec = arch_ch.get("recommendation", "N/A")
    lines += [
        "",
        f"| 架构挑战评分 | {score}/10 |",
        f"| 架构建议 | {rec} |",
    ]

    over_eng = arch_ch.get("over_engineering_flags", [])
    if over_eng:
        lines += ["", "#### 过度工程化警告"]
        for item in over_eng:
            lines.append(f"- {item}")

    handoff_gaps = arch_ch.get("handoff_gaps", [])
    if handoff_gaps:
        lines += ["", "#### 交接缺口"]
        for g in handoff_gaps:
            lines.append(f"- {g}")

    eval_gaps = arch_ch.get("eval_gaps", [])
    if eval_gaps:
        lines += ["", "#### 评估缺口"]
        for g in eval_gaps:
            lines.append(f"- {g}")

    failures = arch_ch.get("failure_mode_omissions", [])
    if failures:
        lines += ["", "#### 未处理的失败模式"]
        for f in failures:
            lines.append(f"- {f}")

    # ── Risks ──
    risks = draft.get("risks_identified", [])
    if risks:
        lines += ["", "---", "", "## 七、风险摘要"]
        lines.append("")
        lines.append("| 风险类型 | 描述 |")
        lines.append("|----------|------|")
        for r in risks:
            if isinstance(r, dict):
                lines.append(f"| {r.get('type', '')} | {r.get('description', '')} |")
            else:
                lines.append(f"| 风险 | {r} |")

    # ── Artifact history ──
    lines += [
        "",
        "---",
        "",
        "## 八、Artifact 版本历史",
    ]
    version_summary = draft.get("artifact_version_summary", {})
    if version_summary:
        for artifact, info in version_summary.items():
            versions = info.get("versions", [])
            if len(versions) > 1:
                lines.append(f"**{artifact}** — 共 {info['total_versions']} 个版本")
                lines.append("")
                lines.append("| 版本 | 文件 |")
                lines.append("|--------|------|")
                for v in sorted(versions):
                    lines.append(f"| v{v} | {artifact}_v{v}.json |")
                lines.append("")
    else:
        lines.append("无多版本历史。")

    lines += [
        "",
        "---",
        "",
        "*本设计稿由司南 Harness Builder 自动生成。*",
    ]
    return "\n".join(lines)
