"""Tests for prompt templates."""

from __future__ import annotations

from doc_checker.prompts import (
    get_code_alignment_prompt,
    get_combined_quality_prompt,
    get_completeness_prompt,
    get_english_quality_prompt,
)


def test_english_quality_prompt_basic():
    """Test English quality prompt generation."""
    docstring = "This is a test docstring."
    api_name = "module.function"

    prompt = get_english_quality_prompt(docstring, api_name)

    assert "module.function" in prompt
    assert "This is a test docstring." in prompt
    assert "grammar" in prompt.lower()
    assert "JSON" in prompt
    assert "severity" in prompt


def test_english_quality_prompt_multiline():
    """Test English quality prompt with multiline docstring."""
    docstring = """
    This is a longer docstring.

    It has multiple lines.
    And paragraphs.
    """
    api_name = "module.Class.method"

    prompt = get_english_quality_prompt(docstring, api_name)

    assert "module.Class.method" in prompt
    assert "multiple lines" in prompt


def test_code_alignment_prompt_basic():
    """Test code alignment prompt generation."""
    signature = "def foo(x: int, y: str = 'default') -> bool"
    docstring = "Does something with x and y."
    api_name = "module.foo"

    prompt = get_code_alignment_prompt(signature, docstring, api_name)

    assert "module.foo" in prompt
    assert signature in prompt
    assert docstring in prompt
    assert "Parameter descriptions match signature" in prompt


def test_code_alignment_prompt_with_code_snippet():
    """Test code alignment prompt includes code snippet."""
    signature = "def bar(x: int) -> int"
    docstring = "Returns x + 1"
    api_name = "module.bar"
    code_snippet = "    return x + 1"

    prompt = get_code_alignment_prompt(signature, docstring, api_name, code_snippet)

    assert "module.bar" in prompt
    assert signature in prompt
    assert docstring in prompt
    assert "return x + 1" in prompt
    assert "Code implementation" in prompt


def test_code_alignment_prompt_no_code_snippet():
    """Test code alignment prompt without code snippet."""
    signature = "def bar(x: int) -> int"
    docstring = "Returns x + 1"
    api_name = "module.bar"

    prompt = get_code_alignment_prompt(signature, docstring, api_name, None)

    assert "module.bar" in prompt
    assert signature in prompt
    assert "Code implementation" not in prompt


def test_completeness_prompt_basic():
    """Test completeness prompt generation."""
    signature = "def test(a: int, b: str = 'default') -> None"
    docstring = "Test function."
    api_name = "module.test"

    prompt = get_completeness_prompt(signature, docstring, api_name)

    assert "module.test" in prompt
    assert signature in prompt
    assert docstring in prompt
    assert "All parameters documented" in prompt


def test_completeness_prompt_public_api():
    """Test completeness prompt for public API."""
    signature = "def public_func() -> int"
    docstring = "Public function."
    api_name = "module.public_func"

    prompt = get_completeness_prompt(signature, docstring, api_name, is_public=True)

    assert "PUBLIC API" in prompt
    assert "users depend on complete docs" in prompt


def test_completeness_prompt_private_api():
    """Test completeness prompt for private API."""
    signature = "def _private_func() -> int"
    docstring = "Private function."
    api_name = "module._private_func"

    prompt = get_completeness_prompt(signature, docstring, api_name, is_public=False)

    assert "PUBLIC API" not in prompt


def test_combined_quality_prompt_basic():
    """Test combined quality prompt generation."""
    signature = "def combined(x: int, y: str) -> bool"
    docstring = "Combined test function."
    api_name = "module.combined"

    prompt = get_combined_quality_prompt(signature, docstring, api_name)

    assert "module.combined" in prompt
    assert signature in prompt
    assert docstring in prompt
    assert "English Quality" in prompt
    assert "Code Alignment" in prompt
    assert "Completeness" in prompt
    assert "Technical Accuracy" in prompt


def test_combined_quality_prompt_with_code():
    """Test combined quality prompt includes code snippet."""
    signature = "def func(x: int) -> int"
    docstring = "Returns doubled value."
    api_name = "module.func"
    code_snippet = "    return x * 2"

    prompt = get_combined_quality_prompt(signature, docstring, api_name, code_snippet)

    assert "return x * 2" in prompt
    assert "Code implementation" in prompt


def test_all_prompts_request_json():
    """Test all prompts request JSON format."""
    sig = "def f() -> None"
    doc = "Test"
    api = "module.f"

    prompts = [
        get_english_quality_prompt(doc, api),
        get_code_alignment_prompt(sig, doc, api),
        get_completeness_prompt(sig, doc, api),
        get_combined_quality_prompt(sig, doc, api),
    ]

    for prompt in prompts:
        assert "JSON" in prompt
        assert "issues" in prompt
        assert "severity" in prompt
        assert "score" in prompt


def test_all_prompts_request_examples():
    """Test all prompts request examples in responses."""
    sig = "def f() -> None"
    doc = "Test"
    api = "module.f"

    prompts = [
        get_english_quality_prompt(doc, api),
        get_code_alignment_prompt(sig, doc, api),
        get_completeness_prompt(sig, doc, api),
        get_combined_quality_prompt(sig, doc, api),
    ]

    for prompt in prompts:
        # Check for example-related keywords
        assert (
            "example" in prompt.lower()
            or "before/after" in prompt.lower()
            or "concrete" in prompt.lower()
        )


def test_prompts_specify_severity_levels():
    """Test all prompts specify severity levels."""
    sig = "def f() -> None"
    doc = "Test"
    api = "module.f"

    prompts = [
        get_english_quality_prompt(doc, api),
        get_code_alignment_prompt(sig, doc, api),
        get_completeness_prompt(sig, doc, api),
        get_combined_quality_prompt(sig, doc, api),
    ]

    for prompt in prompts:
        assert "critical" in prompt
        assert "warning" in prompt
        assert "suggestion" in prompt


def test_prompts_include_api_name():
    """Test all prompts include the API name."""
    sig = "def unique_api_name_12345() -> None"
    doc = "Test docstring"
    api = "module.unique_api_name_12345"

    prompts = [
        get_english_quality_prompt(doc, api),
        get_code_alignment_prompt(sig, doc, api),
        get_completeness_prompt(sig, doc, api),
        get_combined_quality_prompt(sig, doc, api),
    ]

    for prompt in prompts:
        assert "unique_api_name_12345" in prompt
