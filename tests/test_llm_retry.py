"""Regression test for LLM retry: exponential backoff + non-retryable 4xx.

Earlier versions retried exactly twice with no delay, which a real provider
will reject under burst rate-limiting in milliseconds. The fix:
- 3 total attempts
- exponential backoff between attempts (0.5s * 2**(n-1))
- 4xx request-shape errors (BadRequest / Auth / NotFound) skip retry
"""
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sinan import llm as llm_mod
from sinan.llm import _OpenAIClient


@pytest.fixture(autouse=True)
def _fast_backoff(monkeypatch):
    """Shrink backoff so the suite stays under 1s."""
    monkeypatch.setattr(llm_mod, "_BACKOFF_BASE", 0.01)


def _stub_openai_client(responses):
    """Build an _OpenAIClient with a mocked chat.completions.create call."""
    client = _OpenAIClient.__new__(_OpenAIClient)
    client.model = "test-model"

    iterator = iter(responses)

    class _Completions:
        def create(self, **kwargs):
            item = next(iterator)
            if isinstance(item, Exception):
                raise item
            return item

    class _Chat:
        completions = _Completions()

    client.client = type("Inner", (), {"chat": _Chat()})()
    return client


class _FakeResponse:
    def __init__(self, text: str):
        msg = type("Msg", (), {"content": text})()
        choice = type("Choice", (), {"message": msg, "finish_reason": "stop"})()
        self.choices = [choice]


def test_retries_then_succeeds():
    client = _stub_openai_client([
        ConnectionError("transient"),
        ConnectionError("transient"),
        _FakeResponse("hello"),
    ])
    assert client.generate("sys", "user") == "hello"


def test_gives_up_after_max_attempts():
    """3 attempts then raise the last transient error."""
    client = _stub_openai_client([
        ConnectionError("e1"),
        ConnectionError("e2"),
        ConnectionError("e3"),
    ])
    with pytest.raises(ConnectionError, match="e3"):
        client.generate("sys", "user")


def test_non_retryable_fails_fast():
    """A BadRequestError-named exception is raised on first attempt; no retries."""
    class BadRequestError(Exception):
        pass

    calls = {"n": 0}
    client = _OpenAIClient.__new__(_OpenAIClient)
    client.model = "m"

    class _Completions:
        def create(self, **kwargs):
            calls["n"] += 1
            raise BadRequestError("bad input")

    client.client = type("Inner", (), {"chat": type("C", (), {"completions": _Completions()})()})()

    with pytest.raises(BadRequestError):
        client.generate("sys", "user")
    assert calls["n"] == 1, f"expected 1 attempt (non-retryable), got {calls['n']}"


def test_backoff_actually_sleeps(monkeypatch):
    """Backoff must add real delay between attempts."""
    monkeypatch.setattr(llm_mod, "_BACKOFF_BASE", 0.05)
    client = _stub_openai_client([
        ConnectionError("e1"),
        ConnectionError("e2"),
        _FakeResponse("ok"),
    ])
    start = time.time()
    client.generate("sys", "user")
    elapsed = time.time() - start
    # First retry sleeps 0.05s, second sleeps 0.10s → ≥ 0.15s total.
    assert elapsed >= 0.14, f"expected ≥ 0.14s of backoff, got {elapsed:.3f}s"
