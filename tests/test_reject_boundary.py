"""Boundary test for the architecture reject loop.

The ``_approval_outcome_router`` (graph.py) is supposed to allow the user
3 reject rounds and raise on the 4th. An earlier off-by-one bug in that
router raised on the 3rd reject, so users only ever got 2 rounds. This
test pins all four boundary cases:

  - 1 reject → arch_revise fires (round 1)
  - 2 rejects → arch_revise fires (round 2)
  - 3 rejects → arch_revise fires (round 3 — the doc'd max)
  - 4 rejects → RuntimeError raised by the router

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
    """This is the documented max — 3 revisions must all run arch_revise
    successfully before a 4th reject would raise."""
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


def test_fourth_reject_raises_runtime_error(monkeypatch):
    """The 4th reject must raise, but the 3rd revise must have happened
    before it did — otherwise we're only allowing 2 real rounds."""
    register_mock_responses()
    run_id = f"boundary_4r_{uuid.uuid4().hex[:6]}"
    state = make_initial_state(run_id)
    state = intake_node(state, "demo system")
    builtins_input = iter(_build_inputs(4))
    monkeypatch.setattr("builtins.input", lambda p="": next(builtins_input))

    with pytest.raises(RuntimeError, match="rejected 4 times"):
        _run_with_silent_stdout(state)

    # The 3 allowed rounds actually happened — disk holds round-3 brief.
    run_dir = get_run_dir(run_id)
    import json
    revision = json.loads((run_dir / "arch_revision_brief.json").read_text())
    assert revision.get("revision_round") == 3, (
        f"router raised before round 3's revision_brief was written; "
        f"off-by-one bug likely: revision_round = {revision.get('revision_round')}"
    )
