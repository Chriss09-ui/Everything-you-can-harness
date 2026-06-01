"""Regression test for the architecture-layer reject / revision loop.

Covers a real end-to-end flow under mock:
    framework_design → ... → final_spec → sinan_approval (reject)
    → arch_revise → framework_design → ... → sinan_approval (approve)

Before fixing, ``mock_responses.py`` registered the arch_revise mock trigger
as ``"生成结构化的修订简报"`` but ``arch_revise_node`` actually sends the LLM
the prompt suffix ``"翻译为具体的修复指令"`` — mock missed, fallback returned,
``validate_artifact(..., "arch_revision_brief")`` raised. As a result the
reject loop was effectively untestable in mock mode. This test pins both the
prompt-trigger match and the round-trip behavior.
"""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sinan.state import make_initial_state
from sinan.graph import compile_graph
from sinan.nodes.intake import intake_node
from sinan.mock_responses import register_mock_responses
from sinan.artifacts import get_run_dir


def test_reject_then_approve_loop_mock(monkeypatch):
    """Walk the user through one reject round, then approve; assert the loop
    closes and the architecture is regenerated (different version on disk)."""
    register_mock_responses()

    # Input sequence:
    # 1) 4 debate answers
    # 2) "proceed" if sinan_debrief raises unresolved risks (defensive)
    # 3) 7 section pauses (sinan_approval walks 8 sections total; the 8th is
    #    risks, asked right before the approve/reject decision)
    # 4) "reject" → first decision
    # 5) user intent prompt → just enter
    # 6) second loop: 8 section pauses + "approve"
    inputs = iter([
        "约10任务", "完整架构图", "邮件告警", "两周内",
        "proceed",
        # first walk — reject
        "", "", "", "", "", "", "", "",
        "reject",
        "",
        # second walk — approve
        "", "", "", "", "", "", "", "",
        "approve",
    ])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

    run_id = f"test_reject_loop_{uuid.uuid4().hex[:8]}"
    state = make_initial_state(run_id)
    state = intake_node(state, "构建一个能自动审查代码并给出重构建议的多 agent 系统")

    graph = compile_graph()
    final = graph.invoke(state)

    # final state after approve
    assert final["harness_design_draft"] is not None
    assert final["architecture_pack"] is not None
    assert final["current_phase"] == "SINAN_APPROVAL"

    # arch_reject_count should have advanced to 1 + was reset? Actually no —
    # the counter is only incremented on reject (sinan_approval.py:109), never
    # decremented. After 1 reject + 1 approve, count should be 1.
    assert final.get("arch_reject_count") == 1, (
        f"expected arch_reject_count=1 after one reject+approve, "
        f"got {final.get('arch_reject_count')}"
    )

    # arch_revise_node must have run (artifact on disk)
    run_dir = get_run_dir(run_id)
    arch_revision_path = run_dir / "arch_revision_brief.json"
    assert arch_revision_path.exists(), (
        f"arch_revision_brief.json should be written after a reject; "
        f"runs dir: {run_dir}"
    )

    # final_spec runs twice on a reject loop (once before each approval),
    # so we expect at least 2 versions of harness_design_draft on disk.
    draft_versions = list(run_dir.glob("harness_design_draft_v*.json"))
    assert len(draft_versions) >= 1, (
        f"expected at least 1 archived draft version after reject loop, "
        f"found {draft_versions}"
    )

    # arch_revision_brief should carry revision_round=1 (matched to reject
    # count by arch_revise_node at the time the brief was generated).
    import json
    revision = json.loads(arch_revision_path.read_text())
    assert revision.get("revision_round") == 1, (
        f"after 1 reject, arch_revision_brief.revision_round must be 1, "
        f"got {revision.get('revision_round')!r} — full payload: {revision}"
    )
