"""Tests for LLM quality checker."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from doc_checker.llm_checker import QualityChecker
from doc_checker.models import SignatureInfo


@pytest.fixture
def mock_backend():
    """Mock LLM backend."""
    backend = MagicMock()
    backend.generate_json.return_value = {
        "issues": [
            {
                "severity": "warning",
                "category": "grammar",
                "message": "Test issue",
                "suggestion": "Fix it",
                "line_reference": "test text",
            }
        ],
        "score": 85,
        "summary": "Good overall",
    }
    return backend


@pytest.fixture
def mock_code_analyzer(tmp_path: Path):
    """Mock code analyzer."""
    analyzer = MagicMock()
    apis = [
        SignatureInfo(
            name="test_func",
            module="test_module",
            parameters=["x: int", "y: str = 'default'"],
            return_annotation="bool",
            docstring="Test function docstring.",
            is_public=True,
            kind="function",
        ),
        SignatureInfo(
            name="no_docstring_func",
            module="test_module",
            parameters=[],
            return_annotation=None,
            docstring=None,
            is_public=True,
            kind="function",
        ),
    ]
    analyzer.get_public_apis.return_value = apis
    analyzer.get_all_public_apis.return_value = apis
    return analyzer


@patch("doc_checker.llm_checker.get_backend")
@patch("doc_checker.llm_checker.CodeAnalyzer")
def test_quality_checker_init(mock_analyzer_class, mock_get_backend, tmp_path):
    """Test QualityChecker initialization."""
    mock_backend = MagicMock()
    mock_get_backend.return_value = mock_backend
    mock_analyzer_class.return_value = MagicMock()

    checker = QualityChecker(
        tmp_path, backend_type="ollama", model="qwen2.5:3b", api_key=None
    )

    assert checker.root_path == tmp_path
    assert checker.backend == mock_backend
    mock_get_backend.assert_called_once_with("ollama", "qwen2.5:3b", None)
    mock_analyzer_class.assert_called_once_with(tmp_path)


@patch("doc_checker.llm_checker.get_backend")
@patch("doc_checker.llm_checker.CodeAnalyzer")
def test_quality_checker_check_api_quality_success(
    mock_analyzer_class, mock_get_backend, tmp_path, mock_backend, mock_code_analyzer
):
    """Test successful API quality check."""
    mock_get_backend.return_value = mock_backend
    mock_analyzer_class.return_value = mock_code_analyzer

    checker = QualityChecker(tmp_path)
    issues = checker.check_api_quality("test_func", "test_module", verbose=False)

    assert len(issues) == 1
    assert issues[0].api_name == "test_module.test_func"
    assert issues[0].severity == "warning"
    assert issues[0].category == "grammar"
    assert issues[0].message == "Test issue"
    assert issues[0].suggestion == "Fix it"
    assert issues[0].line_reference == "test text"


@patch("doc_checker.llm_checker.get_backend")
@patch("doc_checker.llm_checker.CodeAnalyzer")
def test_quality_checker_api_not_found(
    mock_analyzer_class, mock_get_backend, tmp_path, mock_backend, mock_code_analyzer
):
    """Test quality check for non-existent API."""
    mock_get_backend.return_value = mock_backend
    mock_analyzer_class.return_value = mock_code_analyzer

    checker = QualityChecker(tmp_path)
    issues = checker.check_api_quality("nonexistent", "test_module")

    assert len(issues) == 1
    assert issues[0].severity == "critical"
    assert issues[0].category == "error"
    assert "not found" in issues[0].message


@patch("doc_checker.llm_checker.get_backend")
@patch("doc_checker.llm_checker.CodeAnalyzer")
def test_quality_checker_no_docstring(
    mock_analyzer_class, mock_get_backend, tmp_path, mock_backend, mock_code_analyzer
):
    """Test quality check for API without docstring."""
    mock_get_backend.return_value = mock_backend
    mock_analyzer_class.return_value = mock_code_analyzer

    checker = QualityChecker(tmp_path)
    issues = checker.check_api_quality("no_docstring_func", "test_module")

    assert len(issues) == 1
    assert issues[0].severity == "critical"
    assert issues[0].category == "completeness"
    assert "No docstring" in issues[0].message


@patch("doc_checker.llm_checker.get_backend")
@patch("doc_checker.llm_checker.CodeAnalyzer")
def test_quality_checker_llm_failure(
    mock_analyzer_class, mock_get_backend, tmp_path, mock_code_analyzer
):
    """Test quality check handles LLM failures gracefully."""
    mock_backend = MagicMock()
    mock_backend.generate_json.side_effect = Exception("LLM error")
    mock_get_backend.return_value = mock_backend
    mock_analyzer_class.return_value = mock_code_analyzer

    checker = QualityChecker(tmp_path)
    issues = checker.check_api_quality("test_func", "test_module")

    assert len(issues) == 1
    assert issues[0].severity == "warning"
    assert issues[0].category == "error"
    assert "LLM check failed" in issues[0].message


@patch("doc_checker.llm_checker.get_backend")
@patch("doc_checker.llm_checker.CodeAnalyzer")
def test_quality_checker_verbose_output(
    mock_analyzer_class,
    mock_get_backend,
    tmp_path,
    mock_backend,
    mock_code_analyzer,
    capsys,
):
    """Test quality checker verbose output."""
    mock_get_backend.return_value = mock_backend
    mock_analyzer_class.return_value = mock_code_analyzer

    checker = QualityChecker(tmp_path)
    checker.check_api_quality("test_func", "test_module", verbose=True)

    captured = capsys.readouterr()
    assert "Checking test_module.test_func" in captured.out
    assert "Found 1 issues" in captured.out
    assert "score: 85" in captured.out


@patch("doc_checker.llm_checker.get_backend")
@patch("doc_checker.llm_checker.CodeAnalyzer")
def test_quality_checker_check_module_quality(
    mock_analyzer_class, mock_get_backend, tmp_path, mock_backend, mock_code_analyzer
):
    """Test checking entire module quality."""
    mock_get_backend.return_value = mock_backend
    mock_analyzer_class.return_value = mock_code_analyzer

    checker = QualityChecker(tmp_path)
    issues = checker.check_module_quality("test_module", verbose=False)

    # Checks both: test_func (LLM issue) and no_docstring_func (no docstring)
    assert len(issues) == 2
    names = {i.api_name for i in issues}
    assert "test_module.test_func" in names
    assert "test_module.no_docstring_func" in names


@patch("doc_checker.llm_checker.get_backend")
@patch("doc_checker.llm_checker.CodeAnalyzer")
def test_quality_checker_sample_rate(
    mock_analyzer_class, mock_get_backend, tmp_path, mock_backend
):
    """Test quality checker sampling."""
    # Create 10 APIs
    apis = [
        SignatureInfo(
            name=f"func_{i}",
            module="test_module",
            parameters=[],
            return_annotation=None,
            docstring=f"Function {i}",
            is_public=True,
            kind="function",
        )
        for i in range(10)
    ]

    mock_analyzer = MagicMock()
    mock_analyzer.get_public_apis.return_value = apis
    mock_analyzer.get_all_public_apis.return_value = apis
    mock_analyzer_class.return_value = mock_analyzer
    mock_get_backend.return_value = mock_backend

    checker = QualityChecker(tmp_path)
    issues = checker.check_module_quality("test_module", verbose=False, sample_rate=0.3)

    # Should check ~3 APIs (30% of 10)
    # Each API generates 1 issue, so ~3 issues
    assert 1 <= len(issues) <= 5  # Allow some variance due to random sampling


@patch("doc_checker.llm_checker.get_backend")
@patch("doc_checker.llm_checker.CodeAnalyzer")
def test_quality_checker_multiple_issues(
    mock_analyzer_class, mock_get_backend, tmp_path, mock_code_analyzer
):
    """Test quality check with multiple issues."""
    mock_backend = MagicMock()
    mock_backend.generate_json.return_value = {
        "issues": [
            {
                "severity": "critical",
                "category": "params",
                "message": "Missing parameter",
                "suggestion": "Add param doc",
                "line_reference": None,
            },
            {
                "severity": "warning",
                "category": "grammar",
                "message": "Typo",
                "suggestion": "Fix spelling",
                "line_reference": "speling",
            },
            {
                "severity": "suggestion",
                "category": "completeness",
                "message": "Add example",
                "suggestion": "Show usage",
                "line_reference": None,
            },
        ],
        "score": 65,
        "summary": "Needs improvement",
    }
    mock_get_backend.return_value = mock_backend
    mock_analyzer_class.return_value = mock_code_analyzer

    checker = QualityChecker(tmp_path)
    issues = checker.check_api_quality("test_func", "test_module")

    assert len(issues) == 3
    assert issues[0].severity == "critical"
    assert issues[1].severity == "warning"
    assert issues[2].severity == "suggestion"


@patch("doc_checker.llm_checker.get_backend")
@patch("doc_checker.llm_checker.CodeAnalyzer")
def test_quality_checker_no_issues(
    mock_analyzer_class, mock_get_backend, tmp_path, mock_code_analyzer
):
    """Test quality check with perfect documentation."""
    mock_backend = MagicMock()
    mock_backend.generate_json.return_value = {
        "issues": [],
        "score": 100,
        "summary": "Perfect documentation",
    }
    mock_get_backend.return_value = mock_backend
    mock_analyzer_class.return_value = mock_code_analyzer

    checker = QualityChecker(tmp_path)
    issues = checker.check_api_quality("test_func", "test_module")

    assert len(issues) == 0


@patch("doc_checker.llm_checker.get_backend")
@patch("doc_checker.llm_checker.CodeAnalyzer")
def test_quality_checker_empty_module(
    mock_analyzer_class, mock_get_backend, tmp_path, mock_backend
):
    """Test quality check on module with no APIs."""
    mock_analyzer = MagicMock()
    mock_analyzer.get_public_apis.return_value = []
    mock_analyzer.get_all_public_apis.return_value = []
    mock_analyzer_class.return_value = mock_analyzer
    mock_get_backend.return_value = mock_backend

    checker = QualityChecker(tmp_path)
    issues = checker.check_module_quality("empty_module")

    assert len(issues) == 1
    assert "No public APIs found" in issues[0].message
