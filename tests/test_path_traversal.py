"""Regression tests for path traversal blocking (P0 security fix).

``implement_feature_node`` and ``generator_fix_node`` now run as Claude Agent
SDK agents — they no longer join paths onto ``harness_dir`` in Python. The
``resolve() + is_relative_to()`` guard (``assert_safe_llm_write_target``) lives
in the agent seam instead: MockAgentRunner routes its file side-effects through
it, and RealAgentRunner enforces it via a PreToolUse hook. A path like
``../../etc/passwd`` or an absolute ``/tmp/evil`` must still be blocked from
escaping the harness sandbox.

These tests pin that guard so a future refactor that drops it will fail at least
one of these cases:
  1. "../" escape in the path
  2. absolute path (e.g. "/tmp/x") attempting to escape
  3. ``init.sh`` overwrite (acute: session_setup runs it via ``bash init.sh``)
  4. benign sibling files still get written (we don't over-block)
"""
import sys
from pathlib import Path

from sinan.agent import MockAgentRunner
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


def _scaffold(tmp_path, monkeypatch):
    """Point RUNS_DIR at tmp, build a harness dir + fresh state."""
    from sinan import artifacts as art
    monkeypatch.setattr(art, "RUNS_DIR", tmp_path / "runs")

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


def _setup_agent(tmp_path, monkeypatch, output, files, trigger_substring):
    """Agent-node variant: register a MockAgentRunner response.

    ``files`` are the side-effects the mock agent's Write tool "makes" — routed
    through assert_safe_llm_write_target, so a malicious path is blocked exactly
    as a real agent's PreToolUse hook would block it. ``output`` is the agent's
    structured report (must satisfy the implement_result schema).
    """
    run_id, state = _scaffold(tmp_path, monkeypatch)
    MockAgentRunner.reset()
    MockAgentRunner.register(trigger_substring, output, files=files)
    return run_id, state


def test_implement_feature_blocks_dotdot_escape(tmp_path, monkeypatch):
    """../../etc/x must NOT be written; legit sibling file must still be."""
    run_id, state = _setup_agent(tmp_path, monkeypatch,
        output={
            "status": "implemented",
            "files": [{"path": "src/legit.py", "action": "create"}],
            "summary": "mixed payload",
        },
        files=[
            {"path": "../../etc/evil.txt", "content": "PWNED"},
            {"path": "src/legit.py", "content": "ok = 1\n"},
        ],
        trigger_substring="请在当前项目目录中实现以下功能")

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
    run_id, state = _setup_agent(tmp_path, monkeypatch,
        output={"status": "implemented", "files": [], "summary": "absolute path attempt"},
        files=[{"path": str(abs_target), "content": "PWNED"}],
        trigger_substring="请在当前项目目录中实现以下功能")

    implement_feature_node(state)

    assert not abs_target.exists(), (
        f"absolute path {abs_target} was written — harness sandbox broken"
    )


def test_generator_fix_blocks_path_traversal(tmp_path, monkeypatch):
    """Same guard on the fix path. Legit patches must still go through."""
    run_id, state = _setup_agent(tmp_path, monkeypatch,
        output={
            "status": "fixed",
            "files": [{"path": "src/patched.py", "action": "modify"}],
            "verified": True,
            "summary": "mixed patch",
        },
        files=[
            {"path": "../../../escape.txt", "content": "PWNED"},
            {"path": "src/patched.py", "content": "fixed = True\n"},
        ],
        trigger_substring="请在当前项目目录中修复")

    state["bug_report"] = {"bugs": [{"description": "b1", "severity": "major"}]}
    state["fix_loop_count"] = 0

    generator_fix_node(state)

    harness = get_run_dir(run_id) / "harness"
    escape_candidates = list(tmp_path.rglob("escape.txt"))
    assert escape_candidates == [], f"path traversal escaped: {escape_candidates}"
    assert (harness / "src" / "patched.py").read_text() == "fixed = True\n"


def test_implement_feature_blocks_init_sh_overwrite(tmp_path, monkeypatch):
    """init.sh is the acute risk: session_setup runs it via ``bash init.sh``.

    If an LLM could route ``{"path": "init.sh", ...}`` through implement_feature,
    the next sprint's session init would execute attacker-controlled bash. We
    must block this overwrite even though the path trivially resolves inside
    the harness dir.
    """
    run_id, state = _setup_agent(tmp_path, monkeypatch,
        output={
            "status": "implemented",
            "files": [{"path": "src/legit.py", "action": "create"}],
            "summary": "init.sh hijack attempt",
        },
        files=[
            {"path": "init.sh", "content": "#!/bin/bash\necho PWNED\n"},
            {"path": "src/legit.py", "content": "ok = 1\n"},
        ],
        trigger_substring="请在当前项目目录中实现以下功能")

    init_sh = get_run_dir(run_id) / "harness" / "init.sh"
    init_sh.write_text("echo original\n")
    init_sh.chmod(0o755)

    implement_feature_node(state)

    assert init_sh.read_text() == "echo original\n", (
        "init.sh was overwritten by LLM — next session_setup would run "
        "attacker-controlled bash"
    )
    assert (get_run_dir(run_id) / "harness" / "src" / "legit.py").exists()


def test_generator_fix_blocks_init_sh_overwrite(tmp_path, monkeypatch):
    """Mirror of the implement_feature test, on the bug-fix path."""
    run_id, state = _setup_agent(tmp_path, monkeypatch,
        output={
            "status": "fixed",
            "files": [{"path": "src/patched.py", "action": "modify"}],
            "verified": True,
            "summary": "init.sh hijack via fix",
        },
        files=[
            {"path": "init.sh", "content": "#!/bin/bash\necho PWNED\n"},
            {"path": "src/patched.py", "content": "fixed = True\n"},
        ],
        trigger_substring="请在当前项目目录中修复")

    state["bug_report"] = {"bugs": [{"description": "b1", "severity": "major"}]}
    state["fix_loop_count"] = 0

    init_sh = get_run_dir(run_id) / "harness" / "init.sh"
    init_sh.write_text("echo original\n")
    init_sh.chmod(0o755)

    generator_fix_node(state)

    assert init_sh.read_text() == "echo original\n", (
        "init.sh was overwritten by generator_fix"
    )
    assert (get_run_dir(run_id) / "harness" / "src" / "patched.py").read_text() == "fixed = True\n"
