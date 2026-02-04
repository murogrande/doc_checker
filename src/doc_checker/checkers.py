"""Drift detection orchestrator.

Coordinates all documentation checks: API coverage, reference
validation, parameter docs, local/external links, mkdocs nav,
and LLM-based quality analysis. Entry point is
``DriftDetector.check_all()``.
"""

from __future__ import annotations

import importlib
from pathlib import Path

from .code_analyzer import CodeAnalyzer
from .link_checker import LinkChecker
from .models import DriftReport
from .parsers import MarkdownParser, YamlParser


class DriftDetector:
    """Detect documentation drift in a Python project.

    Compares a project's public API (via importlib/inspect) against
    its mkdocs-based documentation to find gaps, broken references,
    missing parameter docs, dead links, and quality issues.

    Attributes:
        root_path: Project root directory.
        modules: Python module names to check.
        ignore_pulser_reexports: Skip known Pulser re-exported symbols.
        PULSER_REEXPORTS: Symbol names re-exported from Pulser that
            don't need local documentation.
    """

    # APIs re-exported from Pulser - don't need local docs
    PULSER_REEXPORTS = {  # TODO: delete this and make it configurable using the CLI
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
        self,
        root_path: Path,
        modules: list[str],
        ignore_pulser_reexports: bool = True,
        ignore_submodules: list[str] | None = None,
    ):
        """Initialize detector with project root and target modules.

        Args:
            root_path: Path to the project root (must contain ``docs/``
                and ``mkdocs.yml``).
            modules: Python module names to inspect (e.g. ``["emu_mps"]``).
            ignore_pulser_reexports: If True, symbols listed in
                ``PULSER_REEXPORTS`` are excluded from coverage checks.
            ignore_submodules: Submodule names to skip during
                recursive discovery (e.g. ``["optimatrix"]``).
        """
        self.root_path = root_path
        self.modules = modules
        self.ignore_pulser_reexports = ignore_pulser_reexports
        self.ignore_submodules: set[str] = set(ignore_submodules or [])

        # 4 collaborators
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
        """Run selected checks and return a report.

        By default runs basic checks only. External link and LLM quality
        checks are opt-in. When ``skip_basic_checks`` is True, only the
        explicitly enabled optional checks run.

        Args:
            check_external_links: Validate external HTTP/HTTPS URLs
                found in markdown and notebooks.
            check_quality: Evaluate docstring quality via an LLM.
            quality_backend: LLM backend — ``"ollama"`` or ``"openai"``.
            quality_model: Model name override (backend defaults used
                when None).
            quality_api_key: API key for cloud backends (OpenAI).
            quality_sample_rate: Fraction of APIs to check (0.0–1.0).
                Useful for large codebases.
            verbose: Print progress to stdout.
            skip_basic_checks: Skip API coverage, reference validation,
                parameter docs, local links, and mkdocs nav checks.

        Returns:
            A ``DriftReport`` with all detected issues.
        """
        report = DriftReport()
        if check_quality:
            report.llm_backend = quality_backend
            defaults = {"ollama": "qwen2.5:3b", "openai": "gpt-4o-mini"}
            report.llm_model = quality_model or defaults.get(quality_backend)
        self._warn_unmatched_ignores(report)

        if not skip_basic_checks:
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

    def _warn_unmatched_ignores(self, report: DriftReport) -> None:
        """Warn once per unmatched --ignore-submodules entry."""
        if not self.ignore_submodules:
            return
        all_unmatched: set[str] = set()
        for module_name in self.modules:
            _, unmatched = self.code_analyzer.get_all_public_apis(
                module_name, self.ignore_submodules
            )
            all_unmatched |= unmatched
        for name in sorted(all_unmatched):
            report.warnings.append(
                f"--ignore-submodules '{name}' " f"did not match any subpackage"
            )

    def _check_api_coverage(self, report: DriftReport) -> None:
        """Compare public APIs against mkdocstrings references.

        Collects all ``:::`` references from markdown files, then
        iterates over each module's public API. Any API not found
        in the documented references is added to
        ``report.missing_in_docs``.
        """
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
            apis, _ = self.code_analyzer.get_all_public_apis(
                module_name, self.ignore_submodules
            )
            for api in apis:
                # Skip Pulser re-exports
                if self.ignore_pulser_reexports and api.name in self.PULSER_REEXPORTS:
                    continue

                is_documented = (
                    api.name in documented_names.get(module_name, set())
                    or f"{api.module}.{api.name}" in documented
                    or any(ref.endswith(f".{api.name}") for ref in documented)
                )

                if not is_documented:
                    report.missing_in_docs.append(f"{api.module}.{api.name}")

    def _check_references(self, report: DriftReport) -> None:
        """Validate mkdocstrings references resolve to real code.

        Each ``:::`` reference is checked via importlib. Broken ones
        are added to ``report.broken_references``.
        """
        refs = self.md_parser.find_mkdocstrings_refs()
        for ref in refs:
            if not self._is_valid_reference(ref.reference):
                report.broken_references.append(
                    f"{ref.reference} in {ref.file_path}:{ref.line_number}"
                )

    def _is_valid_reference(self, reference: str) -> bool:
        """Check if a dotted reference resolves to a Python object.

        Tries progressively shorter module paths (longest first),
        then resolves remaining parts as attributes.

        Returns:
            True if the reference resolves, False otherwise.
        """
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
        """Check that function/method parameters appear in docstrings.

        For each public API with both a docstring and parameters,
        verifies each parameter name is mentioned in the docstring.
        Skips internal params (``cls``, enum internals, etc.).
        Undocumented params are added to ``report.undocumented_params``.
        """
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
            apis, _ = self.code_analyzer.get_all_public_apis(
                module_name, self.ignore_submodules
            )
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
                            "name": f"{api.module}.{api.name}",
                            "params": ", ".join(undocumented),
                        }
                    )

    def _check_local_links(self, report: DriftReport) -> None:
        """Verify local file links in markdown/notebooks resolve.

        Resolves relative, ``..``-prefixed, and absolute paths.
        Also checks that linked ``.py`` files appear in mkdocs nav.
        Broken links are added to ``report.broken_local_links``.
        """
        links = self.md_parser.find_local_links()
        nav_files = self.yaml_parser.get_nav_files()

        for link in links:
            link_dir = link.file_path.parent
            file_path = link.path.split("#")[0].rstrip("/")
            resolved = (link_dir / file_path).resolve()

            # Try other resolution strategies
            if not resolved.exists() and file_path.startswith(".."):
                resolved = (self.root_path / "docs" / file_path).resolve()
            if not resolved.exists() and file_path.startswith("/"):
                resolved = (self.root_path / file_path.lstrip("/")).resolve()

            # mkdocs URL-style resolution: treat source file as directory
            # e.g. notebooks/file.ipynb -> notebooks/file/ in URL space
            # so ../../path resolves relative to that virtual directory
            if not resolved.exists() and file_path.startswith(".."):
                virtual_dir = link_dir / link.file_path.stem
                resolved = (virtual_dir / file_path).resolve()
                # mkdocs links without extension: .md files only resolve to .md,
                # but notebooks (via mkdocs-jupyter) can resolve to .md or .ipynb
                if not resolved.exists() and not resolved.suffix:
                    is_notebook_source = link.file_path.suffix == ".ipynb"
                    extensions = (".md", ".ipynb") if is_notebook_source else (".md",)
                    for ext in extensions:
                        resolved_with_ext = resolved.with_suffix(ext)
                        if resolved_with_ext.exists():
                            resolved = resolved_with_ext
                            break

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
                if file_path.endswith(".py") and nav_files is not None:
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

        # Check local links in Python docstrings
        # Build map: API fqn → md file dir (mkdocstrings renders
        # docstrings into the page that has the ::: directive, so
        # relative links resolve from that page's directory).
        docs_path = self.root_path / "docs"
        refs = self.md_parser.find_mkdocstrings_refs()
        ref_dirs: dict[str, Path] = {}
        for ref in refs:
            # Index by full ref and by short name so both
            # "emu_mps.mps.MPS" and "emu_mps.MPS" resolve
            ref_dirs[ref.reference] = ref.file_path.parent
            short = ref.reference.split(".")[0] + "." + ref.reference.rsplit(".", 1)[-1]
            if short != ref.reference:
                ref_dirs.setdefault(short, ref.file_path.parent)

        for module_name in self.modules:
            apis, _ = self.code_analyzer.get_all_public_apis(
                module_name, self.ignore_submodules
            )
            for api in apis:
                if not api.docstring:
                    continue
                fqn = f"{api.module}.{api.name}"
                # Find the md page directory where this API's
                # docstring will be rendered by mkdocstrings
                base_dir = ref_dirs.get(fqn, docs_path)
                ds_links = self.md_parser.parse_local_links_in_text(
                    api.docstring, base_dir
                )
                for link in ds_links:
                    file_path = link.path.split("#")[0]
                    resolved = (base_dir / file_path).resolve()
                    if not resolved.exists() and file_path.startswith(".."):
                        resolved = (docs_path / file_path).resolve()
                    if not resolved.exists() and file_path.startswith("/"):
                        resolved = (self.root_path / file_path.lstrip("/")).resolve()
                    if not resolved.exists():
                        report.broken_local_links.append(
                            {
                                "path": link.path,
                                "location": (f"{fqn} (docstring):{link.line_number}"),
                                "text": link.text,
                            }
                        )

    def _check_mkdocs_paths(self, report: DriftReport) -> None:
        """Verify all file paths in mkdocs.yml nav exist on disk."""
        broken = self.yaml_parser.check_nav_paths()
        report.broken_mkdocs_paths.extend(broken)

    def _check_external_links(self, report: DriftReport, verbose: bool) -> None:
        """Validate external HTTP/HTTPS links from docs.

        Collects URLs from markdown/notebooks and checks each via
        async HTTP requests (aiohttp) or urllib fallback. Broken
        links are added to ``report.broken_external_links``.
        """
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
        """Evaluate docstring quality using an LLM backend.

        Lazily imports ``QualityChecker`` to avoid hard dependency on
        ollama/openai. Gracefully skips with a warning if deps are
        missing or the backend fails to initialize. Issues are added
        to ``report.quality_issues``.
        """
        try:
            from .llm_checker import QualityChecker
        except ImportError as e:
            report.warnings.append(
                f"Quality checks skipped: {e}. "
                "Install with: pip install doc-checker[llm]"
            )
            return

        try:
            checker = QualityChecker(
                self.root_path,
                backend,
                model,
                api_key,
                ignore_submodules=self.ignore_submodules,
            )
        except (ImportError, RuntimeError, ValueError) as e:
            report.warnings.append(f"Quality checks skipped: {e}")
            return

        if verbose:
            print(
                f"Running LLM quality checks "
                f"(backend: {backend}, model: {checker.backend.model})..."
            )

        for module_name in self.modules:
            issues = checker.check_module_quality(module_name, verbose, sample_rate)
            report.quality_issues.extend(issues)
