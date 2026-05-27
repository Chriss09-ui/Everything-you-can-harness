"""LangGraph workflow assembly for the Coding Harness."""
from __future__ import annotations
from typing import Annotated, Any
import operator
from langgraph.graph import StateGraph, END
from langgraph.types import Send
from .state import CodingState
from .nodes import (
    planner,
    sprint_plan,
    sprint_negotiate,
    sprint_setup,
    session_init,
    # Init parallel branches (5 nodes)
    init_progress,
    init_script,
    init_feature_list,
    init_git,
    init_loop_entry,
    # Session setup (entry + exit + 4 parallel reads)
    session_setup,
    read_pwd,
    read_progress,
    read_feature_list,
    read_git_log,
    sanity_check,
    bug_triage,
    pick_feature,
    implement_feature,
    test_feature,
    commit_feature,
    generator_review,
    evaluator_qa,
    evaluator_bugs,
    generator_fix,
    sprint_complete,
)


def build_coding_graph() -> StateGraph:
    """Build and return the Coding Harness StateGraph."""
    g = StateGraph(CodingState)

    # ── Register all nodes ──

    # Planning
    g.add_node("planner", _wrap(planner.planner_node))

    # Sprint planning loop
    g.add_node("sprint_plan", _wrap(sprint_plan.sprint_plan_node))
    g.add_node("sprint_negotiate", _wrap(sprint_negotiate.sprint_negotiate_node))
    g.add_node("sprint_setup", _wrap(sprint_setup.sprint_setup_node))

    # Session entry
    g.add_node("session_init", _wrap(session_init.session_init_node))

    # Init parallel fan-out (5 nodes, Sprint 1 only)
    g.add_node("init_progress", _wrap(init_progress.init_progress_node))
    g.add_node("init_script", _wrap(init_script.init_script_node))
    g.add_node("init_feature_list", _wrap(init_feature_list.init_feature_list_node))
    g.add_node("init_git", _wrap(init_git.init_git_node))
    g.add_node("init_loop_entry", _wrap(init_loop_entry.init_loop_entry_node))

    # Session setup (entry + 4 parallel reads + exit)
    g.add_node("session_setup_entry", _wrap(session_setup.session_setup_entry_node))
    g.add_node("session_setup_exit", _wrap(session_setup.session_setup_exit_node))
    g.add_node("read_pwd", _wrap(read_pwd.read_pwd_node))
    g.add_node("read_progress", _wrap(read_progress.read_progress_node))
    g.add_node("read_feature_list", _wrap(read_feature_list.read_feature_list_node))
    g.add_node("read_git_log", _wrap(read_git_log.read_git_log_node))

    # Feature loop
    g.add_node("sanity_check", _wrap(sanity_check.sanity_check_node))
    g.add_node("bug_triage", _wrap(bug_triage.bug_triage_node))
    g.add_node("pick_feature", _wrap(pick_feature.pick_feature_node))
    g.add_node("implement_feature", _wrap(implement_feature.implement_feature_node))
    g.add_node("test_feature", _wrap(test_feature.test_feature_node))
    g.add_node("commit_feature", _wrap(commit_feature.commit_feature_node))

    # Sprint review
    g.add_node("generator_review", _wrap(generator_review.generator_review_node))
    g.add_node("evaluator_qa", _wrap(evaluator_qa.evaluator_qa_node))
    g.add_node("evaluator_bugs", _wrap(evaluator_bugs.evaluator_bugs_node))

    # Fix loop
    g.add_node("generator_fix", _wrap(generator_fix.generator_fix_node))

    # Sprint completion
    g.add_node("sprint_complete", _wrap(sprint_complete.sprint_complete_node))

    # ── Entry point ──
    g.set_entry_point("planner")

    # ── Linear edges ──
    g.add_edge("planner", "sprint_plan")
    g.add_edge("sprint_plan", "sprint_negotiate")
    g.add_edge("sprint_setup", "session_init")
    g.add_edge("generator_review", "evaluator_qa")
    g.add_edge("implement_feature", "test_feature")

    # ── Session init: Sprint 1 → 5 parallel init branches (via Send) ──
    g.add_conditional_edges(
        "session_init",
        _session_init_fanout,
        ["init_progress", "init_script", "init_feature_list", "init_git",
         "init_loop_entry", "session_setup_entry"],
    )

    # 5 parallel init nodes fan-in to session_setup_entry
    for node in ["init_progress", "init_script", "init_feature_list", "init_git", "init_loop_entry"]:
        g.add_edge(node, "session_setup_entry")

    # ── Session setup: 4 parallel context reads (via Send) ──
    g.add_conditional_edges(
        "session_setup_entry",
        _session_setup_fanout,
        ["read_pwd", "read_progress", "read_feature_list", "read_git_log"],
    )

    # 4 parallel read nodes fan-in to session_setup_exit
    for node in ["read_pwd", "read_progress", "read_feature_list", "read_git_log"]:
        g.add_edge(node, "session_setup_exit")

    g.add_edge("session_setup_exit", "sanity_check")

    # bug_triage re-enters sanity_check directly (context already loaded)
    g.add_edge("bug_triage", "sanity_check")

    # ── pick_feature routing ──
    g.add_conditional_edges(
        "pick_feature",
        _pick_feature_router,
        {
            "implement_feature": "implement_feature",
            "generator_review": "generator_review",
        },
    )

    # ── Sprint negotiation loop ──
    g.add_conditional_edges(
        "sprint_negotiate",
        _sprint_negotiate_router,
        {
            "sprint_setup": "sprint_setup",
            "sprint_plan": "sprint_plan",
        },
    )

    # ── Session loop ──
    g.add_conditional_edges(
        "sanity_check",
        _sanity_check_router,
        {
            "pick_feature": "pick_feature",
            "bug_triage": "bug_triage",
        },
    )

    # ── Feature loop ──
    g.add_conditional_edges(
        "test_feature",
        _test_feature_router,
        {
            "commit_feature": "commit_feature",
            "implement_feature": "implement_feature",
        },
    )

    g.add_conditional_edges(
        "commit_feature",
        _commit_feature_router,
        {
            "pick_feature": "pick_feature",
            "generator_review": "generator_review",
        },
    )

    # ── QA loop ──
    g.add_conditional_edges(
        "evaluator_qa",
        _evaluator_qa_router,
        {
            "sprint_complete": "sprint_complete",
            "evaluator_bugs": "evaluator_bugs",
        },
    )

    g.add_conditional_edges(
        "evaluator_bugs",
        _evaluator_bugs_router,
        {
            "generator_fix": "generator_fix",
        },
    )

    g.add_conditional_edges(
        "generator_fix",
        _generator_fix_router,
        {
            "evaluator_qa": "evaluator_qa",
            "generator_fix": "generator_fix",
        },
    )

    # ── Sprint completion ──
    g.add_conditional_edges(
        "sprint_complete",
        _sprint_complete_router,
        {
            "sprint_plan": "sprint_plan",
            "END": END,
        },
    )

    return g


def _wrap(fn):
    def wrapper(state: CodingState) -> dict:
        return fn(state)
    return wrapper


def _session_init_fanout(state: CodingState):
    """Sprint 1, Session 1 → fan-out to 5 init branches via Send.

    Otherwise → skip directly to session_setup_entry.
    """
    if state.get("_is_first_init", False):
        return [
            Send("init_progress", state),
            Send("init_script", state),
            Send("init_feature_list", state),
            Send("init_git", state),
            Send("init_loop_entry", state),
        ]
    return [Send("session_setup_entry", state)]


def _session_setup_fanout(state: CodingState):
    """Fan-out to 4 parallel context reads via Send."""
    return [
        Send("read_pwd", state),
        Send("read_progress", state),
        Send("read_feature_list", state),
        Send("read_git_log", state),
    ]


def _sprint_negotiate_router(state: CodingState) -> str:
    contract = state.get("sprint_contract") or {}
    if contract.get("agreed"):
        return "sprint_setup"
    round_num = state.get("negotiate_round", 1)
    if round_num > 3:
        return "sprint_setup"
    return "sprint_plan"


def _sanity_check_router(state: CodingState) -> str:
    if state.get("sanity_pass"):
        return "pick_feature"
    if state.get("sanity_retry_count", 0) >= 2:
        return "pick_feature"
    return "bug_triage"


def _pick_feature_router(state: CodingState) -> str:
    if state.get("current_feature_id"):
        return "implement_feature"
    return "generator_review"


def _test_feature_router(state: CodingState) -> str:
    result = state.get("test_result") or {}
    if result.get("passed"):
        return "commit_feature"
    feature_retry = state.get("feature_retry_count", 0)
    if feature_retry >= 2:
        return "commit_feature"
    return "implement_feature"


def _commit_feature_router(state: CodingState) -> str:
    feature_list = state.get("feature_list") or {}
    features = feature_list.get("features", [])
    sprint_contract = state.get("sprint_contract") or {}
    sprint_goals = sprint_contract.get("sprint_goals", [])
    sprint_feature_ids = {g.get("feature_id") for g in sprint_goals if g.get("feature_id")}
    sprint_features = [f for f in features if f.get("id") in sprint_feature_ids]
    unfinished = [f for f in sprint_features if not f.get("passes")]
    if unfinished:
        return "pick_feature"
    return "generator_review"


def _evaluator_qa_router(state: CodingState) -> str:
    grade = state.get("evaluator_grade") or {}
    if grade.get("overall_pass"):
        return "sprint_complete"
    return "evaluator_bugs"


def _evaluator_bugs_router(state: CodingState) -> str:
    return "generator_fix"


def _generator_fix_router(state: CodingState) -> str:
    fix_result = state.get("fix_result") or {}
    if fix_result.get("verified"):
        return "evaluator_qa"
    fix_count = state.get("fix_loop_count", 0)
    if fix_count >= 2:
        return "evaluator_qa"
    return "generator_fix"


def _sprint_complete_router(state: CodingState) -> str:
    sprint_result = state.get("sprint_result") or {}
    sprint_num = state.get("sprint_number", 1)

    if sprint_result.get("spec_complete"):
        return "END"

    if sprint_num >= 10:
        raise RuntimeError(
            f"Maximum sprint limit (10) reached. "
            f"Please review the generated code manually."
        )

    # Counters are reset by sprint_complete_node; router is read-only.
    return "sprint_plan"


def compile_coding_graph() -> StateGraph:
    return build_coding_graph().compile()
