"""Integration tests for end-to-end workflows."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from doc_checker.checkers import DriftDetector
from doc_checker.cli import main
from doc_checker.formatters import format_report
from doc_checker.models import DriftReport


@pytest.fixture
def integration_project(tmp_path: Path) -> Path:
    """Create realistic test project."""
    # Create module
    module_dir = tmp_path / "my_lib"
    module_dir.mkdir()

    init_code = '''
"""My Library - Example quantum computing utilities."""

__version__ = "0.1.0"
__all__ = ["Simulator", "run_simulation", "QuantumState"]


class Simulator:
    """Quantum simulator class.

    This class provides methods to simulate quantum systems.

    Attributes:
        backend: Simulation backend to use
        precision: Numerical precision for calculations
    """

    def __init__(self, backend: str = "numpy", precision: float = 1e-10):
        """Initialize simulator.

        Args:
            backend: Backend to use (numpy, torch, jax)
            precision: Numerical precision threshold
        """
        self.backend = backend
        self.precision = precision

    def evolve(self, state, hamiltonian, time):
        """Evolve quantum state.

        This method evolves the quantum state using the Schrodinger equation.

        Args:
            state: Initial quantum state
            hamiltonian: Hamiltonian operator
            time: Evolution time

        Returns:
            Evolved quantum state
        """
        pass


class QuantumState:
    """Represents a quantum state."""

    def __init__(self, data):
        self.data = data


def run_simulation(config: dict) -> QuantumState:
    """Run quantum simulation with given configuration.

    Args:
        config: Configuration dictionary containing simulation parameters

    Returns:
        Final quantum state after simulation

    Example:
        >>> config = {"time": 10, "backend": "numpy"}
        >>> result = run_simulation(config)
    """
    pass
'''
    (module_dir / "__init__.py").write_text(init_code)

    # Create docs
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    index_md = docs_dir / "index.md"
    index_md.write_text(
        """
# My Library Documentation

Welcome to My Library!

::: my_lib.Simulator

::: my_lib.run_simulation

[External Link](https://example.com)
[Local Link](api.md)
"""
    )

    api_md = docs_dir / "api.md"
    api_md.write_text(
        """
# API Reference

::: my_lib.QuantumState
"""
    )

    # Create mkdocs.yml
    mkdocs_yml = tmp_path / "mkdocs.yml"
    mkdocs_yml.write_text(
        """
site_name: My Library
nav:
  - Home: index.md
  - API: api.md
"""
    )

    sys.path.insert(0, str(tmp_path))
    return tmp_path


def test_integration_full_report(integration_project: Path):
    """Test full drift detection report."""
    detector = DriftDetector(integration_project, modules=["my_lib"])
    report = detector.check_all()

    # Should detect no structural issues (all APIs documented)
    assert len(report.missing_in_docs) == 0
    assert len(report.broken_references) == 0
    assert len(report.broken_local_links) == 0
    assert len(report.broken_mkdocs_paths) == 0


def test_integration_report_formatting(integration_project: Path):
    """Test report can be formatted without errors."""
    detector = DriftDetector(integration_project, modules=["my_lib"])
    report = detector.check_all()

    # Format as text
    text_output = format_report(report)
    assert "DOCUMENTATION DRIFT REPORT" in text_output
    assert "=" * 60 in text_output

    # Format as JSON
    json_output = report.to_dict()
    assert "missing_in_docs" in json_output
    assert "broken_references" in json_output
    assert "quality_issues" in json_output
    assert "has_issues" in json_output


def test_format_report_external_links_summary():
    """Format report shows external links summary."""
    report = DriftReport(
        total_external_links=10,
        broken_external_links=[
            {
                "url": "https://bad.com",
                "status": 404,
                "location": "docs/a.md:1",
                "text": "bad",
            },
        ],
    )
    output = format_report(report)
    assert "External links: 1/10 broken" in output

    # No broken links
    report_ok = DriftReport(total_external_links=5)
    output_ok = format_report(report_ok)
    assert "External links: 0/5 broken" in output_ok

    # No external check run -> no summary line
    report_none = DriftReport()
    output_none = format_report(report_none)
    assert "External links" not in output_none


def test_integration_with_quality_checks_mocked(integration_project: Path):
    """Test integration with mocked LLM quality checks."""
    mock_checker = MagicMock()
    mock_checker.check_module_quality.return_value = [
        MagicMock(
            api_name="my_lib.Simulator.evolve",
            severity="warning",
            category="params",
            message="Parameter 'time' could use units specification",
            suggestion="Add: 'time (float): Evolution time in nanoseconds'",
            line_reference="time: Evolution time",
        ),
        MagicMock(
            api_name="my_lib.run_simulation",
            severity="suggestion",
            category="completeness",
            message="Could benefit from more detailed example",
            suggestion="Show example with actual output",
            line_reference=None,
        ),
    ]

    detector = DriftDetector(integration_project, modules=["my_lib"])

    with patch("doc_checker.llm_checker.QualityChecker") as mock_checker_class:
        mock_checker_class.return_value = mock_checker
        report = detector.check_all(check_quality=True, verbose=False)

    assert len(report.quality_issues) == 2
    assert report.has_issues() is True

    # Format report
    text_output = format_report(report)
    assert "Quality issues" in text_output
    assert "WARNING" in text_output
    assert "SUGGESTION" in text_output
    assert "my_lib.Simulator.evolve" in text_output


def test_integration_end_to_end_cli_style(integration_project: Path):
    """Test end-to-end workflow similar to CLI usage."""
    # Simulate CLI workflow
    detector = DriftDetector(
        root_path=integration_project,
        modules=["my_lib"],
        ignore_pulser_reexports=False,
    )

    # Run all checks (no external links, no quality)
    report = detector.check_all(
        check_external_links=False,
        check_quality=False,
        verbose=False,
    )

    # Verify report structure
    assert hasattr(report, "missing_in_docs")
    assert hasattr(report, "broken_references")
    assert hasattr(report, "quality_issues")
    assert hasattr(report, "warnings")

    # Format and verify output
    output = format_report(report)
    assert len(output) > 0
    assert "DOCUMENTATION DRIFT REPORT" in output


def test_integration_with_broken_docs(integration_project: Path):
    """Test detection of various documentation issues."""
    # Add broken reference
    index_md = integration_project / "docs" / "index.md"
    content = index_md.read_text()
    content += "\n::: my_lib.NonExistentClass\n"
    index_md.write_text(content)

    # Add missing local link
    content += "\n[Broken Link](nonexistent.md)\n"
    index_md.write_text(content)

    # Create undocumented function
    module_file = integration_project / "my_lib" / "__init__.py"
    content = module_file.read_text()
    content += "\n\ndef undocumented_func(x, y): return x + y\n"
    content = content.replace(
        '__all__ = ["Simulator", "run_simulation", "QuantumState"]',
        '__all__ = ["Simulator", "run_simulation", "QuantumState", "undocumented_func"]',  # noqa: E501
    )
    module_file.write_text(content)

    detector = DriftDetector(integration_project, modules=["my_lib"])
    report = detector.check_all()

    # Should detect issues
    assert len(report.broken_references) > 0
    assert len(report.broken_local_links) > 0
    # undocumented_func has no docstring, so it's missing from docs
    # Note: The test adds it to __all__, so it should be reported as missing
    assert report.has_issues() is True


def test_integration_json_output(integration_project: Path):
    """Test JSON serialization of full report."""
    detector = DriftDetector(integration_project, modules=["my_lib"])

    mock_checker = MagicMock()
    mock_checker.check_module_quality.return_value = [
        MagicMock(
            api_name="test",
            severity="critical",
            category="params",
            message="Issue",
            suggestion="Fix",
            line_reference=None,
        )
    ]

    with patch("doc_checker.llm_checker.QualityChecker") as mock_checker_class:
        mock_checker_class.return_value = mock_checker
        report = detector.check_all(check_quality=True)

    # Convert to dict (JSON-serializable)
    data = report.to_dict()

    assert isinstance(data, dict)
    assert "missing_in_docs" in data
    assert "quality_issues" in data
    assert isinstance(data["quality_issues"], list)

    if data["quality_issues"]:
        issue = data["quality_issues"][0]
        assert "api_name" in issue
        assert "severity" in issue
        assert "category" in issue
        assert "message" in issue
        assert "suggestion" in issue


def test_integration_multiple_modules(tmp_path: Path):
    """Test checking multiple modules."""
    # Create two modules
    for mod_name in ["mod_a", "mod_b"]:
        mod_dir = tmp_path / mod_name
        mod_dir.mkdir()
        (mod_dir / "__init__.py").write_text(
            f'"""Module {mod_name}."""\n__all__ = ["func"]\ndef func(): pass'
        )

    # Create docs
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "index.md").write_text("::: mod_a.func\n::: mod_b.func")

    mkdocs_yml = tmp_path / "mkdocs.yml"
    mkdocs_yml.write_text("nav:\n  - Home: index.md\n")

    sys.path.insert(0, str(tmp_path))

    detector = DriftDetector(tmp_path, modules=["mod_a", "mod_b"])
    report = detector.check_all()

    # Both modules should be checked
    assert len(report.missing_in_docs) == 0


class TestCLIBehavior:
    """Test CLI flag behaviors via DriftDetector."""

    def test_check_basic_runs_only_basic_checks(self, integration_project: Path):
        """Test --check-basic runs basic checks, skips external/quality."""
        detector = DriftDetector(integration_project, modules=["my_lib"])

        # Simulate --check-basic: basic checks, no external, no quality
        report = detector.check_all(
            check_external_links=False,
            check_quality=False,
        )

        # Basic checks should run (report has structure even if no issues)
        assert hasattr(report, "missing_in_docs")
        assert hasattr(report, "broken_references")
        assert hasattr(report, "undocumented_params")
        assert hasattr(report, "broken_local_links")
        assert hasattr(report, "broken_mkdocs_paths")

        # External and quality should be empty (not run)
        assert len(report.broken_external_links) == 0
        assert len(report.quality_issues) == 0

    def test_check_external_links_only(self, integration_project: Path):
        """Test --check-external-links runs only external link checks."""
        detector = DriftDetector(integration_project, modules=["my_lib"])

        # Simulate --check-external-links: skip basic, only external
        report = detector.check_all(
            check_external_links=True,
            skip_basic_checks=True,
        )

        # Basic checks should be empty (skipped)
        assert len(report.missing_in_docs) == 0
        assert len(report.broken_references) == 0
        assert len(report.undocumented_params) == 0
        assert len(report.broken_local_links) == 0
        assert len(report.broken_mkdocs_paths) == 0

        # Quality should be empty (not enabled)
        assert len(report.quality_issues) == 0

    def test_check_quality_runs_basic_and_quality(self, integration_project: Path):
        """Test --check-quality runs basic + quality, no external links."""
        detector = DriftDetector(integration_project, modules=["my_lib"])

        mock_checker = MagicMock()
        mock_checker.check_module_quality.return_value = []

        with patch("doc_checker.llm_checker.QualityChecker") as mock_cls:
            mock_cls.return_value = mock_checker
            # Simulate --check-quality: basic + quality, no external
            report = detector.check_all(
                check_external_links=False,
                check_quality=True,
            )

        # Basic checks ran
        assert hasattr(report, "missing_in_docs")
        assert hasattr(report, "broken_references")

        # External links not checked
        assert len(report.broken_external_links) == 0

        # Quality checker was called
        mock_checker.check_module_quality.assert_called()

    def test_check_all_runs_everything(self, integration_project: Path):
        """Test --check-all (default) runs all checks."""
        detector = DriftDetector(integration_project, modules=["my_lib"])

        mock_checker = MagicMock()
        mock_checker.check_module_quality.return_value = []

        with patch("doc_checker.llm_checker.QualityChecker") as mock_cls:
            mock_cls.return_value = mock_checker
            report = detector.check_all(
                check_external_links=True,
                check_quality=True,
            )

        # Basic checks ran (has structure)
        assert hasattr(report, "missing_in_docs")
        assert hasattr(report, "broken_references")

        # Quality checker was called
        mock_checker.check_module_quality.assert_called()


class TestWarnOnly:
    """Test --warn-only flag."""

    def test_warn_only_exits_zero_with_issues(self, integration_project: Path):
        """--warn-only should exit 0 even when issues exist."""
        index_md = integration_project / "docs" / "index.md"
        content = index_md.read_text()
        content += "\n::: my_lib.NonExistentClass\n"
        index_md.write_text(content)

        argv = [
            "doc-checker",
            "--check-basic",
            "--warn-only",
            "--modules",
            "my_lib",
            "--root",
            str(integration_project),
        ]
        with patch("sys.argv", argv):
            assert main() == 0

    def test_without_warn_only_exits_one_with_issues(self, integration_project: Path):
        """Without --warn-only should exit 1 when issues exist."""
        index_md = integration_project / "docs" / "index.md"
        content = index_md.read_text()
        content += "\n::: my_lib.NonExistentClass\n"
        index_md.write_text(content)

        argv = [
            "doc-checker",
            "--check-basic",
            "--modules",
            "my_lib",
            "--root",
            str(integration_project),
        ]
        with patch("sys.argv", argv):
            assert main() == 1
