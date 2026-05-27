"""Smoke tests for the coding harness graph."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sinan.coding.state import make_coding_state, CodingState
from sinan.coding.graph import build_coding_graph, compile_coding_graph


def test_coding_graph_compiles():
    """Coding graph should compile without errors."""
    graph = compile_coding_graph()
    assert graph is not None


def test_coding_graph_has_expected_nodes():
    """Coding graph should contain all expected nodes (26 total)."""
    graph = compile_coding_graph()
    nodes = set(graph.nodes)
    # Original 17 + 10 new (5 init parallel + 4 read parallel + session_setup_exit + entry/exit split)
    expected = {
        "planner",
        "sprint_plan",
        "sprint_negotiate",
        "sprint_setup",
        "session_init",
        "init_progress",
        "init_script",
        "init_feature_list",
        "init_git",
        "init_loop_entry",
        "session_setup_entry",
        "session_setup_exit",
        "read_pwd",
        "read_progress",
        "read_feature_list",
        "read_git_log",
        "sanity_check",
        "bug_triage",
        "pick_feature",
        "implement_feature",
        "test_feature",
        "commit_feature",
        "evaluator_qa",
        "evaluator_bugs",
        "generator_fix",
        "sprint_complete",
    }
    assert expected.issubset(nodes), f"Missing nodes: {expected - nodes}"


def test_coding_state_factory():
    """make_coding_state should produce a valid initial state."""
    draft = {"primary_goal": "test harness"}
    state = make_coding_state("coding_test_001", draft)
    assert state["run_id"] == "coding_test_001"
    assert state["harness_design_draft"] == draft
    assert state["sprint_number"] == 1
    assert state["session_number"] == 1
    assert state["negotiate_round"] == 1
    assert state["fix_loop_count"] == 0
    assert state["current_phase"] == "CODING_INIT"


def test_coding_state_schema_fields():
    """CodingState should have all required fields."""
    draft = {}
    state: CodingState = make_coding_state("coding_test_002", draft)
    required_fields = [
        "run_id",
        "harness_design_draft",
        "current_phase",
        "sprint_number",
        "session_number",
        "negotiate_round",
        "fix_loop_count",
        "spec",
        "sprint_contract",
        "sprint_result",
        "feature_list",
        "current_feature_id",
        "current_feature_status",
        "test_result",
        "evaluator_grade",
        "bug_report",
        "last_good_commit",
        "session_progress_count",
        "decision_log",
        "progress_log",
        "messages",
    ]
    for field in required_fields:
        assert field in state, f"Missing field: {field}"
