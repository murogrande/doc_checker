"""Drift detection checks."""

from __future__ import annotations

import importlib
from pathlib import Path

from doc_checker.code_analyzer import CodeAnalyzer
from doc_checker.link_checker import LinkChecker
from doc_checker.models import DriftReport
from doc_checker.parsers import MarkdownParser, YamlParser


class DriftDetector:
    """Detect documentation drift."""

    # APIs re-exported from Pulser - don't need local docs
    PULSER_REEXPORTS = {
        "BitStrings",
        "CorrelationMatrix",
        "Energy",
        "EnergyVariance",
        "EnergySecondMoment",
        "Expectation",
        "Fidelity",
        "Occupation",
        "StateResult",
        "Results",
    }

    def __init__(
        self, root_path: Path, modules: list[str], ignore_pulser_reexports: bool = True
    ):
        self.root_path = root_path
        self.modules = modules
        self.ignore_pulser_reexports = ignore_pulser_reexports

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
    ) -> DriftReport:
        """Run all checks.

        Args:
            check_external_links: Check external HTTP links (slow)
            check_quality: Run LLM quality checks
            quality_backend: "ollama" or "openai"
            quality_model: Model name (uses defaults if None)
            quality_api_key: API key for cloud backends
            quality_sample_rate: Check only this fraction of APIs (0.0-1.0)
            verbose: Print progress
        """
        report = DriftReport()

        self._check_api_coverage(report)
        self._check_references(report)
        self._check_param_docs(report)
        self._check_local_links(report)
        self._check_mkdocs_paths(report)

        if check_external_links:
            self._check_external_links(report, verbose)

        if check_quality:
            self._check_quality(
                report,
                quality_backend,
                quality_model,
                quality_api_key,
                quality_sample_rate,
                verbose,
            )

        return report

    def _check_api_coverage(self, report: DriftReport) -> None:
        """Check all public APIs are documented."""
        refs = self.md_parser.find_mkdocstrings_refs()
        documented = {ref.reference for ref in refs}

        # Build documented names per module
        documented_names: dict[str, set[str]] = {m: set() for m in self.modules}
        for ref in documented:
            parts = ref.split(".")
            if len(parts) >= 2:
                base_module = parts[0]
                if base_module in documented_names:
                    documented_names[base_module].add(parts[-1])
                    documented_names[base_module].add(ref)

        for module_name in self.modules:
            apis = self.code_analyzer.get_public_apis(module_name)
            for api in apis:
                # Skip Pulser re-exports
                if self.ignore_pulser_reexports and api.name in self.PULSER_REEXPORTS:
                    continue

                is_documented = (
                    api.name in documented_names.get(module_name, set())
                    or f"{module_name}.{api.name}" in documented
                    or any(ref.endswith(f".{api.name}") for ref in documented)
                )

                if not is_documented:
                    report.missing_in_docs.append(f"{module_name}.{api.name}")

    def _check_references(self, report: DriftReport) -> None:
        """Check all doc references are valid."""
        refs = self.md_parser.find_mkdocstrings_refs()
        for ref in refs:
            if not self._is_valid_reference(ref.reference):
                report.broken_references.append(
                    f"{ref.reference} in {ref.file_path}:{ref.line_number}"
                )

    def _is_valid_reference(self, reference: str) -> bool:
        """Check if reference points to valid code."""
        parts = reference.split(".")
        for i in range(len(parts), 0, -1):
            module_path = ".".join(parts[:i])
            try:
                module = importlib.import_module(module_path)
                obj = module
                for attr in parts[i:]:
                    obj = getattr(obj, attr)
                return True
            except (ImportError, AttributeError):
                continue
        return False

    def _check_param_docs(self, report: DriftReport) -> None:
        """Check function parameters are documented."""
        ignore_params = {
            "value",
            "names",
            "module",
            "qualname",
            "type",
            "start",
            "boundary",
            "cls",
        }

        for module_name in self.modules:
            apis = self.code_analyzer.get_public_apis(module_name)
            for api in apis:
                if not api.docstring or not api.parameters:
                    continue

                undocumented = []
                for param in api.parameters:
                    param_name = param.split(":")[0].split("=")[0].strip()
                    if param_name in ignore_params:
                        continue
                    if param_name not in api.docstring:
                        undocumented.append(param_name)

                if undocumented:
                    report.undocumented_params.append(
                        {
                            "name": f"{module_name}.{api.name}",
                            "params": ", ".join(undocumented),
                        }
                    )

    def _check_local_links(self, report: DriftReport) -> None:
        """Check local file links exist."""
        links = self.md_parser.find_local_links()
        nav_files = self.yaml_parser.get_nav_files()

        for link in links:
            link_dir = link.file_path.parent
            resolved = (link_dir / link.path).resolve()

            # Try other resolution strategies
            if not resolved.exists() and link.path.startswith(".."):
                resolved = (self.root_path / "docs" / link.path).resolve()
            if not resolved.exists() and link.path.startswith("/"):
                resolved = (self.root_path / link.path.lstrip("/")).resolve()

            if not resolved.exists():
                report.broken_local_links.append(
                    {
                        "path": link.path,
                        "location": f"{link.file_path}:{link.line_number}",
                        "text": link.text,
                    }
                )
            else:
                # Check .py files are in nav
                if link.path.endswith(".py") and nav_files is not None:
                    try:
                        rel_path = resolved.relative_to(self.root_path / "docs")
                        if str(rel_path) not in nav_files:
                            report.broken_local_links.append(
                                {
                                    "path": link.path,
                                    "location": f"{link.file_path}:{link.line_number}",
                                    "text": link.text,
                                    "reason": ".py file not in mkdocs nav",
                                }
                            )
                    except ValueError:
                        pass

    def _check_mkdocs_paths(self, report: DriftReport) -> None:
        """Check mkdocs.yml nav paths exist."""
        broken = self.yaml_parser.check_nav_paths()
        report.broken_mkdocs_paths.extend(broken)

    def _check_external_links(self, report: DriftReport, verbose: bool) -> None:
        """Check external HTTP links."""
        if verbose:
            print("Finding external links...")
        links = self.md_parser.find_external_links()
        if verbose:
            print(f"Found {len(links)} links, checking...")

        results = self.link_checker.check_links(links, verbose)
        for result in results:
            if result.is_broken:
                status = result.status_code if result.status_code else result.error
                report.broken_external_links.append(
                    {
                        "url": result.link.url,
                        "status": status,
                        "location": f"{result.link.file_path}:{result.link.line_number}",
                        "text": result.link.text,
                    }
                )

    def _check_quality(
        self,
        report: DriftReport,
        backend: str,
        model: str | None,
        api_key: str | None,
        sample_rate: float,
        verbose: bool,
    ) -> None:
        """Check documentation quality using LLM."""
        try:
            from doc_checker.llm_checker import QualityChecker
        except ImportError as e:
            report.warnings.append(
                f"Quality checks skipped: {e}. "
                "Install with: pip install doc-checker[llm]"
            )
            return

        try:
            checker = QualityChecker(self.root_path, backend, model, api_key)
        except (ImportError, RuntimeError, ValueError) as e:
            report.warnings.append(f"Quality checks skipped: {e}")
            return

        if verbose:
            print(f"Running LLM quality checks (backend: {backend})...")

        for module_name in self.modules:
            issues = checker.check_module_quality(module_name, verbose, sample_rate)
            report.quality_issues.extend(issues)
