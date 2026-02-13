from __future__ import annotations

from pathlib import Path

from doc_checker.models import DriftReport

from .base import Checker


class LLMQualityChecker(Checker):
    """LLM-based docstring quality analysis.

    Lazily imports QualityChecker from llm_checker in check() to avoid
    hard deps on ollama/openai. Supports ollama and openai backends.
    """

    def __init__(
        self,
        root_path: Path,
        modules: list[str],
        ignore_submodules: set[str],
        backend_type: str = "ollama",
        model: str | None = None,
        api_key: str | None = None,
        sample_rate: float = 1.0,
        verbose: bool = False,
    ):
        self.root_path = root_path
        self.modules = modules
        self.ignore_submodules = ignore_submodules
        self.backend_type = backend_type
        self.model = model
        self.api_key = api_key
        self.sample_rate = sample_rate
        self.verbose = verbose

    def check(self, report: DriftReport) -> None:
        """Run LLM quality checks; skip with warning if deps missing."""
        try:
            from doc_checker.llm_checker import QualityChecker
        except ImportError as e:
            report.warnings.append(
                f"Quality checks skipped: {e}. Install with: pip install doc-checker[llm]"
            )
            return
        try:
            checker = QualityChecker(
                self.root_path,
                self.backend_type,
                self.model,
                self.api_key,
                ignore_submodules=self.ignore_submodules,
            )
        except (ImportError, RuntimeError, ValueError) as e:
            report.warnings.append(f"Quality checks skipped: {e}")
            return
        if self.verbose:
            print(f"LLM quality checks ({self.backend_type}, {checker.backend.model})...")
        for module in self.modules:
            report.quality_issues.extend(
                checker.check_module_quality(module, self.verbose, self.sample_rate)
            )
