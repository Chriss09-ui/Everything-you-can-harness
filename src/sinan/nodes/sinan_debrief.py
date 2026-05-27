"""sinan_debrief — 司南在辩论后与用户交互，收集问题答案。

Agent: 司南 (用户交互)
Layer: 需求层

Reads:
    state["brief_debate"]  — debate result with user_questions

Writes:
    state["user_supplements"]    — raw answer list
    state["user_brief_answers"]  — structured answer records
    state["pending_interrupt"]   — reset to None
    state["current_phase"]       — "WAIT_USER_BRIEF"

Artifacts:
    (none — interactive console node)

Routes:
    → brief_compile  (linear)
"""
from __future__ import annotations
from datetime import datetime, timezone
import json
from ..state import HarnessBuilderState
from ..llm import get_llm_client
from ..prompts import get_prompt
from ..artifacts import append_progress_log, append_decision_log, finalize_phase, load_state_or_file


def sinan_debrief_node(state: HarnessBuilderState) -> dict:
    """Collect user answers to debate questions after Tuopu-Jiewen debate."""
    update_run_state(state["run_id"], "SINAN_DEBRIEF")
    append_progress_log(state["run_id"], "SINAN_DEBRIEF", "Collecting user answers from debate")

    client = get_llm_client()
    system = get_prompt("sinan_interact")

    debate = load_state_or_file(state, "brief_debate")
    prompt_data = {
        "run_id": state["run_id"],
        "current_phase": state.get("current_phase", "unknown"),
        "interaction_type": "user_brief",
        "aligned_points": debate.get("aligned_points", []),
        "remaining_disagreements": debate.get("remaining_disagreements", []),
        "user_questions": debate.get("user_questions", []),
    }
    user = json.dumps(prompt_data, ensure_ascii=False, indent=2)

    raw = client.generate(system, user)
    response = _parse_response(raw)

    display = response.get("display", {})
    questions = display.get("user_questions", [])
    aligned = display.get("aligned_points", [])
    remaining = display.get("remaining_disagreements", [])

    print("\n" + "=" * 60)
    print("司南：" + display.get("header", "辩论已完成，请您填写以下信息"))
    print("=" * 60)

    if aligned:
        print(f"\n【已对齐的需求点】（{len(aligned)} 条）")
        for p in aligned:
            print(f"  ✓ {p}")

    if remaining:
        print(f"\n【仍存在分歧的点】（{len(remaining)} 条）")
        for d in remaining:
            print(f"  ? {d}")

    if questions:
        print(f"\n【需要您确认的问题】（{len(questions)} 条）")
        print(display.get("question_instruction", "请逐条回答（输入 'skip' 跳过，'done' 结束）："))

    answers = []
    answer_records = []
    for i, q in enumerate(questions, 1):
        print(f"\n  问题 {i}: {q}")
        while True:
            line = input("    > ").strip()
            if line.lower() in ("skip", "done", ""):
                answers.append(None)
                answer_records.append({
                    "question": q,
                    "answer": None,
                    "status": "skipped",
                    "answered_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                })
                print("    [已跳过]")
                break
            answers.append(line)
            answer_records.append({
                "question": q,
                "answer": line,
                "status": "answered",
                "answered_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            })
            break

    skipped = sum(1 for a in answers if a is None)
    unresolved_risks = len(remaining) > 0 or skipped > 0

    state["user_supplements"] = answers
    state["user_brief_answers"] = answer_records
    state["pending_interrupt"] = None
    state["current_phase"] = "SINAN_DEBRIEF"

    if unresolved_risks:
        print("\n" + "!" * 60)
        print("⚠  司南提醒：以下风险尚未解决")
        print("!" * 60)
        if remaining:
            print(f"\n  辩论中仍有 {len(remaining)} 个未对齐的分歧")
        if skipped > 0:
            print(f"\n  您跳过了 {skipped} 个必须回答的问题")
        print("\n  请选择：")
        print("    [proceed]  带着这些风险继续（不推荐）")
        print("    [abort]     退出，重新开始")
        print()

        while True:
            choice = input("    > ").strip().lower()
            if choice in ("proceed", "abort"):
                break
            print("    请输入 'proceed' 或 'abort'。")

        if choice == "abort":
            print("\n  已退出。请重新运行并认真回答这些问题。")
            append_decision_log(state["run_id"], {
                "phase": "SINAN_DEBRIEF",
                "type": "user_aborted",
                "content": "User aborted due to unresolved debate risks",
                "rationale": f"{len(remaining)} disagreements, {skipped} skipped",
                "risks": remaining,
            })
            raise SystemExit(
                "用户选择退出：辩论中存在未解决的关键分歧。"
            )

        append_decision_log(state["run_id"], {
            "phase": "SINAN_DEBRIEF",
            "type": "user_proceeded_with_risks",
            "content": f"User proceeded despite {len(remaining)} disagreements and {skipped} skipped",
            "risks": remaining,
        })
        state["gate_flags"]["flagged_risks"] = remaining
    else:
        append_decision_log(state["run_id"], {
            "phase": "SINAN_DEBRIEF",
            "type": "user_input",
            "content": f"All {len(answers)} debate questions answered",
        })

    answered = sum(1 for a in answers if a is not None)
    append_progress_log(
        state["run_id"], "WAIT_USER_BRIEF",
        f"User answered {answered}/{len(answers)} questions, {skipped} skipped"
    )
    finalize_phase(state["run_id"])
    return state


def update_run_state(run_id: str, phase: str) -> None:
    from ..artifacts import update_run_state as _update
    _update(run_id, phase)


def _parse_response(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        # Never silently short-circuit the user gate. Surface the failure so
        # the caller (and the run's decision log) can see what happened.
        raise ValueError(f"Failed to parse sinan_debrief LLM response: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("sinan_debrief LLM response is not a JSON object")
    return data
