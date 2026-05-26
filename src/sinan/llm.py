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
from abc import ABC, abstractmethod
from typing import Any
from dotenv import load_dotenv

load_dotenv()

_log = logging.getLogger(__name__)


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


# Singleton instance
def get_llm_client() -> LLMClient:
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            import anthropic
            return _AnthropicClient(os.getenv("ANTHROPIC_API_KEY", ""))
        except ImportError:
            _log.warning(
                "ANTHROPIC_API_KEY is set but `anthropic` SDK is not installed; "
                "falling back to MockLLM. Install with: pip install anthropic"
            )
            return MockLLMClient()

    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        try:
            return _OpenAIClient(api_key)
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
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        if base_url:
            _log.info("OpenAI-compatible provider: base_url=%s model=%s", base_url, self.model)

    def generate(self, system: str, user: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.3,
        )
        return response.choices[0].message.content


class _AnthropicClient(LLMClient):
    def __init__(self, api_key: str):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

    def generate(self, system: str, user: str) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text
