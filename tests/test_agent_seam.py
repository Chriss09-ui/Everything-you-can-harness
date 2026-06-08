"""Unit tests for the agent execution seam (src/sinan/agent.py).

These never spawn the claude CLI — they exercise MockAgentRunner, which is the
offline backend the rest of the test suite relies on.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from sinan.agent import (
    AgentResult,
    MockAgentRunner,
    get_agent_runner,
)


def test_mock_runner_returns_structured_output_and_writes_files(tmp_path):
    """A registered mock returns its structured output AND writes its files."""
    MockAgentRunner.register(
        "请实现以下功能",
        output={"status": "implemented", "files": [{"path": "main.py", "action": "create"}],
                "summary": "ok"},
        files=[{"path": "main.py", "content": "print('hi')\n"},
               {"path": "src/__init__.py", "content": ""}],
    )
    runner = MockAgentRunner()
    result = runner.run(
        system="你是 Generator",
        prompt="请实现以下功能：feat_001",
        cwd=tmp_path,
        allowed_tools=["Read", "Write", "Edit", "Bash"],
    )
    assert isinstance(result, AgentResult)
    data = result.parse("implement_result")
    assert data["status"] == "implemented"
    # Files the "agent" wrote are really on disk inside cwd.
    assert (tmp_path / "main.py").read_text() == "print('hi')\n"
    assert (tmp_path / "src" / "__init__.py").exists()


def test_mock_runner_honours_safe_write_boundary(tmp_path):
    """Path traversal in a mock's files is blocked, not written outside cwd."""
    MockAgentRunner.register(
        "escape",
        output={"status": "implemented", "files": []},
        files=[{"path": "../evil.py", "content": "x"}],
    )
    runner = MockAgentRunner()
    runner.run(system="", prompt="escape", cwd=tmp_path,
               allowed_tools=["Write"])
    assert not (tmp_path.parent / "evil.py").exists()


def test_mock_runner_unmatched_trigger_is_offline_noop(tmp_path):
    """No registration → empty artifact, never a network/CLI call."""
    runner = MockAgentRunner()
    result = runner.run(system="", prompt="nothing matches",
                        cwd=tmp_path, allowed_tools=[])
    assert result.parse("anything") == {}


def test_backend_selection_defaults_to_mock_without_credentials(monkeypatch):
    """Empty/absent ANTHROPIC_API_KEY → mock backend (keeps tests offline)."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("SINAN_AGENT_BACKEND", raising=False)
    assert isinstance(get_agent_runner(), MockAgentRunner)


def test_backend_selection_force_mock(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-real-looking")
    monkeypatch.setenv("SINAN_AGENT_BACKEND", "mock")
    assert isinstance(get_agent_runner(), MockAgentRunner)
