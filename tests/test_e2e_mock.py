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

    # ── Deeper assertions: pin the architecture-debate actually ran ──
    # Without these, a regression that skips subagent_review or
    # framework_adjust could still pass the artifact-existence checks above
    # (because those nodes write to the same files whether or not they did
    # real work).
    import json
    arch_pack = json.loads((run_dir / "architecture_pack.json").read_text())
    # architecture_pack must have gone through zonggong_integrate (contains
    # the embedded ``design_evolution`` trace that node attaches).
    assert "design_evolution" in arch_pack, (
        f"architecture_pack missing design_evolution — zonggong_integrate "
        f"did not run or was short-circuited: {list(arch_pack.keys())[:8]}"
    )

    # Sub-agent outputs / reviews must carry all three agents. The wrapper
    # schema enforces this, but a regression that drops one agent should fail
    # here, not silently in production.
    subagent_outputs = json.loads((run_dir / "subagent_outputs.json").read_text())
    assert set(subagent_outputs.keys()) >= {"memory", "handoff", "eval"}, (
        f"subagent_outputs missing agents: {subagent_outputs.keys()}"
    )
    subagent_reviews = json.loads((run_dir / "subagent_reviews.json").read_text())
    assert set(subagent_reviews.keys()) >= {"memory", "handoff", "eval"}, (
        f"subagent_reviews missing agents: {subagent_reviews.keys()}"
    )

    # The framework_design.json on disk must reflect the post-adjustment
    # framework — i.e. ``framework_adjust`` must have overwritten the live
    # file. (Earlier bug: that node wrote to framework_design_v2.json
    # instead, leaving framework_design.json stuck on the Round-1 output.)
    framework = json.loads((run_dir / "framework_design.json").read_text())
    assert "nodes" in framework and "edges" in framework, (
        f"framework_design.json must look like a framework dict, got: "
        f"{list(framework.keys())[:6]}"
    )

    print(f"\n✅ E2E test passed. Artifacts in: {run_dir}")
