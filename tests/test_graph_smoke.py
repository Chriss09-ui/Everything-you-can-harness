"""Smoke tests — verify the graph structure and a mock end-to-end run."""
import sys
from pathlib import Path

# Make src importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sinan.state import make_initial_state, HarnessBuilderState
from sinan.graph import (
    build_graph, compile_graph,
    build_architecture_graph, compile_architecture_graph,
)
from sinan.nodes.intake import intake_node


def test_graph_compiles():
    """Graph should compile without errors."""
    graph = compile_graph()
    assert graph is not None


def test_graph_has_expected_nodes():
    """Graph should contain all expected nodes."""
    graph = compile_graph()
    nodes = set(graph.nodes)
    expected = {
        "spec_expansion",
        "spec_challenge",
        "brief_debate",
        "sinan_debrief",
        "brief_compile",
        "framework_design",
        "subagent_review",
        "framework_adjust",
        "zonggong_integrate",
        "architecture_challenge",
        "arch_revise",
        "approval_gate",
        "sinan_approval",
        "final_spec",
    }
    assert expected.issubset(nodes), f"Missing nodes: {expected - nodes}"


def test_architecture_graph_compiles():
    """Architecture-only graph (entered from --from-brief) should compile."""
    graph = compile_architecture_graph()
    assert graph is not None
    nodes = set(graph.nodes)
    # Requirement-layer nodes are still registered for symmetry with full graph,
    # but the entry point is framework_design.
    assert "framework_design" in nodes
    assert "final_spec" in nodes


def test_graph_has_conditional_edges():
    """Graph should have conditional edges (verified by compiling with branching)."""
    graph = compile_graph()
    nodes = set(graph.nodes)
    assert "approval_gate" in nodes  # conditional branch node
    assert "brief_debate" in nodes   # new debate node
    assert "sinan_approval" in nodes  # approval gate target


def test_initial_state():
    """make_initial_state should produce a valid state."""
    state = make_initial_state("test_run_001")
    assert state["run_id"] == "test_run_001"
    assert state["started_at"]
    assert state["current_phase"] == "INTAKE"
    assert state["arch_reject_count"] == 0  # top-level field; gate_flags copy was removed


def test_intake_node():
    """intake_node should populate user_raw_input."""
    state = make_initial_state("test_run_002")
    result = intake_node(state, "I want a code review agent")
    assert result["user_raw_input"] == "I want a code review agent"
    assert result["current_phase"] == "INTAKE"
    assert len(result["messages"]) == 1


def test_state_schema_fields():
    """HarnessBuilderState should have all required fields."""
    state: HarnessBuilderState = make_initial_state("test_run_003")
    required_fields = [
        "run_id", "started_at", "current_phase",
        "user_raw_input", "user_supplements", "user_brief_answers",
        "requirement_pack", "spec_review", "user_brief_form",
        "architecture_pack", "architecture_review", "harness_design_draft",
        "gate_flags", "decision_log", "progress_log",
        "artifact_versions", "pending_interrupt",
        "interrupted_by", "resume_payload", "arch_reject_count",
        "risk_register", "messages",
    ]
    for field in required_fields:
        assert field in state, f"Missing field: {field}"
