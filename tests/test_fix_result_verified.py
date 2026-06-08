"""Regression tests for fix_result.verified handling (M16 + Bug-1).

Earlier M16 implementation had two coupled mistakes:
  - validation schema required ``verified`` as a top-level field
  - generator_fix.py used ``if not result.get("verified"): result["verified"] = sanity.passed``

Combined effect: when LLM truthfully returned ``verified: false``, the
``not get(...)`` branch fired and overwrote it with sanity.passed —
sanity only checks that src/ + main.py exist, not that the bug was
actually fixed. So an honest LLM signal got buried.

This file pins the corrected two-case behaviour.
"""
import json
import sys
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sinan.agent import MockAgentRunner
from sinan.coding.nodes.generator_fix import generator_fix_node
from sinan.coding.state import make_coding_state
from sinan.coding.graph import _generator_fix_router
from sinan.artifacts import ensure_run_dir, get_run_dir


def _setup(tmp_path, monkeypatch, mock_response):
    """Shared harness: tmp RUNS_DIR + harness with src/ + main.py.

    generator_fix runs as an agent now, so the mock is registered on
    MockAgentRunner. ``mock_response`` is the agent's structured report; its
    ``files`` double as the file side-effects the mock agent "writes".
    """
    from sinan import artifacts as art
    monkeypatch.setattr(art, "RUNS_DIR", tmp_path / "runs")
    MockAgentRunner.reset()
    MockAgentRunner.register("请在当前项目目录中修复", mock_response,
                             files=mock_response.get("files", []))

    run_id = "fix_result_test"
    ensure_run_dir(run_id)
    (get_run_dir(run_id) / "harness" / "src").mkdir(parents=True)
    (get_run_dir(run_id) / "harness" / "main.py").write_text("print(1)\n")
    return run_id


def _draft():
    return {
        "version": "1.0", "use_case": "t", "primary_goal": "g",
        "scope": {"inclusions": [], "exclusions": []},
        "success_criteria": [], "test_cases": [],
        "graph": {"nodes": [], "edges": [], "entry_point": "s", "end_state": "END"},
        "phase_sequence": [], "memory_module": {}, "handoff_protocol": {},
        "eval_placements": {}, "state_schema": {"required_fields": []},
    }


def test_llm_says_not_verified_is_honored(tmp_path, monkeypatch):
    """LLM truthfully returning verified=False must NOT be overwritten by sanity."""
    run_id = _setup(tmp_path, monkeypatch, {
        "status": "fixed",
        "files": [{"path": "src/x.py", "content": "x=1\n", "action": "modify"}],
        "verified": False,
        "summary": "still broken",
    })
    state = make_coding_state(run_id, _draft())
    state["bug_report"] = {"bugs": [{"description": "b1", "severity": "major"}]}
    state["fix_loop_count"] = 0

    out = generator_fix_node(state)
    assert out["fix_result"]["verified"] is False, (
        f"LLM-returned False was overwritten; sanity overrode an honest signal"
    )
    assert _generator_fix_router(out) == "generator_fix", (
        f"router should keep fixing when LLM admits failure"
    )


def test_missing_verified_falls_back_to_sanity(tmp_path, monkeypatch):
    """When LLM omits verified entirely, sanity fills in for it."""
    run_id = _setup(tmp_path, monkeypatch, {
        "status": "fixed",
        "files": [{"path": "src/x.py", "content": "x=1\n", "action": "modify"}],
        "summary": "fixed (no verified field returned)",
    })
    state = make_coding_state(run_id, _draft())
    state["bug_report"] = {"bugs": [{"description": "b1", "severity": "major"}]}
    state["fix_loop_count"] = 0

    out = generator_fix_node(state)
    # Sanity passes (files exist), so fallback should set verified=True
    assert out["fix_result"]["verified"] is True, (
        f"missing verified should fall back to sanity.passed=True"
    )
    assert _generator_fix_router(out) == "evaluator_qa", (
        f"router should exit fix loop early when sanity confirms; saves LLM call"
    )


def test_llm_says_verified_true_short_circuits(tmp_path, monkeypatch):
    """LLM returning verified=true should be trusted, regardless of sanity."""
    run_id = _setup(tmp_path, monkeypatch, {
        "status": "fixed",
        "files": [{"path": "src/x.py", "content": "x=1\n", "action": "modify"}],
        "verified": True,
        "summary": "all good",
    })
    state = make_coding_state(run_id, _draft())
    state["bug_report"] = {"bugs": [{"description": "b1", "severity": "major"}]}
    state["fix_loop_count"] = 0

    out = generator_fix_node(state)
    assert out["fix_result"]["verified"] is True
    assert _generator_fix_router(out) == "evaluator_qa"
