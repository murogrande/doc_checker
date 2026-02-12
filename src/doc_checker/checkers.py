"""Drift detection orchestrator.

Provides DriftDetector class that coordinates all documentation checks:
API coverage, broken references, param docs, local/external links, and
optional LLM-based quality analysis.
"""

from __future__ import annotations

from pathlib import Path

from doc_checker.checkers_folder.api_coverage import ApiCoverageChecker
from doc_checker.checkers_folder.base import Checker
from doc_checker.checkers_folder.doc_params import ParamDocsChecker
from doc_checker.checkers_folder.docstrings_links import DocstringsLinksChecker
from doc_checker.checkers_folder.external_links import ExternalLinksChecker
from doc_checker.checkers_folder.local_links import LocalLinksChecker
from doc_checker.checkers_folder.nav_paths import NavPathsChecker
from doc_checker.checkers_folder.quality import LLMQualityChecker
from doc_checker.checkers_folder.references import ReferencesChecker
from doc_checker.code_analyzer import CodeAnalyzer

from .link_checker import LinkChecker
from .models import DriftReport
from .parsers import MarkdownParser, YamlParser


class DriftDetector:
    """Orchestrates all doc drift checkers against a project.

    Instantiates checkers from checkers_folder/ based on flags passed
    to check_all(), runs them sequentially, and returns a DriftReport.
    """

    def __init__(
        self,
        root_path: Path,
        modules: list[str],
        ignore_pulser_reexports: bool = True,
        ignore_submodules: list[str] | None = None,
    ):
        """Initialize detector with project root and target modules.

        Args:
            root_path: Project root containing docs/ and mkdocs.yml.
            modules: Python module names to scan for public APIs.
            ignore_pulser_reexports: Skip PULSER_REEXPORTS names in coverage check.
            ignore_submodules: Submodule prefixes to exclude from analysis.
        """
        self.root_path = root_path
        self.modules = modules
        self.ignore_pulser_reexports = ignore_pulser_reexports
        self.ignore_submodules: set[str] = set(ignore_submodules or [])
        self.code_analyzer = CodeAnalyzer(root_path)
        self.md_parser = MarkdownParser(root_path / "docs")
        self.yaml_parser = YamlParser(root_path / "mkdocs.yml", root_path / "docs")
        self.link_checker = LinkChecker()

    def check_all(
        self,
        check_external_links: bool = False,
        check_quality: bool = False,
        quality_backend: str = "ollama",
        quality_model: str | None = None,
        quality_api_key: str | None = None,
        quality_sample_rate: float = 1.0,
        verbose: bool = False,
        skip_basic_checks: bool = False,
    ) -> DriftReport:
        """Run all enabled checks and return a DriftReport.

        Basic checks (unless skip_basic_checks): API coverage, broken refs,
        param docs, local links, mkdocs nav paths. Optional: external link
        validation, LLM-based docstring quality.

        Args:
            check_external_links: Validate HTTP/HTTPS links via async requests.
            check_quality: Run LLM quality analysis on docstrings.
            quality_backend: LLM backend ("ollama" or "openai").
            quality_model: Model name override (defaults per backend).
            quality_api_key: API key for openai backend.
            quality_sample_rate: Fraction of APIs to check (0.0-1.0).
            verbose: Print progress info.
            skip_basic_checks: Skip basic checks (for standalone link/quality runs).

        Returns:
            DriftReport with all detected issues.
        """
        report = DriftReport()
        if check_quality:
            report.llm_backend = quality_backend
            report.llm_model = quality_model or {
                "ollama": "qwen3:1.7b",
                "openai": "gpt-5.2",
            }.get(quality_backend)
        self._warn_unmatched_ignores(report)
        checkers: list[Checker] = []
        if not skip_basic_checks:
            checkers += [
                ApiCoverageChecker(
                    self.code_analyzer,
                    self.modules,
                    self.ignore_submodules,
                    self.md_parser,
                    self.ignore_pulser_reexports,
                ),
                ReferencesChecker(md_parser=self.md_parser),
                ParamDocsChecker(
                    self.code_analyzer,
                    self.modules,
                    self.ignore_submodules,
                ),
                LocalLinksChecker(
                    self.root_path,
                    self.md_parser,
                    self.yaml_parser,
                ),
                DocstringsLinksChecker(
                    self.code_analyzer,
                    self.modules,
                    self.ignore_submodules,
                    self.root_path,
                    self.md_parser,
                ),
                NavPathsChecker(self.yaml_parser),
            ]
        if check_external_links:
            checkers.append(
                ExternalLinksChecker(self.md_parser, self.link_checker, verbose)
            )
        if check_quality:
            checkers.append(
                LLMQualityChecker(
                    self.root_path,
                    self.modules,
                    self.ignore_submodules,
                    quality_backend,
                    quality_model,
                    quality_api_key,
                    quality_sample_rate,
                    verbose,
                )
            )
        for checker in checkers:
            checker.check(report)

        return report

    def _warn_unmatched_ignores(self, report: DriftReport) -> None:
        """Add warnings for --ignore-submodules entries that matched nothing."""
        if not self.ignore_submodules:
            return
        unmatched: set[str] = set()
        for module in self.modules:
            _, unmatched_in_module = self.code_analyzer.get_all_public_apis(
                module, self.ignore_submodules
            )
            unmatched |= unmatched_in_module
        for name in sorted(unmatched):
            report.warnings.append(
                f"--ignore-submodules '{name}' did not match any subpackage"
            )
