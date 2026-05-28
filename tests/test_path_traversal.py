"""Regression tests for path traversal blocking (P0 security fix).

Before this fix, ``implement_feature_node`` and ``generator_fix_node``
joined LLM-returned ``files[].path`` directly onto ``harness_dir`` and
wrote whatever the LLM returned. A path like ``../../etc/passwd`` or
``../../../tmp/evil`` would resolve outside the harness sandbox and
``pathlib`` would happily write it.

These tests pin the resolve() + is_relative_to() guard so a future
refactor that drops it will fail at least one of these three cases:
  1. "../" escape in the path
  2. absolute path (e.g. "/tmp/x") attempting to escape
  3. benign sibling files still get written (we don't over-block)
"""
import json
import sys
from pathlib import Path

from sinan.llm import MockLLMClient
from sinan.artifacts import ensure_run_dir, get_run_dir
from sinan.coding.state import make_coding_state
from sinan.coding.nodes.implement_feature import implement_feature_node
from sinan.coding.nodes.generator_fix import generator_fix_node


_DRAFT = {
    "version": "1.0", "use_case": "t", "primary_goal": "g",
    "scope": {"inclusions": [], "exclusions": []},
    "success_criteria": [], "test_cases": [],
    "graph": {"nodes": [], "edges": [], "entry_point": "s", "end_state": "END"},
    "phase_sequence": [], "memory_module": {}, "handoff_protocol": {},
    "eval_placements": {}, "state_schema": {"required_fields": []},
}


def _setup(tmp_path, monkeypatch, mock_payload, trigger_substring):
    """Point RUNS_DIR at tmp, register one mock response, return a fresh state."""
    from sinan import artifacts as art
    monkeypatch.setattr(art, "RUNS_DIR", tmp_path / "runs")

    MockLLMClient.reset()
    MockLLMClient.register(trigger_substring, json.dumps(mock_payload, ensure_ascii=False))

    run_id = "path_trav_test"
    ensure_run_dir(run_id)
    (get_run_dir(run_id) / "harness").mkdir(parents=True)
    (get_run_dir(run_id) / "harness" / "main.py").write_text("print(1)\n")
    (get_run_dir(run_id) / "harness" / "src").mkdir(parents=True)

    state = make_coding_state(run_id, _DRAFT)
    state["feature_list"] = {"features": [{"id": "F1", "name": "feat", "priority": "high"}]}
    state["current_feature_id"] = "F1"
    state["spec"] = {"name": "t", "features": [], "success_criteria": []}
    return run_id, state


def test_implement_feature_blocks_dotdot_escape(tmp_path, monkeypatch):
    """../../etc/x must NOT be written; legit sibling file must still be."""
    run_id, state = _setup(tmp_path, monkeypatch, {
        "status": "implemented",
        "files": [
            {"path": "../../etc/evil.txt", "content": "PWNED", "action": "create"},
            {"path": "src/legit.py", "content": "ok = 1\n", "action": "create"},
        ],
        "summary": "mixed payload",
    }, "请实现以下功能")

    implement_feature_node(state)

    harness = get_run_dir(run_id) / "harness"
    # Evil file MUST NOT exist anywhere under tmp_path
    evil_candidates = list(tmp_path.rglob("evil.txt"))
    assert evil_candidates == [], f"path traversal escaped: {evil_candidates}"
    # Legit file still written
    assert (harness / "src" / "legit.py").read_text() == "ok = 1\n"


def test_implement_feature_blocks_absolute_path(tmp_path, monkeypatch):
    """/tmp/whatever must NOT be written. We use a path inside tmp_path so the
    test stays self-contained; if the guard is missing, it WILL be created there
    and the assertion will catch it."""
    abs_target = tmp_path / "abspath_poison.txt"
    assert not abs_target.exists(), "precondition: target should not exist"
    run_id, state = _setup(tmp_path, monkeypatch, {
        "status": "implemented",
        "files": [
            {"path": str(abs_target), "content": "PWNED", "action": "create"},
        ],
        "summary": "absolute path attempt",
    }, "请实现以下功能")

    implement_feature_node(state)

    assert not abs_target.exists(), (
        f"absolute path {abs_target} was written — harness sandbox broken"
    )


def test_generator_fix_blocks_path_traversal(tmp_path, monkeypatch):
    """Same guard on the fix path. Legit patches must still go through."""
    run_id, state = _setup(tmp_path, monkeypatch, {
        "status": "fixed",
        "files": [
            {"path": "../../../escape.txt", "content": "PWNED", "action": "modify"},
            {"path": "src/patched.py", "content": "fixed = True\n", "action": "modify"},
        ],
        "verified": True,
        "self_test_passed": True,
        "summary": "mixed patch",
    }, "Bug 修复")

    state["bug_report"] = {"bugs": [{"description": "b1", "severity": "major"}]}
    state["fix_loop_count"] = 0

    generator_fix_node(state)

    harness = get_run_dir(run_id) / "harness"
    escape_candidates = list(tmp_path.rglob("escape.txt"))
    assert escape_candidates == [], f"path traversal escaped: {escape_candidates}"
    assert (harness / "src" / "patched.py").read_text() == "fixed = True\n"
