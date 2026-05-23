"""CLI entrypoint for 司南 Harness Builder."""
from __future__ import annotations
import uuid
import sys
from pathlib import Path

# Add src to path so tests can import sinan
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sinan.state import make_initial_state
from sinan.graph import compile_graph
from sinan.artifacts import (
    ensure_run_dir, append_progress_log, append_decision_log,
    update_run_state,
)
from sinan.nodes.intake import intake_node
from sinan.mock_responses import register_mock_responses
from sinan.coding.state import make_coding_state
from sinan.coding.graph import compile_coding_graph
from sinan.coding.mock_responses import register_coding_mock_responses


def main():
    # Register mock LLM responses (no-op if real LLM is configured)
    register_mock_responses()
    register_coding_mock_responses()

    print("=" * 60)
    print("司南 Harness Builder — V1 垂直切片")
    print("=" * 60)
    print()

    # Collect user input
    print("请描述你想构建的 agentic harness（用一段自然语言描述你的需求）：")
    print("示例：我想构建一个能自动审查代码并给出重构建议的多 agent 系统")
    print()
    user_input = input("> ").strip()
    if not user_input:
        print("输入为空，退出。")
        return

    # Initialize run
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    ensure_run_dir(run_id)
    append_progress_log(run_id, "SYSTEM", f"Run started: {run_id}")

    # Initialize state
    state = make_initial_state(run_id)
    state = intake_node(state, user_input)

    print(f"\nRun ID: {run_id}")
    print(f"开始处理您的需求...\n")

    # ── Phase 1: Design Layer ──
    graph = compile_graph()

    try:
        final_state = graph.invoke(state)
        print("\n" + "=" * 60)
        print("司南：设计稿生成完成")
        print("=" * 60)
        print(f"\n产出物目录: runs/{run_id}/")
        print(f"  - harness_design_final.md （最终设计稿）")
        print(f"  - requirement_pack.json （需求包）")
        print(f"  - architecture_pack.json （架构设计）")
        print(f"  - decision_log.md （决策日志）")
        print(f"  - progress_log.md （进度日志）")
    except Exception as e:
        print(f"\n设计层异常: {e}")
        append_decision_log(run_id, {
            "phase": "SYSTEM",
            "type": "error",
            "content": f"Design pipeline failed: {str(e)}",
        })
        raise

    # ── Phase 2: Coding Layer ──
    harness_draft = final_state.get("harness_design_draft") or {}

    print("\n" + "=" * 60)
    print("司南：进入研发层")
    print("=" * 60)

    coding_run_id = f"{run_id}_coding"
    ensure_run_dir(coding_run_id)
    coding_state = make_coding_state(coding_run_id, harness_draft)

    coding_graph = compile_coding_graph()

    try:
        coding_final = coding_graph.invoke(coding_state)
        print("\n" + "=" * 60)
        print("司南：研发层完成")
        print("=" * 60)
        sprint_result = coding_final.get("sprint_result") or {}
        print(f"\n总完成率: {sprint_result.get('completion_pct', 0)}%")
        print(f"产出目录: runs/{coding_run_id}/harness/")
        print(f"\n流程结束。")
    except Exception as e:
        print(f"\n研发层异常: {e}")
        append_decision_log(coding_run_id, {
            "phase": "SYSTEM",
            "type": "error",
            "content": f"Coding pipeline failed: {str(e)}",
        })
        raise


if __name__ == "__main__":
    main()
