"""End-to-end mock test — runs the full pipeline with mock LLM, no user input."""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sinan.state import make_initial_state
from sinan.graph import compile_graph
from sinan.nodes.intake import intake_node
from sinan.mock_responses import register_mock_responses
from sinan.artifacts import get_run_dir


def test_full_pipeline_mock(monkeypatch):
    """Full pipeline with mock LLM — no real API calls, no user input needed."""
    register_mock_responses()

    # Mock input() calls to auto-respond.
    # Provide all four debate answers so the run does not enter the proceed/abort loop.
    inputs = iter([
        "大约每天10个任务",  # Q1: daily task volume
        "希望看到完整的架构图和每个节点描述",  # Q2: approval detail level
        "邮件告警即可",  # Q3: failure notification
        "两周内可交付",   # Q4: timeline expectation
        "approve",        # Approval gate: approve
    ])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs, "done"))

    run_id = f"test_e2e_{uuid.uuid4().hex[:8]}"
    state = make_initial_state(run_id)
    state = intake_node(state, "我想构建一个能自动审查代码并给出重构建议的多 agent 系统")

    graph = compile_graph()
    final = graph.invoke(state)

    # Verify key artifacts were produced
    assert final["requirement_pack"] is not None
    assert final["spec_review"] is not None
    assert final["architecture_pack"] is not None
    assert final["architecture_review"] is not None
    assert final["harness_design_draft"] is not None
    assert final["current_phase"] == "FINAL_SPEC"

    # Verify files on disk
    run_dir = get_run_dir(run_id)
    assert (run_dir / "requirement_pack.json").exists()
    assert (run_dir / "spec_review.json").exists()
    assert (run_dir / "brief_debate.json").exists()
    assert (run_dir / "architecture_pack.json").exists()
    assert (run_dir / "architecture_review.json").exists()
    assert (run_dir / "harness_design_draft.json").exists()
    assert (run_dir / "harness_design_final.md").exists()
    assert (run_dir / "run_state.yaml").exists()
    assert (run_dir / "decision_log.md").exists()
    assert (run_dir / "progress_log.md").exists()

    print(f"\n✅ E2E test passed. Artifacts in: {run_dir}")
