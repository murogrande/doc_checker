"""Tests for LLM backends."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from doc_checker.llm_backends import (
    LLMBackend,
    OllamaBackend,
    OpenAIBackend,
    get_backend,
)


class MockLLMBackend(LLMBackend):
    """Mock LLM backend for testing."""

    def __init__(self, responses: list[str] | None = None):
        self.responses = responses or ["test response"]
        self.call_count = 0

    def generate(self, prompt: str, temperature: float = 0.1) -> str:
        response = self.responses[min(self.call_count, len(self.responses) - 1)]
        self.call_count += 1
        return response


def test_llm_backend_abstract():
    """Test LLMBackend cannot be instantiated directly."""
    with pytest.raises(TypeError):
        LLMBackend()  # type: ignore


def test_mock_backend_generate():
    """Test mock backend generates responses."""
    backend = MockLLMBackend(["response 1", "response 2"])

    assert backend.generate("test prompt") == "response 1"
    assert backend.generate("test prompt") == "response 2"
    assert backend.call_count == 2


def test_generate_json_success():
    """Test successful JSON parsing from LLM response."""
    backend = MockLLMBackend(['{"key": "value", "number": 42}'])
    result = backend.generate_json("test")

    assert result == {"key": "value", "number": 42}


def test_generate_json_with_markdown_block():
    """Test JSON extraction from markdown code block."""
    response = '```json\n{"key": "value"}\n```'
    backend = MockLLMBackend([response])
    result = backend.generate_json("test")

    assert result == {"key": "value"}


def test_generate_json_with_generic_code_block():
    """Test JSON extraction from generic code block."""
    response = '```\n{"key": "value"}\n```'
    backend = MockLLMBackend([response])
    result = backend.generate_json("test")

    assert result == {"key": "value"}


def test_generate_json_invalid():
    """Test graceful handling of invalid JSON."""
    backend = MockLLMBackend(["not valid json"])
    result = backend.generate_json("test")

    assert "error" in result
    assert result["issues"] == []
    assert result["score"] == 0


@pytest.mark.skipif(True, reason="Requires ollama package - tested via integration")
def test_ollama_backend_init():
    """Test OllamaBackend initialization."""
    pass


@pytest.mark.skipif(True, reason="Requires ollama package - tested via integration")
def test_ollama_backend_default_model():
    """Test OllamaBackend uses correct default model."""
    pass


@pytest.mark.skipif(True, reason="Requires ollama package - tested via integration")
def test_ollama_backend_generate():
    """Test OllamaBackend generates responses."""
    pass


def test_ollama_backend_missing_package():
    """Test OllamaBackend raises error if ollama not installed."""
    with patch.dict("sys.modules", {"ollama": None}):
        with pytest.raises(ImportError, match="ollama package required"):
            OllamaBackend()


@pytest.mark.skipif(True, reason="Requires ollama package - tested via integration")
def test_ollama_backend_service_not_running():
    """Test OllamaBackend raises error if service not running."""
    pass


@pytest.mark.skipif(True, reason="Requires openai package - tested via integration")
def test_openai_backend_init():
    """Test OpenAIBackend initialization."""
    with patch("openai.OpenAI") as mock_openai_class:
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        backend = OpenAIBackend(model="gpt-4o", api_key="test-key")

        assert backend.model == "gpt-4o"
        assert backend.api_key == "test-key"
        mock_openai_class.assert_called_once_with(api_key="test-key")


@pytest.mark.skipif(True, reason="Requires openai package - tested via integration")
def test_openai_backend_default_model():
    """Test OpenAIBackend uses correct default model."""
    with patch("openai.OpenAI") as mock_openai_class:
        mock_openai_class.return_value = MagicMock()
        backend = OpenAIBackend(api_key="test-key")
        assert backend.model == "gpt-4o-mini"


@pytest.mark.skipif(True, reason="Requires openai package - tested via integration")
def test_openai_backend_api_key_from_env():
    """Test OpenAIBackend reads API key from environment."""
    pass


@pytest.mark.skipif(True, reason="Requires openai package - tested via integration")
def test_openai_backend_no_api_key():
    """Test OpenAIBackend raises error if no API key provided."""
    pass


@pytest.mark.skipif(True, reason="Requires openai package - tested via integration")
def test_openai_backend_generate():
    """Test OpenAIBackend generates responses."""
    pass


def test_openai_backend_missing_package():
    """Test OpenAIBackend raises error if openai not installed."""
    with patch.dict("sys.modules", {"openai": None}):
        with pytest.raises(ImportError, match="openai package required"):
            OpenAIBackend(api_key="test-key")


@patch("doc_checker.llm_backends.OllamaBackend")
def test_get_backend_ollama_default(mock_ollama_class):
    """Test get_backend returns OllamaBackend by default."""
    mock_backend = MagicMock()
    mock_ollama_class.return_value = mock_backend

    backend = get_backend()

    assert backend == mock_backend
    mock_ollama_class.assert_called_once_with("qwen2.5:3b")


@patch("doc_checker.llm_backends.OllamaBackend")
def test_get_backend_ollama_custom_model(mock_ollama_class):
    """Test get_backend with custom Ollama model."""
    mock_backend = MagicMock()
    mock_ollama_class.return_value = mock_backend

    backend = get_backend(backend_type="ollama", model="llama3.2:3b")

    assert backend == mock_backend
    mock_ollama_class.assert_called_once_with("llama3.2:3b")


@patch("doc_checker.llm_backends.OpenAIBackend")
def test_get_backend_openai(mock_openai_class):
    """Test get_backend returns OpenAIBackend."""
    mock_backend = MagicMock()
    mock_openai_class.return_value = mock_backend

    backend = get_backend(backend_type="openai", api_key="test-key")

    assert backend == mock_backend
    mock_openai_class.assert_called_once_with("gpt-4o-mini", "test-key")


@patch("doc_checker.llm_backends.OpenAIBackend")
def test_get_backend_openai_custom_model(mock_openai_class):
    """Test get_backend with custom OpenAI model."""
    mock_backend = MagicMock()
    mock_openai_class.return_value = mock_backend

    backend = get_backend(backend_type="openai", model="gpt-4o", api_key="test-key")

    assert backend == mock_backend
    mock_openai_class.assert_called_once_with("gpt-4o", "test-key")


def test_get_backend_unknown():
    """Test get_backend raises error for unknown backend."""
    with pytest.raises(ValueError, match="Unknown backend: invalid"):
        get_backend(backend_type="invalid")
