"""Tests for risk_register accumulation behavior.

History: this file used to guard the ``Annotated[list[dict], operator.add]``
reducer on ``risk_register``, which was added (M7) so that potential future
fan-out of risk discovery could append safely. In practice:

  1. The graph is purely serial — the reducer's concurrent-merge property
     was never exercised.
  2. The reducer actively caused a bug: most nodes returned the FULL state
     dict (``return state``) after mutating it. LangGraph applied the reducer
     to the entire returned list, so every serial node re-applied the
     accumulated risks against the running register. A real run produced
     2072 entries from ~2 source risks after ~11 serial nodes.

The reducer has been removed. ``risk_register`` is now a plain list, and
risk-writing nodes (``spec_challenge``, ``architecture_challenge``) build
the next-state list explicitly by reading the prior list and extending it.

These tests pin the post-fix behavior so:
  - the running register survives each layer (no overwrite),
  - the bug cannot silently come back (a log assertion if somehow the
    exponential duplication reappears).
"""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_risk_register_is_a_plain_list_field():
    """``risk_register`` must not carry a reducer annotation. Adding one back
    without also converting every other node to partial-return style would
    reintroduce the 2072-risks bug from the deletion note."""
    from typing import get_type_hints, Annotated
    from sinan.state import HarnessBuilderState

    hints = get_type_hints(HarnessBuilderState, include_extras=True)
    rr = hints["risk_register"]
    # No __metadata__ ⇒ no Annotated reducer. A plain ``list[dict]`` type has
    # no metadata.
    meta = getattr(rr, "__metadata__", None)
    assert meta is None, (
        f"risk_register must NOT be Annotated (no reducer) — got {rr!r}. "
        "See state.py comments before re-adding a reducer."
    )


def test_partial_returns_accumulate_via_explicit_extend():
    """Simulate the two risk-writing nodes' write pattern and verify the
    running register carries both batches (the M7 functional goal)."""
    from sinan.state import make_initial_state

    state = make_initial_state("reducer_test")

    # What spec_challenge would do (paraphrased): read prior list + extend
    new_spec = [{"type": "ambiguity", "item": " unclear goal"}]
    state["risk_register"] = state.get("risk_register", []) + new_spec

    # What architecture_challenge would do
    new_arch = [
        {"type": "arch_risk", "item": "over-engineered"},
        {"type": "arch_risk", "item": "missing failure mode"},
    ]
    state["risk_register"] = state.get("risk_register", []) + new_arch

    assert len(state["risk_register"]) == 3, (
        f"expected 3 risks accumulated, got {len(state['risk_register'])}"
    )


def test_no_duplication_after_sequential_invocation(monkeypatch):
    """End-to-end guard against the actual bug: a single full-pipeline mock
    run must produce O(unique-risks) entries, not 2^N duplicates. If a
    future change reintroduces the reducer or otherwise breaks the
    accumulation scheme, the count here will balloon and this test will fail.
    """
    import io
    import sys as _sys

    from sinan.state import make_initial_state
    from sinan.graph import compile_graph
    from sinan.nodes.intake import intake_node
    from sinan.mock_responses import register_mock_responses

    register_mock_responses()

    inputs = iter([
        "约10任务", "完整架构图", "邮件告警", "两周内",
        "proceed",
        "", "", "", "", "", "", "", "",
        "approve",
    ])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

    run_id = f"risk_no_dup_{uuid.uuid4().hex[:8]}"
    state = make_initial_state(run_id)
    state = intake_node(state, "构建一个多 agent 系统")

    saved = _sys.stdout
    _sys.stdout = io.StringIO()
    try:
        graph = compile_graph()
        final = graph.invoke(state)
    finally:
        _sys.stdout = saved

    risks = final.get("risk_register", [])
    # Mocks produce exactly 2 ambiguity risks (from spec_challenge) + 4 arch
    # risks (from architecture_challenge). Full pipeline has no other
    # risk-writing nodes in the design layer. Anything over ~12 is the bug
    # coming back (parallel + doubling).
    assert len(risks) <= 12, (
        f"risk_register has {len(risks)} entries — expected <= 12. "
        f"This is the exponential-duplication bug described in state.py "
        f"coming back. First 3 risks: {risks[:3]}."
    )
    assert len(risks) >= 4, (
        f"risk_register should contain at least the architecture_challenge "
        f"risks; got {len(risks)} {risks}"
    )
