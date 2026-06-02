"""LLM client adapter — swap mock for real OpenAI/Anthropic without touching the rest.

Provider configuration (via .env):
    OpenAI (default):     OPENAI_API_KEY + optional LLM_MODEL (default gpt-4o-mini)
    Anthropic:            ANTHROPIC_API_KEY + optional ANTHROPIC_MODEL (default claude-sonnet-4-6)
    Any OpenAI-compatible provider (DeepSeek, Moonshot, 智谱, 通义, Doubao, OpenRouter,
    Groq, Together, Ollama, vLLM, ...): set OPENAI_API_KEY + OPENAI_BASE_URL + LLM_MODEL.

    Examples:
        # DeepSeek
        OPENAI_BASE_URL=https://api.deepseek.com/v1
        LLM_MODEL=deepseek-chat

        # Moonshot Kimi
        OPENAI_BASE_URL=https://api.moonshot.cn/v1
        LLM_MODEL=moonshot-v1-8k

        # 智谱 GLM
        OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4
        LLM_MODEL=glm-4

        # 通义千问
        OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
        LLM_MODEL=qwen-plus

        # 本地 Ollama
        OPENAI_BASE_URL=http://localhost:11434/v1
        LLM_MODEL=llama3.1
"""
from __future__ import annotations
import json
import logging
import os
import time
from abc import ABC, abstractmethod
from typing import Any
from dotenv import load_dotenv

load_dotenv()

_log = logging.getLogger(__name__)


# Total attempts (including the first call). Tunable for tests via monkeypatch.
_MAX_ATTEMPTS = 3
# Base delay seconds for exponential backoff: sleep = _BACKOFF_BASE * 2**(attempt-1).
# Default schedule: 0.5s, 1.0s between attempts 1→2, 2→3.
_BACKOFF_BASE = 0.5
# Exception class names that should NOT be retried (4xx that means "your
# request is wrong", not transient). 429 RateLimitError IS retryable, so it
# is intentionally absent.
_NON_RETRYABLE_EXC_NAMES = frozenset({
    "BadRequestError",
    "AuthenticationError",
    "PermissionDeniedError",
    "NotFoundError",
    "UnprocessableEntityError",
})

# Content-shape errors that we raised ourselves. These look like transient
# exceptions but aren't: ``content=None`` from OpenAI typically means
# finish_reason=length (output truncated by max_tokens) or refusal — either
# way, retrying the identical prompt with the identical token budget will
# produce the identical result, so we'd just burn quota +60s of backoff.
# Defined as plain ``Exception`` subclasses with stable names so the retry
# loop can match them by name without importing this module's internals.
class _LLMContentEmpty(Exception):
    """LLM returned no choices."""


class _LLMContentNone(Exception):
    """LLM returned choices[0].message.content=None — usually finish_reason=length
    or refusal. Not transient: same prompt + same budget yields same output."""


_NON_RETRYABLE_CONTENT_ERRORS = frozenset({
    _LLMContentEmpty.__name__,
    _LLMContentNone.__name__,
})


def _should_retry(exc: Exception) -> bool:
    """Decide whether to retry a failed LLM call.

    Both openai and anthropic SDKs raise subclasses with names like
    ``BadRequestError`` and ``RateLimitError``. We match by class name so we
    don't have to import either SDK at module load. 429 / 5xx fall through to
    "retry"; explicit 4xx-request-shape errors and our own content-shape
    errors (``_LLMContentNone`` / ``_LLMContentEmpty``) don't.
    """
    return (
        type(exc).__name__ not in _NON_RETRYABLE_EXC_NAMES
        and type(exc).__name__ not in _NON_RETRYABLE_CONTENT_ERRORS
    )


class LLMClient(ABC):
    """Abstract LLM client."""

    @abstractmethod
    def generate(self, system: str, user: str) -> str:
        """Return LLM text response."""
        ...


class MockLLMClient(LLMClient):
    """Mock LLM that returns deterministic JSON based on keyword matching."""

    _class_responses: dict[str, str] = {}

    def __init__(self) -> None:
        # Per-instance responses, copied from the class registry. Each
        # get_llm_client() call returns a fresh instance, so tests can't
        # leak registrations into other tests.
        self._responses: dict[str, str] = dict(self._class_responses)

    @classmethod
    def register(cls, trigger: str, response: str) -> None:
        cls._class_responses[trigger] = response

    @classmethod
    def reset(cls) -> None:
        cls._class_responses.clear()

    def generate(self, system: str, user: str) -> str:
        combined = system + user
        matched_response = None
        for trigger, response in self._responses.items():
            if trigger.lower() in combined.lower():
                matched_response = response
        if matched_response is not None:
            return matched_response
        return self._fallback_response(user)

    def _fallback_response(self, user: str) -> str:
        """Generate a plausible mock response when no trigger matches."""
        return json.dumps({
            "status": "mock_response",
            "input_preview": user[:100],
            "note": "No mock registered for this prompt. Register with MockLLMClient.register()."
        })


# Singleton instance cache, keyed by the env-signature at construction time.
# Re-creating the SDK client per call wastes a connection pool and (for
# providers that authenticate at construction) an auth roundtrip. Cache is
# keyed on (provider, api_key, base_url, model) so changing any of these
# between calls picks up the new config.
_CLIENT_CACHE: dict[tuple, LLMClient] = {}


def _cache_key() -> tuple:
    return (
        "anthropic" if os.getenv("ANTHROPIC_API_KEY") else "openai",
        os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY") or "",
        os.getenv("OPENAI_BASE_URL") or "",
        os.getenv("LLM_MODEL") or os.getenv("ANTHROPIC_MODEL") or "",
    )


# Singleton instance
def get_llm_client() -> LLMClient:
    key = _cache_key()
    cached = _CLIENT_CACHE.get(key)
    if cached is not None:
        return cached

    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            import anthropic
            client = _AnthropicClient(os.getenv("ANTHROPIC_API_KEY", ""))
            _CLIENT_CACHE[key] = client
            return client
        except ImportError:
            _log.warning(
                "ANTHROPIC_API_KEY is set but `anthropic` SDK is not installed; "
                "falling back to MockLLM. Install with: pip install anthropic"
            )
            return MockLLMClient()

    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        try:
            client = _OpenAIClient(api_key)
            _CLIENT_CACHE[key] = client
            return client
        except ImportError:
            _log.warning(
                "OPENAI_API_KEY is set but `openai` SDK is not installed; "
                "falling back to MockLLM. Install with: pip install openai"
            )
            return MockLLMClient()

    return MockLLMClient()


class _OpenAIClient(LLMClient):
    def __init__(self, api_key: str):
        from openai import OpenAI
        base_url = os.getenv("OPENAI_BASE_URL")
        # Give the SDK an explicit timeout so a stuck provider doesn't hang
        # the entire graph indefinitely. 120s is long enough for the slowest
        # models but bounded.
        self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=120.0)
        self.model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        if base_url:
            _log.info("OpenAI-compatible provider: base_url=%s model=%s", base_url, self.model)

    def generate(self, system: str, user: str) -> str:
        # Retry with exponential backoff on transient errors (network, 429,
        # 5xx). 4xx request-shape errors and content-shape errors (None /
        # empty) are NOT retried — the next attempt would fail the same way
        # and we'd just burn quota. Symmetric to _AnthropicClient below
        # (max_tokens=4096) so provider swaps don't silently re-introduce
        # truncation-driven content=None failures.
        last_err: Exception | None = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=0.3,
                    max_tokens=4096,
                )
                if not response.choices:
                    # We're inside the "choices is empty" branch, so there is
                    # no choices[0] to read a finish_reason from — the SDK
                    # didn't return any completion at all (rare; usually means
                    # provider-side error before generation started).
                    raise _LLMContentEmpty("no choices returned")
                content = response.choices[0].message.content
                if content is None:
                    raise _LLMContentNone(
                        f"finish_reason={response.choices[0].finish_reason}"
                    )
                return content
            except Exception as exc:
                last_err = exc
                _log.warning("OpenAI attempt %d failed: %s: %s",
                             attempt, type(exc).__name__, exc)
                if not _should_retry(exc):
                    _log.warning("OpenAI error %s is non-retryable; failing immediately",
                                 type(exc).__name__)
                    break
                if attempt < _MAX_ATTEMPTS:
                    time.sleep(_BACKOFF_BASE * (2 ** (attempt - 1)))
        assert last_err is not None
        raise last_err


class _AnthropicClient(LLMClient):
    def __init__(self, api_key: str):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

    def generate(self, system: str, user: str) -> str:
        last_err: Exception | None = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                )
                if not response.content:
                    raise _LLMContentEmpty(
                        f"stop_reason={response.stop_reason if hasattr(response, 'stop_reason') else 'n/a'}"
                    )
                text = response.content[0].text
                if text is None:
                    raise _LLMContentNone(
                        f"stop_reason={getattr(response, 'stop_reason', None)}"
                    )
                return text
            except Exception as exc:
                last_err = exc
                _log.warning("Anthropic attempt %d failed: %s: %s",
                             attempt, type(exc).__name__, exc)
                if not _should_retry(exc):
                    _log.warning("Anthropic error %s is non-retryable; failing immediately",
                                 type(exc).__name__)
                    break
                if attempt < _MAX_ATTEMPTS:
                    time.sleep(_BACKOFF_BASE * (2 ** (attempt - 1)))
        assert last_err is not None
        raise last_err
