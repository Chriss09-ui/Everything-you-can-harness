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


def _require(state: HarnessBuilderState, key: str, producer: str, filename: str | None = None) -> dict:
    """Read a required upstream artifact; raise if missing.

    final_spec used to silently fall back to ``{}`` for missing inputs, which
    produced a schema-valid but content-empty draft that the coding layer then
    ran with as if it were real. This helper makes the dependency explicit.

    Args:
        state: workflow state dict (must contain ``run_id``).
        key: state field name and (by default) disk filename stem.
        producer: name of the upstream node responsible for producing this
            artifact, included in the error message to point at the fix.
        filename: optional override for disk filename (default: ``<key>.json``).
    """
    value = load_state_or_file(state, key, filename=filename)
    if not value:
        run_id = state.get("run_id", "<unknown>")
        fname = filename or f"{key}.json"
        raise RuntimeError(
            f"final_spec requires {key} but it is missing in both state and "
            f"on disk (runs/{run_id}/{fname}). Producer: {producer}. "
            f"Run the architecture layer from the start, or use --from-brief "
            f"with a complete run."
        )
    return value


def final_spec_node(state: HarnessBuilderState) -> dict:
    update_run_state(state["run_id"], "FINAL_SPEC")
    append_progress_log(state["run_id"], "FINAL_SPEC", "Compiling final design draft")

    # All architecture-debate artifacts are required. We fail fast on missing
    # upstream rather than silently producing an empty draft. The only optional
    # field is framework_adjustments (only present after a reject round).
    brief = _require(state, "user_brief_form", "brief_compile")
    framework = _require(state, "framework_design", "framework_design")
    reviews = _require(state, "subagent_reviews", "subagent_review")
    arch_review = _require(state, "architecture_review", "architecture_challenge")
    arch_pack = _require(state, "architecture_pack", "zonggong_integrate")
    subagent_outputs = _require(state, "subagent_outputs", "subagent_review")
    adjustments = load_state_or_file(
        state, "framework_adjustments", filename="framework_adjustment.json"
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

    # Summary is read AFTER write_json so the draft's own freshly-registered
    # version shows up in the rendered md. Embedding it inside the JSON draft
    # would necessarily be one version stale (computed before its own write).
    version_summary = get_artifact_summary(state["run_id"])
    md = _render_markdown(draft, state, version_summary)
    write_md(state["run_id"], "harness_design_final.md", md)

    append_progress_log(state["run_id"], "FINAL_SPEC", "Design draft compiled and saved (pending user approval)")
    append_decision_log(state["run_id"], {
        "phase": "FINAL_SPEC",
        "type": "draft_compiled",
        "content": "Harness Design Draft compiled — awaiting user approval in sinan_approval",
    })
    finalize_phase(state["run_id"])

    return state


def _derive_test_cases(brief: dict) -> list[dict]:
    """Derive initial test_cases for the harness from the requirement contract.

    Each success_criterion gets a placeholder test case with a stable id and
    the criterion text echoed back as ``scenario``. The user (in
    sinan_approval) is expected to flesh out the placeholders; if they accept
    the placeholders as-is, the runner will use whatever the harness's
    published main.py consumes as input.

    Schema (per test case):
        {
          "id": "tc_<n>",
          "scenario": "<human description — often the success_criterion>",
          "input": "...",                 # what to feed the harness via stdin
          "expected_output_keys": [...],  # required top-level keys in output
          "expected_to_pass": True        # False ⇒ expects the harness to refuse
        }

    **Placeholder rule**: derived cases have empty ``input`` / empty
    ``expected_output_keys`` by default, so they're marked
    ``expected_to_pass=False`` to prevent the runner from treating them as
    "hard pass" evidence. If the user fills in real input/keys, they're
    expected to also flip ``expected_to_pass`` to True (otherwise the runner
    will count a successful run as a "soft pass" — passing against an
    expectation of failure, which contributes nothing to overall_pass).

    The user can override by editing ``harness_design_draft.json`` directly —
    ``final_spec`` reads test_cases from there only (``brief`` itself does
    not carry test_cases under any current schema).
    """
    if not brief:
        return []
    # Try the draft on disk first — this is where a user-edited test_cases
    # list would live. ``brief`` (user_brief_form) does not carry test_cases
    # under the current schema, so checking ``brief.get("test_cases")`` was
    # dead code. If we ever extend the requirement contract to include
    # test cases, that's the place to read it.
    success_criteria = brief.get("success_criteria") or []
    cases = []
    for idx, criterion in enumerate(success_criteria, 1):
        # Derived cases start as placeholders — runner must not consider
        # them as hard evidence of correctness.
        cases.append({
            "id": f"tc_{idx:03d}",
            "scenario": criterion,
            "input": "",                  # placeholder — user fills in
            "expected_output_keys": [],    # placeholder
            "expected_to_pass": False,     # placeholder, see docstring
            "is_placeholder": True,
        })
    return cases


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
        "test_cases": _derive_test_cases(brief),
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
        # NOTE: artifact_version_summary is intentionally NOT embedded here.
        # It is rendered into the md AFTER write_json runs (see final_spec_node),
        # so the current draft's own version is visible in the rendered output.
    }


def _derive_state_schema(state: HarnessBuilderState) -> dict:
    """Reflect ``HarnessBuilderState``'s declared fields into the schema section.

    Previously the design draft embedded a hand-maintained list of 25 fields;
    any field added/removed in ``state.py`` would silently drift out of sync.
    We now read ``HarnessBuilderState.__annotations__`` so the schema in the
    design draft is always the actual schema. Field order matches the
    declaration order in the TypedDict.
    """
    from ..state import HarnessBuilderState as _State

    fields = []
    for name, typ in _State.__annotations__.items():
        fields.append({
            "name": name,
            "type": _type_to_string(typ),
            # We don't try to auto-generate descriptions — that would just be
            # another hand-maintained table, prone to the same drift. The md
            # rendering shows name + type, which is enough for readers.
            "description": "",
        })
    return {"required_fields": fields}


def _type_to_string(typ) -> str:
    """Render a typing annotation to a short human-readable string."""
    import typing
    # Primitive types
    if typ is str:
        return "string"
    if typ is int:
        return "int"
    if typ is bool:
        return "bool"
    if typ is dict:
        return "dict"
    if typ is list:
        return "list"
    origin = typing.get_origin(typ)
    args = typing.get_args(typ)
    if origin is typing.Union:
        # Optional[X] is Union[X, None]
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1 and len(args) == 2:
            return f"Optional[{_type_to_string(non_none[0])}]"
        return " | ".join(_type_to_string(a) for a in args)
    if origin is dict:
        return "dict"
    if origin is list:
        return "list"
    if origin is typing.Literal:
        return f"Literal[{', '.join(repr(a) for a in args)}]"
    # Fallback — strip module prefix from typing constructs
    return getattr(typ, "__name__", str(typ)).split(".")[-1]


def _render_markdown(
    draft: dict,
    state: HarnessBuilderState,
    version_summary: dict | None = None,
) -> str:
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
    version_summary = version_summary or {}
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
