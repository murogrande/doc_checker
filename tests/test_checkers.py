"""Tests for checkers module."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from doc_checker.checkers import DriftDetector


@pytest.fixture
def test_project(tmp_path: Path) -> Path:
    """Create a test project structure."""
    # Create module
    module_dir = tmp_path / "test_pkg"
    module_dir.mkdir()
    init_file = module_dir / "__init__.py"
    code = '''
"""Test package."""

__all__ = ["TestClass", "test_function"]


class TestClass:
    """A test class."""

    def __init__(self, param1: int):
        """Initialize.

        Args:
            param1: First parameter
        """
        self.param1 = param1


def test_function(x: int, y: int = 10) -> int:
    """Test function.

    Args:
        x: First arg
    """
    return x + y
'''
    init_file.write_text(code)

    # Create docs
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    index_md = docs_dir / "index.md"
    index_md.write_text(
        """
# Documentation

::: test_pkg.TestClass

External link: [Example](https://example.com)
Local link: [Script](../script.py)
"""
    )

    # Create mkdocs.yml
    mkdocs_yml = tmp_path / "mkdocs.yml"
    mkdocs_yml.write_text(
        """
nav:
  - Home: index.md
"""
    )

    # Add to sys.path
    sys.path.insert(0, str(tmp_path))

    return tmp_path


class TestDriftDetector:
    """Test DriftDetector."""

    def test_check_api_coverage_missing(self, test_project: Path):
        detector = DriftDetector(test_project, modules=["test_pkg"])
        report = detector.check_all()

        # test_function is missing from docs
        assert "test_pkg.test_function" in report.missing_in_docs
        # TestClass is documented
        assert "test_pkg.TestClass" not in report.missing_in_docs

    def test_check_api_coverage_documented(self, test_project: Path):
        detector = DriftDetector(test_project, modules=["test_pkg"])

        # Add test_function to docs
        index_md = test_project / "docs" / "index.md"
        content = index_md.read_text()
        content += "\n::: test_pkg.test_function\n"
        index_md.write_text(content)

        report = detector.check_all()
        assert "test_pkg.test_function" not in report.missing_in_docs

    def test_check_references_valid(self, test_project: Path):
        detector = DriftDetector(test_project, modules=["test_pkg"])
        report = detector.check_all()

        # TestClass reference should be valid
        assert not any("test_pkg.TestClass" in ref for ref in report.broken_references)

    def test_check_references_invalid(self, test_project: Path):
        # Add invalid reference
        index_md = test_project / "docs" / "index.md"
        content = index_md.read_text()
        content += "\n::: test_pkg.NonExistent\n"
        index_md.write_text(content)

        detector = DriftDetector(test_project, modules=["test_pkg"])
        report = detector.check_all()

        assert any("NonExistent" in ref for ref in report.broken_references)

    def test_check_param_docs(self, test_project: Path):
        detector = DriftDetector(test_project, modules=["test_pkg"])
        report = detector.check_all()

        # test_function has undocumented param 'y'
        undoc = [u for u in report.undocumented_params if "test_function" in u["name"]]
        assert len(undoc) == 1
        assert "y" in undoc[0]["params"]

    def test_check_local_links_missing(self, test_project: Path):
        detector = DriftDetector(test_project, modules=["test_pkg"])
        report = detector.check_all()

        # ../script.py doesn't exist
        assert len(report.broken_local_links) == 1
        assert "../script.py" in report.broken_local_links[0]["path"]

    def test_check_local_links_exists(self, test_project: Path):
        # Create the script file
        script = test_project / "script.py"
        script.write_text("# Script")

        detector = DriftDetector(test_project, modules=["test_pkg"])
        report = detector.check_all()

        # Link should now be valid
        assert not any(
            "../script.py" in link["path"] for link in report.broken_local_links
        )

    def test_check_local_links_mkdocs_url_style(self, test_project: Path):
        """Test mkdocs URL-style resolution for notebook internal links."""
        import json

        # Create structure: docs/pkg/notebooks/tutorial.ipynb
        # with link ../../advanced/guide/ -> docs/pkg/advanced/guide.md
        notebooks = test_project / "docs" / "pkg" / "notebooks"
        notebooks.mkdir(parents=True)
        advanced = test_project / "docs" / "pkg" / "advanced"
        advanced.mkdir(parents=True)

        # Create notebook with mkdocs-style internal link
        nb = {"cells": [{"source": ["See [guide](../../advanced/guide/#section)\n"]}]}
        (notebooks / "tutorial.ipynb").write_text(json.dumps(nb))

        # Create target file (mkdocs resolves guide/ to guide.md)
        (advanced / "guide.md").write_text("# Guide")

        detector = DriftDetector(test_project, modules=["test_pkg"])
        report = detector.check_all()

        # Link should resolve via mkdocs URL-style (not file-style)
        assert not any("guide" in link["path"] for link in report.broken_local_links)

    def test_check_local_links_notebook_without_extension(self, test_project: Path):
        """Test notebook link to notebook without .ipynb extension."""
        import json

        # Create structure: docs/pkg_a/notebooks/source.ipynb
        # with link ../../../pkg_b/notebooks/target -> docs/pkg_b/notebooks/target.ipynb
        pkg_a = test_project / "docs" / "pkg_a" / "notebooks"
        pkg_a.mkdir(parents=True)
        pkg_b = test_project / "docs" / "pkg_b" / "notebooks"
        pkg_b.mkdir(parents=True)

        # Create notebook with link to another notebook without extension
        nb = {"cells": [{"source": ["See [other](../../../pkg_b/notebooks/target)\n"]}]}
        (pkg_a / "source.ipynb").write_text(json.dumps(nb))

        # Create target notebook
        target_nb = {"cells": [{"source": ["# Target"]}]}
        (pkg_b / "target.ipynb").write_text(json.dumps(target_nb))

        detector = DriftDetector(test_project, modules=["test_pkg"])
        report = detector.check_all()

        # Link should resolve to .ipynb file (notebooks can omit extension)
        assert not any("target" in link["path"] for link in report.broken_local_links)

    def test_check_local_links_md_to_notebook_requires_extension(
        self, test_project: Path
    ):
        """Test markdown link to notebook MUST have .ipynb extension."""
        import json

        # Create structure: docs/benchmarks/perf.md
        # with link ../notebooks/tutorial (no extension) -> should be broken
        benchmarks = test_project / "docs" / "benchmarks"
        benchmarks.mkdir(parents=True)
        notebooks = test_project / "docs" / "notebooks"
        notebooks.mkdir(parents=True)

        # Create markdown with link to notebook WITHOUT extension
        (benchmarks / "perf.md").write_text(
            "See [tutorial](../notebooks/tutorial) for details.\n"
        )

        # Create target notebook
        target_nb = {"cells": [{"source": ["# Tutorial"]}]}
        (notebooks / "tutorial.ipynb").write_text(json.dumps(target_nb))

        detector = DriftDetector(test_project, modules=["test_pkg"])
        report = detector.check_all()

        # Link should be broken - markdown files must include .ipynb extension
        assert any("tutorial" in link["path"] for link in report.broken_local_links)

    def test_check_mkdocs_paths(self, test_project: Path):
        detector = DriftDetector(test_project, modules=["test_pkg"])
        report = detector.check_all()

        # index.md exists, so no broken paths
        assert len(report.broken_mkdocs_paths) == 0

    def test_check_mkdocs_paths_broken(self, test_project: Path):
        # Add broken path to mkdocs.yml
        mkdocs_yml = test_project / "mkdocs.yml"
        content = mkdocs_yml.read_text()
        content += "  - Missing: missing.md\n"
        mkdocs_yml.write_text(content)

        detector = DriftDetector(test_project, modules=["test_pkg"])
        report = detector.check_all()

        assert len(report.broken_mkdocs_paths) == 1
        assert "missing.md" in report.broken_mkdocs_paths[0]["path"]

    def test_ignore_pulser_reexports(self, test_project: Path):
        # Create module with Pulser re-export
        module_dir = test_project / "test_pulser"
        module_dir.mkdir()
        init_file = module_dir / "__init__.py"
        init_file.write_text('__all__ = ["Results"]\nclass Results: pass')

        detector = DriftDetector(
            test_project, modules=["test_pulser"], ignore_pulser_reexports=True
        )
        report = detector.check_all()

        # Results should be ignored
        assert "test_pulser.Results" not in report.missing_in_docs

    def test_has_issues(self, test_project: Path):
        detector = DriftDetector(test_project, modules=["test_pkg"])
        report = detector.check_all()

        # Should have issues (missing APIs, undocumented params, broken links)
        assert report.has_issues() is True

    def test_no_issues(self, tmp_path: Path):
        # Create minimal project with everything documented
        module_dir = tmp_path / "perfect_pkg"
        module_dir.mkdir()
        init_file = module_dir / "__init__.py"
        init_file.write_text('__all__ = []\n"""Perfect package."""')

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "index.md").write_text("# Docs")

        mkdocs_yml = tmp_path / "mkdocs.yml"
        mkdocs_yml.write_text("nav:\n  - Home: index.md\n")

        sys.path.insert(0, str(tmp_path))

        detector = DriftDetector(tmp_path, modules=["perfect_pkg"])
        report = detector.check_all()

        assert report.has_issues() is False

    def test_check_api_coverage_submodule(self, test_project: Path):
        """Submodule APIs detected as missing from docs."""
        sub = test_project / "test_pkg" / "sub"
        sub.mkdir()
        (sub / "__init__.py").write_text(
            '__all__ = ["SubHelper"]\nclass SubHelper:\n    "sub helper"\n'
        )

        # Reimport so walk_packages finds the subpackage
        sys.modules.pop("test_pkg", None)
        sys.modules.pop("test_pkg.sub", None)

        detector = DriftDetector(test_project, modules=["test_pkg"])
        report = detector.check_all()

        assert "test_pkg.sub.SubHelper" in report.missing_in_docs

    def test_ignore_submodules(self, test_project: Path):
        """ignore_submodules excludes submodule APIs from coverage."""
        sub = test_project / "test_pkg" / "ignored"
        sub.mkdir()
        (sub / "__init__.py").write_text(
            '__all__ = ["Hidden"]\nclass Hidden:\n    "hidden"\n'
        )

        sys.modules.pop("test_pkg", None)
        sys.modules.pop("test_pkg.ignored", None)

        detector = DriftDetector(
            test_project,
            modules=["test_pkg"],
            ignore_submodules=["test_pkg.ignored"],
        )
        report = detector.check_all()

        assert not any("Hidden" in m for m in report.missing_in_docs)

    def test_skip_basic_checks(self, test_project: Path):
        """Test skip_basic_checks=True skips API coverage, refs, params, local links."""
        detector = DriftDetector(test_project, modules=["test_pkg"])

        # Without skip: should have issues (missing API, broken local link, etc.)
        report_full = detector.check_all()
        assert len(report_full.missing_in_docs) > 0
        assert len(report_full.broken_local_links) > 0

        # With skip: basic checks should be empty
        report_skip = detector.check_all(skip_basic_checks=True)
        assert len(report_skip.missing_in_docs) == 0
        assert len(report_skip.broken_references) == 0
        assert len(report_skip.undocumented_params) == 0
        assert len(report_skip.broken_local_links) == 0
        assert len(report_skip.broken_mkdocs_paths) == 0


class TestDocstringLocalLinks:
    """Tests for broken local links in Python docstrings."""

    def test_docstring_broken_local_link(self, tmp_path: Path):
        """Broken link in docstring detected."""
        mod = tmp_path / "link_pkg"
        mod.mkdir()
        (mod / "__init__.py").write_text(
            '__all__ = ["Foo"]\n'
            "class Foo:\n"
            '    """See [guide](../docs/missing.md) for details."""\n'
        )
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "index.md").write_text("# Docs\n::: link_pkg.Foo\n")
        (tmp_path / "mkdocs.yml").write_text("nav:\n  - Home: index.md\n")
        sys.path.insert(0, str(tmp_path))
        try:
            detector = DriftDetector(tmp_path, modules=["link_pkg"])
            report = detector.check_all()
            broken = [
                b for b in report.broken_local_links if "docstring" in b["location"]
            ]
            assert len(broken) == 1
            assert "missing.md" in broken[0]["path"]
            assert "link_pkg.Foo" in broken[0]["location"]
        finally:
            sys.modules.pop("link_pkg", None)

    def test_docstring_valid_local_link(self, tmp_path: Path):
        """Valid link in docstring not flagged."""
        mod = tmp_path / "ok_pkg"
        mod.mkdir()
        (mod / "__init__.py").write_text(
            '__all__ = ["Bar"]\n'
            "class Bar:\n"
            '    """See [guide](guide.md) for info."""\n'
        )
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "index.md").write_text("# Docs\n::: ok_pkg.Bar\n")
        (docs / "guide.md").write_text("# Guide\n")
        (tmp_path / "mkdocs.yml").write_text("nav:\n  - Home: index.md\n")
        sys.path.insert(0, str(tmp_path))
        try:
            detector = DriftDetector(tmp_path, modules=["ok_pkg"])
            report = detector.check_all()
            broken = [
                b for b in report.broken_local_links if "docstring" in b["location"]
            ]
            assert len(broken) == 0
        finally:
            sys.modules.pop("ok_pkg", None)

    def test_docstring_link_with_anchor_valid(self, tmp_path: Path):
        """Link with #fragment resolves when file exists."""
        mod = tmp_path / "anchor_pkg"
        mod.mkdir()
        (mod / "__init__.py").write_text(
            '__all__ = ["Cfg"]\n'
            "class Cfg:\n"
            '    """Check [precision](advanced/config.md#precision)."""\n'
        )
        docs = tmp_path / "docs"
        docs.mkdir()
        adv = docs / "advanced"
        adv.mkdir()
        (adv / "config.md").write_text("# Config\n## precision\n")
        (docs / "index.md").write_text("# Docs\n::: anchor_pkg.Cfg\n")
        (tmp_path / "mkdocs.yml").write_text("nav:\n  - Home: index.md\n")
        sys.path.insert(0, str(tmp_path))
        try:
            detector = DriftDetector(tmp_path, modules=["anchor_pkg"])
            report = detector.check_all()
            broken = [
                b for b in report.broken_local_links if "docstring" in b["location"]
            ]
            assert len(broken) == 0
        finally:
            sys.modules.pop("anchor_pkg", None)

    def test_docstring_link_with_anchor_broken(self, tmp_path: Path):
        """Link with #fragment flagged when file missing."""
        mod = tmp_path / "brk_pkg"
        mod.mkdir()
        (mod / "__init__.py").write_text(
            '__all__ = ["X"]\n' "class X:\n" '    """See [section](missing.md#foo)."""\n'
        )
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "index.md").write_text("# Docs\n::: brk_pkg.X\n")
        (tmp_path / "mkdocs.yml").write_text("nav:\n  - Home: index.md\n")
        sys.path.insert(0, str(tmp_path))
        try:
            detector = DriftDetector(tmp_path, modules=["brk_pkg"])
            report = detector.check_all()
            broken = [
                b for b in report.broken_local_links if "docstring" in b["location"]
            ]
            assert len(broken) == 1
            assert "missing.md#foo" in broken[0]["path"]
        finally:
            sys.modules.pop("brk_pkg", None)

    def test_docstring_link_resolves_relative_to_mkdocstrings_page(self, tmp_path: Path):
        """Link resolves relative to the ::: page, not docs root."""
        mod = tmp_path / "rel_pkg"
        mod.mkdir()
        # Docstring has relative link "advanced/config.md"
        (mod / "__init__.py").write_text(
            '__all__ = ["Cls"]\n'
            "class Cls:\n"
            '    """See [cfg](advanced/config.md)."""\n'
        )
        docs = tmp_path / "docs"
        sub = docs / "rel_pkg"
        sub.mkdir(parents=True)
        # ::: ref lives in docs/rel_pkg/api.md
        (sub / "api.md").write_text("::: rel_pkg.Cls\n")
        # Target file at docs/rel_pkg/advanced/config.md
        adv = sub / "advanced"
        adv.mkdir()
        (adv / "config.md").write_text("# Config\n")
        (docs / "index.md").write_text("# Docs\n")
        (tmp_path / "mkdocs.yml").write_text("nav:\n  - Home: index.md\n")
        sys.path.insert(0, str(tmp_path))
        try:
            detector = DriftDetector(tmp_path, modules=["rel_pkg"])
            report = detector.check_all()
            broken = [
                b for b in report.broken_local_links if "docstring" in b["location"]
            ]
            # Should NOT be flagged — resolves from api.md's dir
            assert len(broken) == 0
        finally:
            sys.modules.pop("rel_pkg", None)

    def test_docstring_link_resolves_with_reexported_api(self, tmp_path: Path):
        """Link resolves when ::: uses full path but API is re-exported.

        Simulates: ::: pkg.sub.Cls in docs/pkg/api.md, but API discovered
        as pkg.Cls via __init__.py re-export.
        """
        pkg = tmp_path / "reexp_pkg"
        pkg.mkdir()
        sub = pkg / "sub"
        sub.mkdir()
        (sub / "__init__.py").write_text(
            "class Cls:\n" '    """See [cfg](advanced/config.md)."""\n'
        )
        (pkg / "__init__.py").write_text('from .sub import Cls\n__all__ = ["Cls"]\n')
        docs = tmp_path / "docs"
        pkg_docs = docs / "reexp_pkg"
        pkg_docs.mkdir(parents=True)
        # ::: uses full submodule path
        (pkg_docs / "api.md").write_text("::: reexp_pkg.sub.Cls\n")
        adv = pkg_docs / "advanced"
        adv.mkdir()
        (adv / "config.md").write_text("# Config\n")
        (docs / "index.md").write_text("# Docs\n")
        (tmp_path / "mkdocs.yml").write_text("nav:\n  - Home: index.md\n")
        sys.path.insert(0, str(tmp_path))
        try:
            detector = DriftDetector(tmp_path, modules=["reexp_pkg"])
            report = detector.check_all()
            broken = [
                b for b in report.broken_local_links if "docstring" in b["location"]
            ]
            assert len(broken) == 0
        finally:
            sys.modules.pop("reexp_pkg", None)
            sys.modules.pop("reexp_pkg.sub", None)


class TestQualityChecks:
    """Tests for LLM quality checks integration."""

    def test_check_quality_disabled_by_default(self, test_project: Path):
        """Test quality checks not run by default."""
        detector = DriftDetector(test_project, modules=["test_pkg"])
        report = detector.check_all()

        assert len(report.quality_issues) == 0

    def test_check_quality_missing_dependency(self, test_project: Path):
        """Test quality checks gracefully handle missing dependencies."""
        from unittest.mock import patch

        detector = DriftDetector(test_project, modules=["test_pkg"])

        with patch("doc_checker.checkers.importlib.import_module") as mock_import:
            mock_import.side_effect = ImportError("No module named 'ollama'")
            report = detector.check_all(check_quality=True)

        # Should add warning, not crash
        assert len(report.warnings) > 0
        assert any("Quality checks skipped" in w for w in report.warnings)

    def test_check_quality_enabled(self, test_project: Path):
        """Test quality checks run when enabled."""
        from unittest.mock import MagicMock, patch

        detector = DriftDetector(test_project, modules=["test_pkg"])

        # Mock the quality checker
        mock_checker = MagicMock()
        mock_checker.check_module_quality.return_value = [
            MagicMock(
                api_name="test_pkg.test_function",
                severity="warning",
                category="grammar",
                message="Test issue",
                suggestion="Fix it",
                line_reference="test",
            )
        ]

        with patch("doc_checker.llm_checker.QualityChecker") as mock_checker_class:
            mock_checker_class.return_value = mock_checker
            report = detector.check_all(
                check_quality=True,
                quality_backend="ollama",
                quality_model="qwen2.5:3b",
            )

        assert len(report.quality_issues) == 1
        assert report.quality_issues[0].api_name == "test_pkg.test_function"

    def test_check_quality_with_sample_rate(self, test_project: Path):
        """Test quality checks with sampling."""
        from unittest.mock import MagicMock, patch

        detector = DriftDetector(test_project, modules=["test_pkg"])

        mock_checker = MagicMock()
        mock_checker.check_module_quality.return_value = []

        with patch("doc_checker.llm_checker.QualityChecker") as mock_checker_class:
            mock_checker_class.return_value = mock_checker
            detector.check_all(check_quality=True, quality_sample_rate=0.5, verbose=True)

        # Verify sample_rate was passed
        mock_checker.check_module_quality.assert_called_with("test_pkg", True, 0.5)

    def test_check_quality_backend_error(self, test_project: Path):
        """Test quality checks handle backend initialization errors."""
        from unittest.mock import patch

        detector = DriftDetector(test_project, modules=["test_pkg"])

        with patch("doc_checker.llm_checker.QualityChecker") as mock_checker_class:
            mock_checker_class.side_effect = RuntimeError("Ollama not running")
            report = detector.check_all(check_quality=True)

        # Should add warning, not crash
        assert len(report.warnings) > 0
        assert any("Ollama not running" in w for w in report.warnings)

    def test_quality_issues_in_has_issues(self, test_project: Path):
        """Test quality issues contribute to has_issues()."""
        from unittest.mock import MagicMock, patch

        detector = DriftDetector(test_project, modules=["test_pkg"])

        mock_checker = MagicMock()
        mock_checker.check_module_quality.return_value = [
            MagicMock(
                api_name="test",
                severity="critical",
                category="params",
                message="Missing param",
                suggestion="Add it",
                line_reference=None,
            )
        ]

        with patch("doc_checker.llm_checker.QualityChecker") as mock_checker_class:
            mock_checker_class.return_value = mock_checker
            report = detector.check_all(check_quality=True)

        assert report.has_issues() is True
        assert len(report.quality_issues) > 0
