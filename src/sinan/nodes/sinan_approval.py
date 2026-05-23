"""sinan_approval — 司南请求用户对架构设计做出最终决策。

Agent: 司南 (用户交互)
Layer: 架构层

Reads:
    state["architecture_pack"]    — from zonggong_integrate
    state["architecture_review"] — from architecture_challenge
    state["gate_flags"]          — from approval_gate (risk details)

Writes:
    state["resume_payload"]      — {approval: "approve"|"reject"|"request_changes", user_intent: str}
    state["arch_reject_count"]   — incremented on reject
    state["pending_interrupt"]    — reset to None
    state["current_phase"]        — "SINAN_APPROVAL"

Artifacts:
    (none — interactive console node)

Routes:
    → final_spec    when approval == "approve"
    → arch_revise   when rejection (≤2 rounds, else RuntimeError)
"""
from __future__ import annotations
from ..state import HarnessBuilderState
from ..artifacts import append_progress_log, append_decision_log


def sinan_approval_node(state: HarnessBuilderState) -> dict:
    """Show architecture summary and collect user approval decision."""
    arch = state.get("architecture_pack") or {}
    review = state.get("architecture_review") or {}
    gate_flags = state.get("gate_flags", {})

    print("\n" + "=" * 60)
    print("司南：架构设计已完成，请审阅后做出决策")
    print("=" * 60)

    # 守门判断
    risk_level = gate_flags.get("risk_level", "unknown")
    reasoning = gate_flags.get("shoumen_reasoning", "")
    key_concerns = gate_flags.get("key_concerns", [])
    print("\n【守门判断】")
    print(f"  风险等级: {risk_level}")
    if reasoning:
        print(f"  判断理由: {reasoning}")
    if key_concerns:
        print(f"  重点关注:")
        for c in key_concerns:
            print(f"    · {c}")

    # 架构概览
    print("\n【架构概览】")
    phases = arch.get("phase_sequence", [])
    print(f"  阶段序列: {', '.join(phases) if phases else '未定义'}")
    gates = arch.get("approval_gates", [])
    print(f"  审批闸门: {len(gates)} 处")
    print(f"  失败恢复: {arch.get('failure_recovery', '未定义')}")

    # 逆审评分
    print("\n【逆审评分】")
    print(f"  评分: {review.get('challenge_score', '?')}/10")
    print(f"  建议: {review.get('recommendation', '?')}")

    # 逆审详细警告
    if review.get("handoff_gaps"):
        print(f"\n【交接缺口警告】({len(review['handoff_gaps'])} 条)")
        for g in review["handoff_gaps"][:3]:
            print(f"  - {g}")
    if review.get("eval_gaps"):
        print(f"\n【评估缺口警告】({len(review['eval_gaps'])} 条)")
        for e in review["eval_gaps"][:3]:
            print(f"  - {e}")
    if review.get("failure_mode_omissions"):
        print(f"\n【未覆盖失败模式】({len(review['failure_mode_omissions'])} 条)")
        for f in review["failure_mode_omissions"][:3]:
            print(f"  - {f}")
    if review.get("over_engineering_flags"):
        print(f"\n【过度设计警告】({len(review['over_engineering_flags'])} 条)")
        for f in review["over_engineering_flags"][:3]:
            print(f"  - {f}")

    # 收集用户决策
    print("\n请选择: [approve] / [reject] / [request_changes]")
    print("（如选择 reject 或 request_changes，请说明您希望修改的方向）")
    while True:
        choice = input("  > ").strip().lower()
        if choice in ("approve", "reject", "request_changes"):
            break
        print("  无效输入。")

    # 如果拒绝或要求修改，收集修改方向
    user_intent = ""
    if choice in ("reject", "request_changes"):
        print("\n  请简要说明您希望修改的方向（直接回车可跳过）：")
        user_intent = input("  > ").strip()

    state["resume_payload"] = {"approval": choice, "user_intent": user_intent}
    state["pending_interrupt"] = None
    state["interrupted_by"] = "user"
    state["current_phase"] = "SINAN_APPROVAL"

    reject_count = state.get("arch_reject_count", 0)
    if choice in ("reject", "request_changes"):
        state["arch_reject_count"] = reject_count + 1

    append_decision_log(state["run_id"], {
        "phase": "SINAN_APPROVAL",
        "type": f"user_{choice}",
        "content": f"User chose '{choice}' — reject_count={state['arch_reject_count']}",
        "user_intent": user_intent,
    })
    append_progress_log(
        state["run_id"], "SINAN_APPROVAL",
        f"User selected: {choice} (arch_reject_count={state['arch_reject_count']})"
    )

    return state
