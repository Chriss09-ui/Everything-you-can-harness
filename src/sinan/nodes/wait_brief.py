"""wait_brief — 司南向用户展示辩论结论并收集核心需求表单 (legacy, 已由 sinan_debrief 替代).

Agent: 司南 (用户交互)
Layer: 需求层

状态: 不在当前 graph 中（遗留节点，已被 sinan_debrief 替代）

Reads:
    state["brief_debate"]  — debate result

Writes:
    state["user_supplements"]    — raw answer list
    state["pending_interrupt"]  — reset to None
    state["current_phase"]      — "WAIT_USER_BRIEF"

Artifacts:
    (none — interactive console node)

Routes:
    (不在 graph 中注册)
"""
from __future__ import annotations
from ..state import HarnessBuilderState
from ..artifacts import append_progress_log, append_decision_log


def wait_brief_node(state: HarnessBuilderState) -> dict:
    debate = state.get("brief_debate") or {}
    user_questions = debate.get("user_questions", [])
    aligned_points = debate.get("aligned_points", [])
    remaining = debate.get("remaining_disagreements", [])

    print("\n" + "=" * 60)
    print("司南：拓谱与诘问已完成需求辩论，请您填写以下信息")
    print("=" * 60)

    # 展示辩论结论
    if aligned_points:
        print(f"\n【已对齐的需求点】（{len(aligned_points)} 条）")
        for p in aligned_points:
            print(f"  ✓ {p}")

    if remaining:
        print(f"\n【仍存在分歧的点】（{len(remaining)} 条）")
        for d in remaining:
            print(f"  ? {d}")

    # 展示必须回答的问题
    if user_questions:
        print(f"\n【需要您确认的问题】（{len(user_questions)} 条）")
        for i, q in enumerate(user_questions, 1):
            print(f"  {i}. {q}")
        print()

    answers = []
    if user_questions:
        print("请逐条回答上述问题（输入 'skip' 跳过某条，输入 'done' 结束）：")
        for i, q in enumerate(user_questions, 1):
            print(f"\n  问题 {i}: {q}")
            while True:
                line = input("    > ").strip()
                if line.lower() == "skip":
                    answers.append(None)
                    print("    [已跳过]")
                    break
                if line.lower() == "done":
                    # 停止回答，直接进入下一阶段
                    answers.append(None)
                    break
                if line:
                    answers.append(line)
                    break
                print("    请输入内容，或输入 'skip' 跳过，或 'done' 结束。")

    # 处理跳过或 done 的情况
    state["user_supplements"] = answers
    state["pending_interrupt"] = None
    state["interrupted_by"] = "user"
    state["current_phase"] = "WAIT_USER_BRIEF"

    answered = sum(1 for a in answers if a is not None)
    skipped = sum(1 for a in answers if a is None)
    remaining_count = len(remaining)
    unresolved_risks = remaining_count > 0 or skipped > 0

    # ── 风险警告 ──
    if unresolved_risks:
        print("\n" + "!" * 60)
        print("⚠  司南提醒：以下风险尚未解决")
        print("!" * 60)

        if remaining_count > 0:
            print(f"\n  辩论中仍有 {remaining_count} 个未对齐的分歧：")
            for d in remaining:
                print(f"    ? {d}")

        if skipped > 0:
            print(f"\n  您跳过了 {skipped} 个必须回答的问题。")

        print("\n  这些未解决的问题可能会导致后续架构设计出现偏差。")
        print("\n  请选择后续处理方式：")
        print("    [proceed]  带着这些风险继续（不推荐）")
        print("    [abort]     退出，重新从头开始")
        print()

        while True:
            choice = input("    > ").strip().lower()
            if choice in ("proceed", "abort"):
                break
            print("    请输入 'proceed' 或 'abort'。")

        if choice == "abort":
            print("\n  已退出。请重新运行并认真回答这些问题后，再进入架构设计。")
            append_decision_log(state["run_id"], {
                "phase": "WAIT_USER_BRIEF",
                "type": "user_aborted",
                "content": "User chose to abort due to unresolved debate risks",
                "rationale": f"{remaining_count} remaining disagreements, {skipped} skipped questions",
                "risks": remaining,
            })
            raise KeyboardInterrupt("用户选择退出：辩论中存在未解决的关键分歧。")

        # 用户选择继续，记录风险
        append_decision_log(state["run_id"], {
            "phase": "WAIT_USER_BRIEF",
            "type": "user_proceeded_with_risks",
            "content": f"User chose to proceed despite {remaining_count} unresolved disagreements and {skipped} skipped questions",
            "rationale": "用户自愿承担风险，继续进入契约阶段",
            "risks": remaining,
        })
        state["gate_flags"]["flagged_risks"] = remaining

    append_progress_log(state["run_id"], "WAIT_USER_BRIEF",
                        f"User answered {answered}/{len(answers)} questions, {skipped} skipped, {remaining_count} remaining disagreements")
    append_decision_log(state["run_id"], {
        "phase": "WAIT_USER_BRIEF",
        "type": "user_input",
        "content": f"User answered {answered}/{len(answers)} debate questions",
    })

    return state
