"""LLM-powered documentation quality checker."""

from __future__ import annotations

from pathlib import Path

from .code_analyzer import CodeAnalyzer
from .llm_backends import get_backend
from .models import QualityIssue
from .prompts import get_combined_quality_prompt


class QualityChecker:
    """Check documentation quality using LLMs."""

    def __init__(
        self,
        root_path: Path,
        backend_type: str = "ollama",
        model: str | None = None,
        api_key: str | None = None,
        ignore_submodules: set[str] | None = None,
    ):
        """Initialize quality checker.

        Args:
            root_path: Project root path
            backend_type: "ollama" (default) or "openai"
            model: Model name (uses defaults if None)
            api_key: API key for cloud backends
            ignore_submodules: Submodule names to skip.

        Raises:
            ImportError: If backend package not installed
            RuntimeError: If backend not available
        """
        self.root_path = root_path
        self.code_analyzer = CodeAnalyzer(root_path)
        self.backend = get_backend(backend_type, model, api_key)
        self.ignore_submodules = ignore_submodules

    def check_api_quality(
        self, api_name: str, module_name: str, verbose: bool = False
    ) -> list[QualityIssue]:
        """Check quality of single API documentation.

        Args:
            api_name: API name (e.g., "MPS.evolve")
            module_name: Module name (e.g., "emu_mps")
            verbose: Print progress

        Returns:
            List of quality issues found
        """
        # Get API info
        apis = self.code_analyzer.get_public_apis(module_name)
        api_info = next((api for api in apis if api.name == api_name), None)

        if not api_info:
            return [
                QualityIssue(
                    api_name=f"{module_name}.{api_name}",
                    severity="critical",
                    category="error",
                    message=f"API {api_name} not found in module {module_name}",
                    suggestion="Check API name spelling",
                    line_reference=None,
                )
            ]

        if not api_info.docstring:
            return [
                QualityIssue(
                    api_name=f"{module_name}.{api_name}",
                    severity="critical",
                    category="completeness",
                    message="No docstring found",
                    suggestion="Add docstring explaining what this API does",
                    line_reference=None,
                )
            ]

        # Build signature string
        params_str = ", ".join(api_info.parameters)
        return_str = (
            f" -> {api_info.return_annotation}" if api_info.return_annotation else ""
        )
        signature = f"def {api_name}({params_str}){return_str}"

        if verbose:
            print(f"  Checking {module_name}.{api_name}...")

        # Get LLM evaluation
        prompt = get_combined_quality_prompt(
            signature=signature,
            docstring=api_info.docstring,
            api_name=f"{module_name}.{api_name}",
        )

        try:
            response = self.backend.generate_json(prompt)
        except Exception as e:
            return [
                QualityIssue(
                    api_name=f"{module_name}.{api_name}",
                    severity="warning",
                    category="error",
                    message=f"LLM check failed: {e}",
                    suggestion="Check LLM backend connection",
                    line_reference=None,
                )
            ]

        # Parse response
        issues = []
        for issue_data in response.get("issues", []):
            issues.append(
                QualityIssue(
                    api_name=f"{module_name}.{api_name}",
                    severity=issue_data.get("severity", "warning"),
                    category=issue_data.get("category", "unknown"),
                    message=issue_data.get("message", "No message"),
                    suggestion=issue_data.get("suggestion", "No suggestion"),
                    line_reference=issue_data.get("line_reference"),
                )
            )

        if verbose and issues:
            print(f"    Found {len(issues)} issues (score: {response.get('score', 0)})")

        return issues

    def check_module_quality(
        self, module_name: str, verbose: bool = False, sample_rate: float = 1.0
    ) -> list[QualityIssue]:
        """Check quality of all APIs in a module.

        Args:
            module_name: Module to check (e.g., "emu_mps")
            verbose: Print progress
            sample_rate: Check only this fraction of APIs (0.0-1.0)

        Returns:
            List of all quality issues found
        """
        import random

        apis, _ = self.code_analyzer.get_all_public_apis(
            module_name, self.ignore_submodules
        )

        if not apis:
            if verbose:
                print(f"No public APIs found in {module_name}")
            return [
                QualityIssue(
                    api_name=module_name,
                    severity="warning",
                    category="error",
                    message=f"No public APIs found in module {module_name}",
                    suggestion="Check module name or ensure it is installed",
                    line_reference=None,
                )
            ]

        if sample_rate < 1.0:
            apis = random.sample(apis, int(len(apis) * sample_rate))

        if verbose:
            print(f"Checking {len(apis)} APIs in {module_name}...")

        all_issues = []
        for api in apis:
            issues = self.check_api_quality(api.name, module_name, verbose)
            all_issues.extend(issues)

        return all_issues
