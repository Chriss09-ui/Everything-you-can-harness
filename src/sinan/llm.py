"""LLM client adapter — swap mock for real OpenAI/Anthropic without touching the rest."""
from __future__ import annotations
import json
import os
from abc import ABC, abstractmethod
from typing import Any
from dotenv import load_dotenv

load_dotenv()


class LLMClient(ABC):
    """Abstract LLM client."""

    @abstractmethod
    def generate(self, system: str, user: str) -> str:
        """Return LLM text response."""
        ...


class MockLLMClient(LLMClient):
    """Mock LLM that returns deterministic JSON based on keyword matching."""

    _responses: dict[str, str] = {}

    @classmethod
    def register(cls, trigger: str, response: str) -> None:
        cls._responses[trigger] = response

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
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        try:
            import anthropic
            if os.getenv("ANTHROPIC_API_KEY"):
                return _AnthropicClient(os.getenv("ANTHROPIC_API_KEY", ""))
            return _OpenAIClient(api_key)
        except ImportError:
            return MockLLMClient()
    return MockLLMClient()


class _OpenAIClient(LLMClient):
    def __init__(self, api_key: str):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key)
        self.model = os.getenv("LLM_MODEL", "gpt-4o-mini")

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

    def generate(self, system: str, user: str) -> str:
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text
