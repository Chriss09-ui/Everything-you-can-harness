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
    # After the debate answers, sinan_approval walks the user through 7 sections
    # (each pauses for input) before collecting the final approve/reject/request_changes
    # decision. Section pauses consume any non-decision input; "approve" lands on the
    # final decision prompt.
    #
    # If sinan_debrief detects unresolved risks, an extra "proceed" is needed (after
    # the 4 debate answers, before the section pauses).
    inputs = iter([
        "大约每天10个任务",  # Q1
        "希望看到完整的架构图和每个节点描述",  # Q2
        "邮件告警即可",  # Q3
        "两周内可交付",   # Q4
        "proceed",        # sinan_debrief risk-proceed (only consumed if unresolved_risks)
        "",  # section pause — requirements
        "",  # section pause — architecture
        "",  # section pause — modules
        "",  # section pause — governance
        "",  # section pause — rationale
        "",  # section pause — reviews
        "",  # section pause — risks
        "approve",        # Final decision
    ])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

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
    # sinan_approval ran AFTER final_spec, so current_phase ends on SINAN_APPROVAL.
    assert final["current_phase"] == "SINAN_APPROVAL"

    draft = final["harness_design_draft"]
    assert draft["primary_goal"] != "未定义"
    assert draft["scope"]["inclusions"]
    assert draft["success_criteria"]
    assert draft["constraints"]
    assert draft["memory_module"].get("working_memory")
    assert draft["handoff_protocol"].get("handoff_points")
    assert draft["eval_placements"].get("eval_triggers")

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
