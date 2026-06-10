"""sinan_approval — 司南与用户梳理完整架构设计并收集决策。

Agent: 司南 (用户交互)
Layer: 架构层（终态前最后一站）

**职责**：把 `harness_design_final.md` 里完整的设计稿分章节讲给用户听，让用户在
掌握全貌的前提下做出 approve / reject / request_changes 决策。

**前置节点 final_spec 已经把 md + json 写到磁盘了**：
- `harness_design_final.md` 是给用户看的人读版
- `harness_design_draft.json` 是给研发层 AI 看的结构化版（用户 approve 后由
  `--from-design` 自动消费）

Reads:
    state["harness_design_draft"]  — from final_spec (already in state or on disk)
    state["gate_flags"]           — from approval_gate (risk details)

Writes:
    state["resume_payload"]      — {approval: "approve"|"reject"|"request_changes", user_intent: str}
    state["arch_reject_count"]   — incremented on reject / request_changes
                                   (audit/display only; no hard cap)
    state["pending_interrupt"]    — reset to None
    state["current_phase"]        — "SINAN_APPROVAL"

Artifacts:
    (none — interactive console node)

Routes:
    → END           when approval == "approve" or "abort"  (router handles)
    → arch_revise   when reject / request_changes (no cap — user keeps
                    revising until they explicitly approve or abort)
"""
from __future__ import annotations
from ..state import HarnessBuilderState
from ..artifacts import (
    append_progress_log, append_decision_log, load_state_or_file,
    update_run_state, join_display,
)


def sinan_approval_node(state: HarnessBuilderState) -> dict:
    """Walk the user through the full design and collect the approval decision."""
    update_run_state(state["run_id"], "SINAN_APPROVAL")
    draft = load_state_or_file(state, "harness_design_draft")
    gate_flags = state.get("gate_flags", {})
    run_id = state["run_id"]
    reject_count_before = state.get("arch_reject_count", 0)

    print("\n" + "=" * 60)
    print("司南：架构设计已就绪，下面带您梳理一遍")
    print("=" * 60)
    print(f"（完整设计稿: runs/{run_id}/harness_design_final.md）")
    print(f"（研发层入口: runs/{run_id}/harness_design_draft.json）")

    # ── 守门风险摘要（先讲风险，让用户带着警觉看后续） ──
    risk_level = gate_flags.get("risk_level", "unknown")
    reasoning = gate_flags.get("shoumen_reasoning", "")
    key_concerns = gate_flags.get("key_concerns", []) or []
    print(f"\n【守门风险摘要】 risk_level = {risk_level}")
    if reasoning:
        print(f"  理由: {reasoning}")
    if key_concerns:
        print(f"  重点关注:")
        for c in key_concerns:
            print(f"    · {c}")

    # ── 全文梳理 ──
    sections = _build_sections(draft)
    skip_rest = False
    for title, body in sections:
        if skip_rest:
            break
        print("\n" + "─" * 60)
        print(f"【{title}】")
        for line in body:
            print(line)
        ans = _pause_for_user()
        if ans.strip().lower() == "q":
            skip_rest = True

    # ── 决策 ──
    print("\n" + "=" * 60)
    print("以上是完整设计。请做出决策：")
    print("  [approve]         架构合理，进研发层")
    print("  [request_changes] 有修改意见，希望保留大方向（会回到辩论循环）")
    print("  [reject]          需要重做（会回到辩论循环）")
    print("  [abort]           停止整个流程，保留当前设计稿在盘上")
    print(f"  当前已拒绝次数: {reject_count_before}")
    print("=" * 60)

    while True:
        try:
            choice = input("  您的选择 > ").strip().lower()
        except EOFError:
            # Non-interactive env (piped stdin / CI / forgotten test mock):
            # default to ``abort`` rather than ``approve``. Previously this
            # silently auto-approved the architecture when no human was at
            # the prompt — a dangerous default for an audit gate. ``abort``
            # preserves the latest draft on disk and lets a human pick it up
            # later via ``--from-design`` if they want. Tests that need a
            # specific decision monkeypatch input() explicitly.
            choice = "abort"
        if choice in ("approve", "reject", "request_changes", "abort"):
            break
        print("  无效输入。请输入 approve / reject / request_changes / abort")

    user_intent = ""
    if choice in ("reject", "request_changes"):
        print("\n  请简要说明您希望修改的方向（直接回车可跳过）：")
        try:
            user_intent = input("  > ").strip()
        except EOFError:
            user_intent = ""

    state["resume_payload"] = {"approval": choice, "user_intent": user_intent}
    state["pending_interrupt"] = None
    state["current_phase"] = "SINAN_APPROVAL"

    if choice in ("reject", "request_changes"):
        state["arch_reject_count"] = reject_count_before + 1

    append_decision_log(run_id, {
        "phase": "SINAN_APPROVAL",
        "type": f"user_{choice}",
        "content": f"User chose '{choice}' — reject_count={state['arch_reject_count']}",
        "user_intent": user_intent,
    })
    append_progress_log(
        run_id, "SINAN_APPROVAL",
        f"User selected: {choice} (arch_reject_count={state['arch_reject_count']})"
    )

    return state


def _pause_for_user() -> str:
    """Light pause so the user can read each section before next one prints.

    Returns the user's input (trimmed). User types 'q' to skip remaining sections.
    """
    try:
        return input("\n  （回车继续 / 输入 q 跳过剩余章节）> ").strip()
    except EOFError:
        return ""


def _build_sections(draft: dict) -> list[tuple[str, list[str]]]:
    """Render each section of the draft as plain terminal lines."""
    sections: list[tuple[str, list[str]]] = []

    # 一、需求
    req_lines = []
    req_lines.append(f"核心目标: {draft.get('primary_goal', '未定义')}")
    stakeholders = draft.get("stakeholders", []) or []
    if stakeholders:
        req_lines.append(f"干系人: {join_display(stakeholders)}")
    scope = draft.get("scope", {}) or {}
    inclusions = scope.get("inclusions", []) or []
    exclusions = scope.get("exclusions", []) or []
    if inclusions:
        req_lines.append("范围 · 包含:")
        for s in inclusions:
            req_lines.append(f"  - {s}")
    if exclusions:
        req_lines.append("范围 · 排除:")
        for s in exclusions:
            req_lines.append(f"  - {s}")
    success_criteria = draft.get("success_criteria", []) or []
    if success_criteria:
        req_lines.append("成功标准:")
        for i, c in enumerate(success_criteria, 1):
            req_lines.append(f"  {i}. {c}")
    constraints = draft.get("constraints", []) or []
    if constraints:
        req_lines.append("约束条件:")
        for c in constraints:
            req_lines.append(f"  - {c}")
    sections.append(("一、需求确认", req_lines))

    # 二、架构
    arch_lines = []
    graph = draft.get("graph", {}) or {}
    nodes = graph.get("nodes", []) or []
    if nodes:
        arch_lines.append(f"Agent Graph ({len(nodes)} 个节点):")
        for n in nodes:
            if isinstance(n, dict):
                arch_lines.append(f"  - {n.get('name', '?')}: {n.get('role', n.get('description', ''))}")
            else:
                arch_lines.append(f"  - {n}")
    edges = graph.get("edges", []) or []
    if edges:
        arch_lines.append(f"节点连线 ({len(edges)} 条):")
        for e in edges[:8]:
            if isinstance(e, dict):
                arch_lines.append(f"  {e.get('from', '?')} → {e.get('to', '?')}")
            else:
                arch_lines.append(f"  {e}")
        if len(edges) > 8:
            arch_lines.append(f"  ...（共 {len(edges)} 条，详见 md）")
    cond_edges = graph.get("conditional_edges", []) or []
    if cond_edges:
        arch_lines.append(f"条件路由 ({len(cond_edges)} 条):")
        for ce in cond_edges:
            if isinstance(ce, dict):
                arch_lines.append(f"  {ce.get('condition', '?')}: {ce.get('routes', '')}")
    phases = draft.get("phase_sequence", []) or []
    if phases:
        arch_lines.append(f"阶段序列: {join_display(phases, sep=' → ')}")
    arch_lines.append(f"入口: {graph.get('entry_point', '未定义')}")
    arch_lines.append(f"终态: {graph.get('end_state', '未定义')}")
    sections.append(("二、架构设计", arch_lines))

    # 三、核心模块
    mod_lines = []
    memory = draft.get("memory_module", {}) or {}
    handoff = draft.get("handoff_protocol", {}) or {}
    eval_d = draft.get("eval_placements", {}) or {}
    mod_lines.append("记忆模块:")
    if memory:
        for k, v in memory.items():
            mod_lines.append(f"  {k}: {v}")
    else:
        mod_lines.append("  (未定义)")
    mod_lines.append("")
    mod_lines.append("交接协议:")
    if handoff:
        for k, v in handoff.items():
            mod_lines.append(f"  {k}: {v}")
    else:
        mod_lines.append("  (未定义)")
    mod_lines.append("")
    mod_lines.append("评估机制:")
    if eval_d:
        for k, v in eval_d.items():
            mod_lines.append(f"  {k}: {v}")
    else:
        mod_lines.append("  (未定义)")
    sections.append(("三、核心模块设计", mod_lines))

    # 四、治理
    gov_lines = []
    approval_gates = draft.get("approval_gates", []) or []
    gov_lines.append(f"审批闸门: {join_display(approval_gates, empty='无')}")
    gov_lines.append(f"失败恢复: {draft.get('failure_recovery', '未定义')}")
    sections.append(("四、治理与安全", gov_lines))

    # 五、设计理念
    rationale = draft.get("design_rationale", "")
    design_evolution = draft.get("design_evolution", []) or []
    rat_lines = []
    if rationale:
        rat_lines.append(rationale)
    if design_evolution:
        rat_lines.append("保留要素:")
        for e in design_evolution:
            rat_lines.append(f"  - {e}")
    if not rationale and not design_evolution:
        rat_lines.append("(无)")
    sections.append(("五、设计理念", rat_lines))

    # 六、测试用例（架构层带下来的，runner 会用这些测试生成的代码）
    tc_lines = []
    test_cases = draft.get("test_cases", []) or []
    if test_cases:
        tc_lines.append(f"共 {len(test_cases)} 个测试用例（runner 会按这些跑生成的 harness）：")
        tc_lines.append("")
        for tc in test_cases:
            tc_lines.append(f"  · {tc.get('id', '?')}: {tc.get('scenario', '(无描述)')}")
            user_input = tc.get("input", "")
            if user_input:
                tc_lines.append(f"      输入: {user_input[:80]}{'...' if len(str(user_input)) > 80 else ''}")
            keys = tc.get("expected_output_keys", []) or []
            if keys:
                tc_lines.append(f"      期望输出键: {join_display(keys)}")
            if not tc.get("expected_to_pass", True):
                tc_lines.append("      预期: harness 应拒绝/报错")
        tc_lines.append("")
        tc_lines.append("（测试用例可在 runs/<run_id>/harness_design_draft.json 编辑后重跑）")
    else:
        tc_lines.append("(无 — 研发层将无测试用例可跑，建议在 sinan_approval 之前补全)")
    sections.append(("六、测试用例", tc_lines))

    # 七、审查摘要
    rev_lines = []
    review_sum = draft.get("subagent_review_summary", {}) or {}
    by_agent = review_sum.get("by_agent", {}) or {}
    if by_agent:
        rev_lines.append("子代理评审:")
        rev_lines.append("| 子代理 | 不兼容 | 缺失 | 认可 | 摘要 |")
        rev_lines.append("|--------|--------|------|------|------|")
        for name, info in by_agent.items():
            rev_lines.append(
                f"| {name} | "
                f"{len(info.get('incompatibilities', []))} | "
                f"{len(info.get('missing_elements', []))} | "
                f"{len(info.get('endorsed_elements', []))} | "
                f"{info.get('summary', '')} |"
            )
    arch_ch = draft.get("architecture_challenge", {}) or {}
    score = arch_ch.get("challenge_score", "N/A")
    rec = arch_ch.get("recommendation", "N/A")
    rev_lines.append("")
    rev_lines.append(f"架构挑战评分: {score}/10")
    rev_lines.append(f"架构建议: {rec}")
    for label, key in [
        ("过度设计警告", "over_engineering_flags"),
        ("交接缺口", "handoff_gaps"),
        ("评估缺口", "eval_gaps"),
        ("未覆盖失败模式", "failure_mode_omissions"),
        ("成本/复杂度问题", "cost_complexity_concerns"),
    ]:
        items = arch_ch.get(key, []) or []
        if items:
            rev_lines.append(f"{label} ({len(items)} 条):")
            for it in items[:5]:
                rev_lines.append(f"  - {it}")
    sections.append(("七、审查摘要", rev_lines))

    # 八、风险摘要
    risk_lines = []
    risks = draft.get("risks_identified", []) or []
    if risks:
        for r in risks:
            if isinstance(r, dict):
                risk_lines.append(f"  - {r.get('type', '?')}: {r.get('description', '')}")
            else:
                risk_lines.append(f"  - {r}")
    else:
        risk_lines.append("(无)")
    sections.append(("八、风险摘要", risk_lines))

    return sections
