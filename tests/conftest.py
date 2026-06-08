"""Test configuration shared across all tests.

Two autouse responsibilities:

1. Reset ``MockLLMClient`` / ``MockAgentRunner`` class-level registries before
   each test, so triggers registered by one test (e.g. test_path_traversal
   registers ``"Bug 修复"``) don't leak into the next.

2. Force OFFLINE backends regardless of the developer's ``.env``. The repo's
   ``.env`` may carry a real ``ANTHROPIC_API_KEY`` (e.g. pointed at a DeepSeek
   Anthropic-compatible proxy). Without this guard, ``get_llm_client()`` and
   ``get_agent_runner()`` would select REAL backends — the suite would hit the
   network and even spawn the ``claude`` CLI for coding-layer agent nodes,
   making tests slow, flaky, and non-deterministic. We clear the credential
   env vars and pin ``SINAN_AGENT_BACKEND=mock`` so every test runs purely on
   the mock seams.

Tests that NEED to keep something registered across the reset should use
``monkeypatch.setattr`` on the class dict directly, or call the standard
``register_*_responses()`` helper at the top of the test.
"""
from __future__ import annotations

import pytest

import sinan.llm as _llm
from sinan.llm import MockLLMClient
from sinan.agent import MockAgentRunner


@pytest.fixture(autouse=True)
def _offline_mock_backends(monkeypatch):
    """Reset mock registries AND force offline backends before each test."""
    # Force offline: strip any real credentials the dev's .env loaded, and pin
    # the agent backend to mock. get_llm_client() falls back to MockLLMClient
    # when no key is present; clearing the client cache prevents a real client
    # cached by a prior import from leaking in.
    for var in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "OPENAI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("SINAN_AGENT_BACKEND", "mock")
    _llm._CLIENT_CACHE.clear()

    MockLLMClient.reset()
    MockAgentRunner.reset()
    yield
    MockLLMClient.reset()
    MockAgentRunner.reset()
    _llm._CLIENT_CACHE.clear()
