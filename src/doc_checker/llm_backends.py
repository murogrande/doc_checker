"""LLM backend abstraction layer."""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Any


class LLMBackend(ABC):
    """Abstract base for LLM backends."""

    model: str

    @abstractmethod
    def generate(self, prompt: str, temperature: float = 0.1) -> str:
        """Generate completion from prompt."""
        pass

    def generate_json(self, prompt: str, temperature: float = 0.1) -> dict[str, Any]:
        """Generate and parse JSON response."""
        response: str = self.generate(prompt, temperature)
        # Extract JSON from markdown code blocks if present
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            response = response[start:end].strip()
        elif "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            response = response[start:end].strip()

        try:
            result: dict[str, Any] = json.loads(response)
            return result
        except json.JSONDecodeError as e:
            # Fallback: return error structure
            return {
                "error": f"Failed to parse JSON: {e}",
                "raw_response": response,
                "issues": [],
                "score": 0,
                "summary": "Failed to parse LLM response",
            }


class OllamaBackend(LLMBackend):
    """Ollama local LLM backend (default)."""

    def __init__(self, model: str = "qwen2.5:3b"):
        """Initialize Ollama backend.

        Args:
            model: Model name (qwen2.5:3b, llama3.2:3b, phi3.5, gemma2:2b)

        Raises:
            ImportError: If ollama package not installed
            RuntimeError: If Ollama service not running
        """
        try:
            import ollama  # TODO: ollama should be in requirements.txt
        except ImportError:
            raise ImportError(
                "ollama package required. Install with: pip install ollama\n"
                "Then install Ollama: https://ollama.ai/download"
            )
        self.client = ollama
        self.model = model

        # Test connection
        try:
            self.client.list()
        except Exception as e:
            raise RuntimeError(
                f"Ollama service not running. Start with: ollama serve\n" f"Error: {e}"
            )

    def generate(self, prompt: str, temperature: float = 0.1) -> str:
        """Generate completion via Ollama."""
        response = self.client.generate(
            model=self.model,
            prompt=prompt,
            options={
                "temperature": temperature,
                "num_predict": 1024,
            },
        )
        result: str = response["response"]
        return result


class OpenAIBackend(LLMBackend):
    """OpenAI API backend."""

    def __init__(self, model: str = "gpt-5.2", api_key: str | None = None):
        """Initialize OpenAI backend.

        Args:
            model: Model name (gpt-5.2 recommended)
            api_key: API key (defaults to OPENAI_API_KEY env var)

        Raises:
            ImportError: If openai package not installed
            ValueError: If API key not provided
        """
        try:
            from openai import (
                OpenAI,
            )  # TODO: openai should be in requirements.txt or others like anthropic
        except ImportError:
            raise ImportError("openai package required. Install with: pip install openai")

        # Get API key with priority: explicit > env var
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY env var:\n"
                "  export OPENAI_API_KEY='sk-proj-...'\n"
                "Or pass api_key parameter explicitly."
            )

        self.client = OpenAI(api_key=self.api_key)
        self.model = model

    def generate(self, prompt: str, temperature: float = 0.1) -> str:
        """Generate completion via OpenAI."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_completion_tokens=1024,
        )
        return response.choices[0].message.content or ""


def get_backend(
    backend_type: str = "ollama",
    model: str | None = None,
    api_key: str | None = None,
) -> LLMBackend:
    """Factory to get LLM backend.

    Args:
        backend_type: "ollama" (default, local) or "openai" (API)
        model: Model name (uses sensible defaults if None)
        api_key: API key for OpenAI backend

    Returns:
        Configured LLM backend

    Raises:
        ValueError: If backend_type unknown
        ImportError: If required package not installed
        RuntimeError: If backend not available
    """
    if backend_type == "ollama":
        return OllamaBackend(model or "qwen2.5:3b")
    elif backend_type == "openai":
        return OpenAIBackend(model or "gpt-4o-mini", api_key)
    else:
        raise ValueError(f"Unknown backend: {backend_type}. Choose from: ollama, openai")
