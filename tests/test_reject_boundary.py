"""Boundary tests for the architecture reject loop.

The ``_approval_outcome_router`` (graph.py) has **no hard cap on reject
rounds** — the user can keep choosing ``reject`` / ``request_changes`` and
the loop will keep regenerating until they explicitly pick ``approve`` or
``abort``. This file pins:

  - 1 reject → arch_revise fires (round 1)
  - 2 rejects → arch_revise fires (round 2)
  - 3 rejects → arch_revise fires (round 3)
  - 4 rejects → arch_revise STILL fires (no cap; previously raised here)
  - abort → graph ends gracefully without entering arch_revise

We exercise the actual compiled graph end-to-end so that the test only
passes when sinan_approval, arch_revise, framework_design (with revision
context), and the router all coordinate correctly.
"""
import io
import sys
import uuid

import pytest

from sinan.state import make_initial_state
from sinan.graph import compile_graph
from sinan.nodes.intake import intake_node
from sinan.mock_responses import register_mock_responses
from sinan.artifacts import get_run_dir


def _build_inputs(reject_count: int):
    """Build the input() stream for N reject rounds followed by an approve."""
    base = ["约10任务", "完整架构图", "邮件告警", "两周内", "proceed"]
    for _ in range(reject_count):
        # 8 section pauses (sinan_approval _build_sections returns 8) + reject
        # + user_intent follow-up (just empty string).
        base.extend([""] * 8 + ["reject", ""])
    # Final approve: 8 more pauses then "approve".
    base.extend([""] * 8 + ["approve"])
    return iter(base)


def _run_with_silent_stdout(state):
    """Run graph.invoke with print output discarded.

    Uses os.devnull instead of io.StringIO — under pytest, redirecting to a
    StringIO that's never read can interact badly with the capsys/capture
    machinery and stall the run. Writing to a real file (even /dev/null)
    keeps the print callside simple and avoids any buffering surprises.
    """
    import os
    devnull = open(os.devnull, "w")
    saved = sys.stdout
    sys.stdout = devnull
    try:
        return compile_graph().invoke(state)
    finally:
        sys.stdout = saved
        devnull.close()


def test_one_reject_then_approve_completes(monkeypatch):
    register_mock_responses()
    run_id = f"boundary_1r_{uuid.uuid4().hex[:6]}"
    state = make_initial_state(run_id)
    state = intake_node(state, "demo system")
    builtins_input = iter(_build_inputs(1))
    monkeypatch.setattr("builtins.input", lambda p="": next(builtins_input))
    final = _run_with_silent_stdout(state)
    assert final["arch_reject_count"] == 1
    assert final["harness_design_draft"] is not None


def test_two_rejects_then_approve_completes(monkeypatch):
    register_mock_responses()
    run_id = f"boundary_2r_{uuid.uuid4().hex[:6]}"
    state = make_initial_state(run_id)
    state = intake_node(state, "demo system")
    builtins_input = iter(_build_inputs(2))
    monkeypatch.setattr("builtins.input", lambda p="": next(builtins_input))
    final = _run_with_silent_stdout(state)
    assert final["arch_reject_count"] == 2
    # arch_revision_brief should have been written at least once per reject
    run_dir = get_run_dir(run_id)
    assert (run_dir / "arch_revision_brief.json").exists()


def test_three_rejects_then_approve_completes(monkeypatch):
    """3 reject rounds in a row, then approve — all three arch_revise rounds
    must run and the loop must close cleanly."""
    register_mock_responses()
    run_id = f"boundary_3r_{uuid.uuid4().hex[:6]}"
    state = make_initial_state(run_id)
    state = intake_node(state, "demo system")
    builtins_input = iter(_build_inputs(3))
    monkeypatch.setattr("builtins.input", lambda p="": next(builtins_input))
    final = _run_with_silent_stdout(state)
    assert final["arch_reject_count"] == 3
    # Should have archived older revision briefs
    run_dir = get_run_dir(run_id)
    arch_rev_path = run_dir / "arch_revision_brief.json"
    assert arch_rev_path.exists()
    import json
    revision = json.loads(arch_rev_path.read_text())
    assert revision.get("revision_round") == 3, (
        f"after 3 rejects, latest revision_round should be 3, "
        f"got {revision.get('revision_round')}"
    )


def test_fourth_reject_still_revises_no_cap(monkeypatch):
    """No hard cap: the 4th reject must STILL fire arch_revise, not raise.

    The user keeps revising until they explicitly approve or abort. Previously
    this test pinned a 3-round cap (4th reject raised RuntimeError); that cap
    was removed because it was an arbitrary halt that surprised users — see
    docs/architecture_layer.md for the new contract.
    """
    register_mock_responses()
    run_id = f"boundary_4r_{uuid.uuid4().hex[:6]}"
    state = make_initial_state(run_id)
    state = intake_node(state, "demo system")
    # 4 rejects then approve — must complete without raising.
    builtins_input = iter(_build_inputs(4))
    monkeypatch.setattr("builtins.input", lambda p="": next(builtins_input))

    final = _run_with_silent_stdout(state)

    assert final["arch_reject_count"] == 4, (
        f"4 rejects should result in arch_reject_count=4, "
        f"got {final.get('arch_reject_count')}"
    )
    # All 4 revise rounds must have written briefs.
    run_dir = get_run_dir(run_id)
    import json
    revision = json.loads((run_dir / "arch_revision_brief.json").read_text())
    assert revision.get("revision_round") == 4, (
        f"after 4 rejects, latest revision_round must be 4, "
        f"got {revision.get('revision_round')}"
    )


def test_abort_ends_gracefully_without_revise(monkeypatch):
    """Picking ``abort`` in sinan_approval must end the graph cleanly —
    no arch_revise, no RuntimeError, draft stays on disk for later resume."""
    register_mock_responses()
    run_id = f"boundary_abort_{uuid.uuid4().hex[:6]}"
    state = make_initial_state(run_id)
    state = intake_node(state, "demo system")

    # 5 debate answers, then 8 section pauses, then "abort" (no user_intent
    # follow-up since abort doesn't ask for one).
    inputs = iter([
        "约10任务", "完整架构图", "邮件告警", "两周内", "proceed",
        "", "", "", "", "", "", "", "",
        "abort",
    ])
    monkeypatch.setattr("builtins.input", lambda p="": next(inputs))

    final = _run_with_silent_stdout(state)

    # abort must NOT increment reject count
    assert final.get("arch_reject_count", 0) == 0
    # final draft is still on disk (final_spec ran before the abort)
    run_dir = get_run_dir(run_id)
    assert (run_dir / "harness_design_draft.json").exists()
    assert (run_dir / "harness_design_final.md").exists()
    # arch_revise must NOT have run on the abort path
    assert not (run_dir / "arch_revision_brief.json").exists(), (
        "arch_revise wrote a brief — abort should bypass it entirely"
    )
    # resume_payload records the abort
    assert (final.get("resume_payload") or {}).get("approval") == "abort"


def test_reject_then_abort_keeps_partial_progress(monkeypatch):
    """User rejects once (revise runs), then aborts: arch_reject_count=1,
    arch_revise wrote 1 brief, and the loop ends gracefully on abort."""
    register_mock_responses()
    run_id = f"boundary_rej_abort_{uuid.uuid4().hex[:6]}"
    state = make_initial_state(run_id)
    state = intake_node(state, "demo system")

    inputs = iter([
        "约10任务", "完整架构图", "邮件告警", "两周内", "proceed",
        # First walk — reject
        "", "", "", "", "", "", "", "",
        "reject",
        "",
        # Second walk — abort
        "", "", "", "", "", "", "", "",
        "abort",
    ])
    monkeypatch.setattr("builtins.input", lambda p="": next(inputs))

    final = _run_with_silent_stdout(state)

    assert final["arch_reject_count"] == 1
    run_dir = get_run_dir(run_id)
    # The single revise round ran
    import json
    assert (run_dir / "arch_revision_brief.json").exists()
    revision = json.loads((run_dir / "arch_revision_brief.json").read_text())
    assert revision.get("revision_round") == 1
    # And we ended on abort, not approve
    assert (final.get("resume_payload") or {}).get("approval") == "abort"
