"""Test configuration shared across all tests.

Currently serves one purpose: automatically reset ``MockLLMClient``'s
class-level response registry before each test, so individual tests that
register private triggers (e.g. test_path_traversal registers ``"Bug 修复"``
for coding-layer node tests) don't leak into other tests.

Without this, a test that runs after ``test_path_traversal`` sees a
``MockLLMClient`` pre-populated with coding-layer triggers that don't match
any design-layer prompt. Tests that use the snapshot-based
``test_mock_trigger_coverage`` already work around this; the auto-reset
here extends that safety to every test.

Tests that NEED to keep something registered across the reset should use
``monkeypatch.setattr`` on the class dict directly, or call
``register_mock_responses()`` (the standard helper) at the top of the test,
which is what every existing design-layer test already does.
"""
from __future__ import annotations

import pytest

from sinan.llm import MockLLMClient


@pytest.fixture(autouse=True)
def _reset_mock_llm_registry():
    """Auto-reset MockLLMClient's class state before each test."""
    MockLLMClient.reset()
    yield
    MockLLMClient.reset()
