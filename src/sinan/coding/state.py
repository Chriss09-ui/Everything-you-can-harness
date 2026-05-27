"""CodingState — state schema for the coding harness graph."""
from __future__ import annotations
import operator
from typing import TypedDict, Optional, Annotated


def _merge_dicts(a: dict, b: dict) -> dict:
    """Merge two dicts. Used as LangGraph reducer for session_context."""
    result = dict(a)
    result.update(b)
    return result


class CodingState(TypedDict, total=False):
    # ── Meta ──
    run_id: str
    harness_design_draft: dict          # from design layer
    current_phase: str

    # ── Sprint / Session tracking ──
    sprint_number: int
    session_number: int
    negotiate_round: int
    fix_loop_count: int

    # ── Artifacts ──
    spec: Optional[dict]                 # product spec from planner
    sprint_contract: Optional[dict]      # negotiated sprint goals
    sprint_result: Optional[dict]        # sprint evaluation summary
    feature_list: Optional[dict]         # in-memory view of feature_list.json
    current_feature_id: Optional[str]
    current_feature_status: Optional[str]
    test_result: Optional[dict]
    evaluator_grade: Optional[dict]
    fix_result: Optional[dict]
    bug_report: Optional[dict]

    # ── Feature loop ──
    sanity_pass: Optional[bool]
    implement_result: Optional[dict]
    triage_result: Optional[dict]
    feature_retry_count: int
    sanity_retry_count: int          # caps the sanity_check→bug_triage→sanity_check loop

    # ── Git ──
    last_good_commit: Optional[str]

    # ── Session budget ──
    session_progress_count: int

    # ── Session context (parallel reads, merged by reducer) ──
    # Fields: pwd, progress, feature_list, git_history
    # Written by read_pwd, read_progress, read_feature_list, read_git_log in parallel
    session_context: Annotated[dict, _merge_dicts]

    # ── Decision log ──
    decision_log: list[dict]
    progress_log: list[dict]
    messages: list[dict]


def make_coding_state(run_id: str, harness_design_draft: dict) -> CodingState:
    return CodingState(
        run_id=run_id,
        harness_design_draft=harness_design_draft,
        current_phase="CODING_INIT",
        sprint_number=1,
        session_number=1,
        negotiate_round=1,
        fix_loop_count=0,
        spec=None,
        sprint_contract=None,
        sprint_result=None,
        feature_list=None,
        current_feature_id=None,
        current_feature_status=None,
        test_result=None,
        evaluator_grade=None,
        fix_result=None,
        bug_report=None,
        last_good_commit=None,
        sanity_pass=None,
        implement_result=None,
        triage_result=None,
        feature_retry_count=0,
        sanity_retry_count=0,
        session_progress_count=0,
        session_context={},
        decision_log=[],
        progress_log=[],
        messages=[],
    )
