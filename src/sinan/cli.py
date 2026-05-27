"""CLI entrypoint for 司南 Harness Builder.

Usage:
    python -m sinan.cli                       # full pipeline: design → coding
    python -m sinan.cli --from-brief <id>     # skip requirement layer; run
                                              # architecture + coding from
                                              # runs/<id>/user_brief_form.json
    python -m sinan.cli --from-design <id>    # skip design layer; resume coding
                                              # from runs/<id>/harness_design_draft.json
"""
from __future__ import annotations
import argparse
import json
import uuid
import sys
from pathlib import Path

# Add src to path so tests can import sinan
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sinan.state import make_initial_state
from sinan.graph import compile_graph, compile_architecture_graph
from sinan.artifacts import (
    ensure_run_dir, get_run_dir, append_progress_log, append_decision_log,
    update_run_state,
)
from sinan.validation import validate_artifact
from sinan.nodes.intake import intake_node
from sinan.mock_responses import register_mock_responses
from sinan.coding.state import make_coding_state
from sinan.coding.graph import compile_coding_graph
from sinan.coding.mock_responses import register_coding_mock_responses


def main():
    parser = argparse.ArgumentParser(description="司南 Harness Builder")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--from-brief",
        metavar="RUN_ID",
        help="Skip requirement layer; run architecture + coding layers from "
             "runs/<RUN_ID>/user_brief_form.json",
    )
    group.add_argument(
        "--from-design",
        metavar="RUN_ID",
        help="Skip design layer; resume coding layer from "
             "runs/<RUN_ID>/harness_design_draft.json",
    )
    args = parser.parse_args()

    # Register mock LLM responses (no-op if real LLM is configured)
    register_mock_responses()
    register_coding_mock_responses()

    print("=" * 60)
    print("司南 Harness Builder — V1 垂直切片")
    print("=" * 60)
    print()

    if args.from_design:
        run_id = args.from_design
        draft_path = get_run_dir(run_id) / "harness_design_draft.json"
        if not draft_path.exists():
            print(f"找不到设计稿: {draft_path}")
            print("请先跑完整流程，或检查 run_id 是否正确。")
            sys.exit(1)
        with open(draft_path, encoding="utf-8") as f:
            draft = json.load(f)
        try:
            validate_artifact(draft, "harness_design_draft")
        except ValueError as e:
            print(f"设计稿 schema 校验失败，无法恢复: {e}")
            print("请重新跑完整流程以生成合法的设计稿。")
            sys.exit(1)
        print(f"从 run_id={run_id} 的设计稿恢复，跳过设计层。")
        _run_coding_layer(run_id, harness_draft=draft)
        return

    if args.from_brief:
        run_id = args.from_brief
        brief_path = get_run_dir(run_id) / "user_brief_form.json"
        if not brief_path.exists():
            print(f"找不到需求契约: {brief_path}")
            print("请先跑过需求层一次，或检查 run_id 是否正确。")
            sys.exit(1)
        with open(brief_path, encoding="utf-8") as f:
            brief = json.load(f)
        try:
            validate_artifact(brief, "user_brief_form")
        except ValueError as e:
            print(f"需求契约 schema 校验失败: {e}")
            print("请重新跑需求层以生成合法契约。")
            sys.exit(1)
        print(f"从 run_id={run_id} 的需求契约恢复，跳过需求层。")
        _run_architecture_then_coding(run_id, brief_path)
        return

    # ── Full pipeline ──

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
    _run_coding_layer(run_id, harness_draft)


def _run_architecture_then_coding(run_id: str, brief_path: Path) -> None:
    """Skip the requirement layer; run architecture + coding from an existing brief."""
    with open(brief_path, encoding="utf-8") as f:
        brief = json.load(f)

    state = make_initial_state(run_id)
    state["user_brief_form"] = brief
    # Use a resume-specific phase rather than the requirement-layer exit
    # phase — the next node is framework_design, not brief_compile.
    state["current_phase"] = "ARCHITECTURE_RESUME"

    # Carry forward prior reject count so resume doesn't gift the user 3 fresh
    # rejections on every --from-brief. Counted from decision_log.md entries
    # written by sinan_approval_node (those are the durable audit trail).
    prior_rejects = _count_arch_rejects(run_id)
    if prior_rejects > 0:
        state["arch_reject_count"] = prior_rejects
        print(f"恢复架构层，已累计 {prior_rejects}/3 次拒绝。")

    append_progress_log(run_id, "SYSTEM",
        f"Resumed at architecture layer from {brief_path.name}")

    print(f"开始重跑架构层 + 研发层...\n")

    graph = compile_architecture_graph()
    try:
        final_state = graph.invoke(state)
        print("\n" + "=" * 60)
        print("司南：架构层完成")
        print("=" * 60)
    except Exception as e:
        print(f"\n架构层异常: {e}")
        append_decision_log(run_id, {
            "phase": "SYSTEM",
            "type": "error",
            "content": f"Architecture pipeline failed: {str(e)}",
        })
        raise

    harness_draft = final_state.get("harness_design_draft") or {}
    _run_coding_layer(run_id, harness_draft)


def _count_arch_rejects(run_id: str) -> int:
    """Count prior SINAN_APPROVAL rejects from decision_log.md.

    Each reject / request_changes appends a line like
    ``## [timestamp] SINAN_APPROVAL | user_reject`` (or user_request_changes).
    """
    log_path = get_run_dir(run_id) / "decision_log.md"
    if not log_path.exists():
        return 0
    try:
        with open(log_path, encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return 0
    count = 0
    for line in content.splitlines():
        # Match "## [ts] SINAN_APPROVAL | user_reject" / "user_request_changes"
        if "SINAN_APPROVAL" in line and (
            "user_reject" in line or "user_request_changes" in line
        ):
            count += 1
    return count


def _run_coding_layer(run_id: str, harness_draft: dict) -> None:
    """Run the coding layer against runs/<run_id>/.

    Coding artifacts go into runs/<run_id>/harness/. The draft is passed via
    state when available; otherwise the planner falls back to reading
    runs/<run_id>/harness_design_draft.json from disk.
    """
    print("\n" + "=" * 60)
    print("司南：进入研发层")
    print("=" * 60)

    ensure_run_dir(run_id)
    coding_state = make_coding_state(run_id, harness_draft)
    coding_graph = compile_coding_graph()

    try:
        coding_final = coding_graph.invoke(coding_state)
        print("\n" + "=" * 60)
        print("司南：研发层完成")
        print("=" * 60)
        sprint_result = coding_final.get("sprint_result") or {}
        print(f"\n总完成率: {sprint_result.get('completion_pct', 0)}%")
        print(f"产出目录: runs/{run_id}/harness/")
        print(f"\n流程结束。")
    except Exception as e:
        print(f"\n研发层异常: {e}")
        append_decision_log(run_id, {
            "phase": "SYSTEM",
            "type": "error",
            "content": f"Coding pipeline failed: {str(e)}",
        })
        raise


if __name__ == "__main__":
    main()
