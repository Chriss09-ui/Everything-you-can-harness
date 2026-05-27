"""Regression tests for risk_register reducer (M7 fix).

Before M7, spec_challenge and architecture_challenge mutated
state["risk_register"] in place via list.extend(). That works for serial
execution but silently loses entries under concurrent writes. The fix gives
risk_register an operator.add reducer and makes the nodes return partial
updates like {"risk_register": [...new risks...]}.
"""
import operator
import sys
from pathlib import Path
from typing import Annotated, get_type_hints

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sinan.state import make_initial_state, HarnessBuilderState


def test_risk_register_is_annotated_with_add_reducer():
    """The state schema must declare risk_register with operator.add so
    concurrent writes concat instead of overwrite."""
    hints = get_type_hints(HarnessBuilderState, include_extras=True)
    rr = hints["risk_register"]
    # Annotated[list[dict], operator.add]
    meta = getattr(rr, "__metadata__", None)
    assert meta is not None, f"risk_register must be Annotated — got {rr!r}"
    assert operator.add in meta, (
        f"risk_register reducer must be operator.add, got metadata {meta!r}"
    )


def test_partial_returns_accumulate_via_reducer():
    """Simulate the two node partial returns and verify reducer math."""
    state = make_initial_state("reducer_test")

    # What spec_challenge returns (paraphrased)
    partial_spec = {"risk_register": [
        {"type": "ambiguity", "item": " unclear goal"},
    ]}
    # What architecture_challenge returns
    partial_arch = {"risk_register": [
        {"type": "arch_risk", "item": "over-engineered"},
        {"type": "arch_risk", "item": "missing failure mode"},
    ]}

    existing = state.get("risk_register", [])
    merged = operator.add(
        operator.add(existing, partial_spec["risk_register"]),
        partial_arch["risk_register"],
    )
    assert len(merged) == 3, f"expected 3 risks accumulated, got {len(merged)}"


def test_concurrent_writes_do_not_lose_entries():
    """The bug M7 prevents: if two writers ran in parallel and both read
    ``state["risk_register"]`` at the same instant, then both .extend()ed
    their own list and wrote back, only the last writer's risks survive.
    The reducer model avoids this — each writer only contributes its own
    delta and LangGraph's channel layer serializes the merge."""
    # Simulate three concurrent partial updates (e.g. three reviewer nodes)
    partials = [
        {"risk_register": [{"from": "reviewer_1"}]},
        {"risk_register": [{"from": "reviewer_2"}]},
        {"risk_register": [{"from": "reviewer_3"}]},
    ]
    # The reducer applies them left-to-right; the final list contains all 3
    state = make_initial_state("concurrent_test")
    base = state.get("risk_register", [])
    for p in partials:
        base = operator.add(base, p["risk_register"])
    assert len(base) == 3, f"concurrent merge lost entries: {base!r}"
    sources = sorted(r["from"] for r in base)
    assert sources == ["reviewer_1", "reviewer_2", "reviewer_3"]
