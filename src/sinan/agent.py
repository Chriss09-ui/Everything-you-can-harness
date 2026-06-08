"""Agent execution seam — run a tool-using Claude Agent SDK agent to a final
structured result.

This is the coding layer's counterpart to ``llm.py``. Where ``llm.py`` does a
single text completion (``generate(system, user) -> str``), this seam drives a
*real agent*: the model autonomously uses the Claude Code tool set
(Read/Write/Edit/Bash/Glob/Grep) inside a sandboxed ``cwd`` to read, write, and
run code, iterating until it reports a final JSON artifact.

Two implementations behind one ``AgentRunner`` interface (same swap-without-
touching-callers pattern as ``llm.py``):

    RealAgentRunner  — wraps ``claude_agent_sdk.query()``. Requires the
                       ``claude`` Code CLI to be installed AND authenticated in
                       the runtime: the SDK spawns it as a subprocess. This is a
                       NEW deploy dependency vs. "pip package + API key".
    MockAgentRunner  — fully offline. Never spawns the CLI. Returns a
                       deterministic structured output by keyword match AND
                       performs the file side-effects a real agent's Write tool
                       would have produced, so downstream runner / sanity checks
                       still see real files on disk.

Backend selection mirrors ``get_llm_client``: real only when a real credential
is present (non-empty ``ANTHROPIC_API_KEY``) or explicitly forced via
``SINAN_AGENT_BACKEND=real``; otherwise mock. The repo's ``.env`` ships empty
keys, so the test suite stays offline by default.

Safety boundary (and its known limit): every real agent is boxed by
``cwd=<harness dir>`` + ``allowed_tools`` *enforced* via
``permission_mode="dontAsk"`` (tools NOT in the list are denied — so the
read-only / zero-tool nodes genuinely cannot run Bash) + ``setting_sources=[]``
(don't load Sinan's own CLAUDE.md / settings into the harness agent) + a
PreToolUse hook that reuses ``assert_safe_llm_write_target`` to block writes
(via the Write/Edit tools) that escape the harness dir or hit a critical file,
plus a denylist for destructive Bash.

KNOWN LIMIT — for the two Bash-enabled nodes (implement_feature, generator_fix)
this is NOT a hard filesystem sandbox: a shell redirect (``echo > /abs/path``)
still escapes, because no command-string filter is sound. The real containment
boundary for those nodes is OS-level — the per-job container at deploy time.
Locally we accept this for trusted runs. (Verified empirically: ``dontAsk``
blocks Bash for the read-only nodes; the Write-tool escape is blocked by the
hook; the Bash-redirect escape is not, hence the deploy-time container.)
"""
from __future__ import annotations

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

from .validation import parse_llm_json
from .artifacts import assert_safe_llm_write_target

load_dotenv()

_log = logging.getLogger(__name__)

# Default per-call turn budget. A "turn" is one user/assistant pair; one agent
# task (implement a feature, fix bugs) spans many internal tool turns, so this
# is a runaway-cost ceiling, NOT a loop-count cap. The loop counts that matter
# (sprint≤10, fix≤2, ...) stay where they always were: the graph.py routers.
_DEFAULT_MAX_TURNS = 40

# Conservative Bash denylist. The primary sandbox is cwd + path checks; this
# only catches obviously destructive / exfiltrating commands that a buggy or
# misled agent might emit. Matched as substrings against the command string.
_BASH_DENY = (
    "rm -rf /",
    "rm -rf ~",
    ":(){",          # fork bomb
    "mkfs",
    "dd if=",
    "sudo ",
    "shutdown",
    "reboot",
)

# Tool names whose input names a filesystem write target we must sandbox.
_WRITE_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})


@dataclass
class AgentResult:
    """Outcome of one agent run.

    ``structured_output`` is the SDK's ``ResultMessage.structured_output`` when
    an ``output_format`` schema was requested; otherwise None and ``text`` (the
    ResultMessage.result string) carries the final JSON for tolerant parsing.
    """

    text: str
    structured_output: Optional[dict] = None
    total_cost_usd: float = 0.0
    num_turns: int = 0
    is_error: bool = False

    def parse(self, artifact_name: str) -> dict:
        """Return the final artifact dict.

        Prefer the SDK's validated structured output; fall back to tolerant
        JSON extraction from the final text (same parser the llm.py path used).
        Callers still run ``validate_artifact`` themselves so schema enforcement
        stays visible at the node level.
        """
        if isinstance(self.structured_output, dict):
            return self.structured_output
        return parse_llm_json(self.text, artifact_name)


class AgentRunner(ABC):
    """Abstract agent runner."""

    @abstractmethod
    def run(
        self,
        *,
        system: str,
        prompt: str,
        cwd: Path,
        allowed_tools: list[str],
        schema: Optional[dict] = None,
        max_turns: int = _DEFAULT_MAX_TURNS,
    ) -> AgentResult:
        """Run an agent to completion and return its final result."""
        ...


# ── Mock (offline) ──────────────────────────────────────────────────────────


class MockAgentRunner(AgentRunner):
    """Deterministic, offline agent. Never spawns the claude CLI.

    Registered responses map a trigger substring (matched against system +
    prompt, case-insensitive, same as MockLLMClient) to:
        output : the structured dict the agent "returns"
        files  : list of {path, content} the agent's Write tool "wrote"
                 (relative to cwd; written through assert_safe_llm_write_target
                 so the mock honours the same safety boundary as production)
    """

    # trigger -> {"output": dict, "files": list[dict]}
    _class_responses: dict[str, dict] = {}

    def __init__(self) -> None:
        # Per-instance copy so concurrent tests can't leak registrations.
        self._responses: dict[str, dict] = dict(self._class_responses)

    @classmethod
    def register(cls, trigger: str, output: dict, files: Optional[list[dict]] = None) -> None:
        cls._class_responses[trigger] = {"output": output, "files": files or []}

    @classmethod
    def reset(cls) -> None:
        cls._class_responses.clear()

    def run(
        self,
        *,
        system: str,
        prompt: str,
        cwd: Path,
        allowed_tools: list[str],
        schema: Optional[dict] = None,
        max_turns: int = _DEFAULT_MAX_TURNS,
    ) -> AgentResult:
        combined = (system + prompt).lower()
        matched: Optional[dict] = None
        for trigger, payload in self._responses.items():
            if trigger.lower() in combined:
                matched = payload
        if matched is None:
            # No registration → return a harmless empty-ish artifact. Tests that
            # exercise a node MUST register its trigger; an unmatched run here
            # surfaces as a downstream validation failure, not a silent network
            # call.
            return AgentResult(text="{}", structured_output={})

        # Reproduce the file side-effects a real agent's Write tool would make,
        # honouring the same safety boundary as production.
        for f in matched.get("files", []):
            try:
                target = assert_safe_llm_write_target(cwd, f["path"])
            except RuntimeError as e:
                _log.warning("MockAgentRunner blocked write: %s", e)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f.get("content", ""))

        output = matched.get("output", {})
        return AgentResult(text="", structured_output=output)


# ── Real (Claude Agent SDK) ──────────────────────────────────────────────────


class RealAgentRunner(AgentRunner):
    """Drives a real tool-using agent via ``claude_agent_sdk.query()``.

    The SDK import is lazy (inside ``run``) so importing this module never
    requires the SDK to be installed — same lazy-import discipline as the
    openai/anthropic clients in llm.py.
    """

    def run(
        self,
        *,
        system: str,
        prompt: str,
        cwd: Path,
        allowed_tools: list[str],
        schema: Optional[dict] = None,
        max_turns: int = _DEFAULT_MAX_TURNS,
    ) -> AgentResult:
        # graph.invoke() is synchronous and not running inside an event loop,
        # so a per-call asyncio.run is safe. NOTE: if a caller ever switches to
        # graph.ainvoke() (running this inside an event loop), this will raise
        # "asyncio.run() cannot be called from a running event loop" and the
        # seam must grow an async entrypoint.
        return asyncio.run(
            self._run_async(
                system=system,
                prompt=prompt,
                cwd=cwd,
                allowed_tools=allowed_tools,
                schema=schema,
                max_turns=max_turns,
            )
        )

    async def _run_async(
        self,
        *,
        system: str,
        prompt: str,
        cwd: Path,
        allowed_tools: list[str],
        schema: Optional[dict],
        max_turns: int,
    ) -> AgentResult:
        from claude_agent_sdk import (
            query,
            ClaudeAgentOptions,
            HookMatcher,
            ResultMessage,
        )

        options = ClaudeAgentOptions(
            system_prompt=system,
            cwd=str(cwd),
            allowed_tools=allowed_tools,
            # dontAsk: auto-allow the tools in allowed_tools (graph runs
            # unattended, no interactive prompts) AND deny any tool NOT in the
            # list. Unlike bypassPermissions — which allows everything, so Bash
            # ran even when unlisted — this makes allowed_tools an enforced
            # allowlist (verified: the read-only nodes can no longer spawn Bash).
            permission_mode="dontAsk",
            # Isolation: do NOT load Sinan's own CLAUDE.md / .claude settings
            # into the harness agent. [] = SDK isolation mode.
            setting_sources=[],
            max_turns=max_turns,
            hooks={
                "PreToolUse": [
                    HookMatcher(matcher=None, hooks=[_make_safe_hook(Path(cwd))])
                ]
            },
            output_format=(
                {"type": "json_schema", "schema": schema} if schema else None
            ),
        )

        result_msg = None
        try:
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, ResultMessage):
                    result_msg = message
        except Exception as e:
            # The SDK raises (sometimes a bare ``Exception``, e.g. "Reached
            # maximum number of turns (N)") instead of returning a ResultMessage
            # when the CLI ends in an error state. Translate it into a clear
            # seam-level error rather than leaking an opaque deep-SDK / asyncio
            # traceback up through the graph.
            raise RuntimeError(f"Agent run failed: {e}") from e

        if result_msg is None:
            raise RuntimeError("Agent run produced no ResultMessage")

        return AgentResult(
            text=result_msg.result or "",
            structured_output=getattr(result_msg, "structured_output", None),
            total_cost_usd=result_msg.total_cost_usd or 0.0,
            num_turns=result_msg.num_turns,
            is_error=result_msg.is_error,
        )


def _make_safe_hook(harness_dir: Path):
    """Build a PreToolUse hook that boxes an agent into ``harness_dir``.

    Blocks: writes resolving outside the harness dir or to a critical harness
    file (reuses ``assert_safe_llm_write_target``), and destructive Bash.
    """

    async def _hook(input_data: dict, tool_use_id: Any, context: Any) -> dict:
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {}) or {}

        if tool_name in _WRITE_TOOLS:
            path = tool_input.get("file_path") or tool_input.get("path") or ""
            try:
                assert_safe_llm_write_target(harness_dir, str(path))
            except RuntimeError as e:
                return _deny(str(e))

        if tool_name == "Bash":
            command = tool_input.get("command", "") or ""
            for bad in _BASH_DENY:
                if bad in command:
                    return _deny(f"Blocked destructive command pattern: {bad!r}")

        return {}

    return _hook


def _deny(reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


# ── Backend selection ────────────────────────────────────────────────────────


def get_agent_runner() -> AgentRunner:
    """Return the active agent runner.

    Mirrors ``get_llm_client``: real backend only when a real credential is
    available (so the empty-key ``.env`` keeps tests offline). Force either way
    with ``SINAN_AGENT_BACKEND=real|mock``.
    """
    backend = (os.getenv("SINAN_AGENT_BACKEND") or "").strip().lower()
    if backend == "mock":
        return MockAgentRunner()
    if backend == "real":
        return RealAgentRunner()

    # Auto: real only if an Anthropic credential is actually set (non-empty).
    if os.getenv("ANTHROPIC_API_KEY"):
        return RealAgentRunner()
    return MockAgentRunner()
