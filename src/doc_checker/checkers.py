"""Drift detection orchestrator."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import TYPE_CHECKING

from .code_analyzer import CodeAnalyzer
from .link_checker import LinkChecker
from .models import BrokenLinkInfo, DriftReport, LocalLink
from .parsers import MarkdownParser, YamlParser

if TYPE_CHECKING:
    from .models import SignatureInfo


class DriftDetector:
    """Detect documentation drift in a Python project."""

    PULSER_REEXPORTS = {  # TODO: make configurable via CLI
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
    IGNORE_PARAMS = {
        "value",
        "names",
        "module",
        "qualname",
        "type",
        "start",
        "boundary",
        "cls",
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
                "ollama": "qwen2.5:3b",
                "openai": "gpt-4o-mini",
            }.get(quality_backend)
        self._warn_unmatched_ignores(report)
        if not skip_basic_checks:
            self._check_api_coverage(report)
            self._check_references(report)
            self._check_param_docs(report)
            self._check_local_links(report)
            report.broken_mkdocs_paths.extend(self.yaml_parser.check_nav_paths())
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
        """Add warnings for --ignore-submodules entries that matched nothing."""
        if not self.ignore_submodules:
            return
        unmatched: set[str] = set()
        for m in self.modules:
            _, u = self.code_analyzer.get_all_public_apis(m, self.ignore_submodules)
            unmatched |= u
        for name in sorted(unmatched):
            report.warnings.append(
                f"--ignore-submodules '{name}' did not match any subpackage"
            )

    def _check_api_coverage(self, report: DriftReport) -> None:
        """Find public APIs missing from mkdocstrings ::: references.

        Scans all modules for public APIs, then checks each against documented
        refs. Matches by short name, full path, or suffix. Appends missing
        APIs to report.missing_in_docs.
        """
        refs = self.md_parser.find_mkdocstrings_refs()
        documented = {r.reference for r in refs}
        doc_names: dict[str, set[str]] = {m: set() for m in self.modules}
        for ref in documented:
            parts = ref.split(".")
            if len(parts) >= 2 and parts[0] in doc_names:
                doc_names[parts[0]].update([parts[-1], ref])
        for m in self.modules:
            apis, _ = self.code_analyzer.get_all_public_apis(m, self.ignore_submodules)
            for api in apis:
                if self.ignore_pulser_reexports and api.name in self.PULSER_REEXPORTS:
                    continue
                if not self._is_api_documented(api, documented, doc_names):
                    report.missing_in_docs.append(f"{api.module}.{api.name}")

    def _is_api_documented(
        self, api: "SignatureInfo", documented: set[str], doc_names: dict[str, set[str]]
    ) -> bool:
        """Check if API is documented via any naming convention.

        Checks three patterns: (1) short name in module's doc_names set,
        (2) exact fqn match in documented, (3) suffix match for re-exports.
        """
        base = api.module.split(".")[0]
        return (
            api.name in doc_names.get(base, set())
            or f"{api.module}.{api.name}" in documented
            or any(r.endswith(f".{api.name}") for r in documented)
        )

    def _check_references(self, report: DriftReport) -> None:
        """Find mkdocstrings ::: refs that don't resolve to Python objects.

        Each ::: reference is validated via importlib to ensure the dotted
        path actually exists. Broken refs appended to report.broken_references.
        """
        for ref in self.md_parser.find_mkdocstrings_refs():
            if not self._is_valid_reference(ref.reference):
                report.broken_references.append(
                    f"{ref.reference} in {ref.file_path}:{ref.line_number}"
                )

    def _is_valid_reference(self, reference: str) -> bool:
        """Check if dotted reference resolves to a Python object.

        Tries progressively shorter module prefixes (a.b.c → a.b → a) then
        getattr for remaining parts. Returns True if any combo succeeds.
        """
        parts = reference.split(".")
        for i in range(len(parts), 0, -1):
            try:
                mod = importlib.import_module(".".join(parts[:i]))
                for attr in parts[i:]:
                    mod = getattr(mod, attr)
                return True
            except (ImportError, AttributeError):
                continue
        return False

    def _check_param_docs(self, report: DriftReport) -> None:
        """Find function parameters not mentioned in docstrings.

        For each API with params and docstring, checks if param names appear
        in the docstring text. Skips IGNORE_PARAMS (self, cls, etc). Missing
        params appended to report.undocumented_params.
        """
        for m in self.modules:
            apis, _ = self.code_analyzer.get_all_public_apis(m, self.ignore_submodules)
            for api in apis:
                if not api.docstring or not api.parameters:
                    continue
                undoc = [
                    p.split(":")[0].split("=")[0].strip()
                    for p in api.parameters
                    if p.split(":")[0].split("=")[0].strip() not in self.IGNORE_PARAMS
                    and p.split(":")[0].split("=")[0].strip() not in (api.docstring or "")
                ]
                if undoc:
                    report.undocumented_params.append(
                        {"name": f"{api.module}.{api.name}", "params": ", ".join(undoc)}
                    )

    def _check_local_links(self, report: DriftReport) -> None:
        """Verify local file links in markdown, notebooks, and docstrings.

        Validates relative/absolute paths resolve to existing files. Applies
        mkdocs-specific rules: notebooks must omit .ipynb extension, .py files
        must be in mkdocs nav. Also checks links in Python docstrings.
        """
        nav = self.yaml_parser.get_nav_files()
        for link in self.md_parser.find_local_links():
            self._validate_link(link, nav, report)
        self._check_docstring_links(report)

    def _validate_link(
        self, link: LocalLink, nav: set[str] | None, report: DriftReport
    ) -> None:
        """Validate a single local link against filesystem and mkdocs rules.

        Checks: (1) path resolves to existing file, (2) notebook links omit
        .ipynb extension, (3) .py files are included in mkdocs nav.
        """
        fp = link.path.split("#")[0].rstrip("/")
        suffix, ldir = link.file_path.suffix, link.file_path.parent
        resolved = self._resolve_path(ldir, fp, suffix)
        if not resolved:
            report.broken_local_links.append(self._broken(link, fp))
        elif suffix == ".ipynb" and fp.endswith(".ipynb"):
            report.broken_local_links.append(
                self._broken(link, fp, "notebook links should omit .ipynb")
            )
        elif fp.endswith(".py") and nav:
            try:
                if str(resolved.relative_to(self.root_path / "docs")) not in nav:
                    report.broken_local_links.append(
                        self._broken(link, link.path, ".py file not in mkdocs nav")
                    )
            except ValueError:
                pass

    def _resolve_path(self, ldir: Path, fp: str, suffix: str) -> Path | None:
        """Try multiple strategies to resolve a local link path.

        Resolution order: (1) direct relative from link's dir, (2) ../ from
        docs root, (3) absolute from project root, (4) mkdocs URL-style with
        auto-extension for notebooks. Returns resolved Path or None.
        """
        docs = self.root_path / "docs"
        # Direct relative
        if (r := (ldir / fp).resolve()).exists():
            return r
        # ../ from docs root
        if fp.startswith("..") and (r := (docs / fp).resolve()).exists():
            return r
        # Absolute from project root
        if (
            fp.startswith("/")
            and (r := (self.root_path / fp.lstrip("/")).resolve()).exists()
        ):
            return r
        # mkdocs URL-style
        if fp.startswith(".."):
            src = next(
                (f for f in ldir.iterdir() if f.suffix == suffix),
                ldir / (ldir.name + suffix),
            )
            r = (ldir / src.stem / fp).resolve()
            if r.exists():
                return r
            if not r.suffix:
                for ext in (".md", ".ipynb") if suffix == ".ipynb" else (".md",):
                    if r.with_suffix(ext).exists():
                        return r.with_suffix(ext)
        return None

    def _broken(
        self, link: LocalLink, path: str, reason: str | None = None
    ) -> BrokenLinkInfo:
        """Create a BrokenLinkInfo dict from a LocalLink."""
        info: BrokenLinkInfo = {
            "path": path,
            "location": f"{link.file_path}:{link.line_number}",
            "text": link.text,
        }
        if reason:
            info["reason"] = reason
        return info

    def _check_docstring_links(self, report: DriftReport) -> None:
        """Check local links in Python docstrings.

        Links resolve relative to the md file containing the ::: directive
        (matching mkdocstrings rendering). Builds fqn→dir map including
        short-name aliases for re-exported APIs.
        """
        docs = self.root_path / "docs"
        refs = {
            r.reference: r.file_path.parent
            for r in self.md_parser.find_mkdocstrings_refs()
        }
        for r, p in list(refs.items()):
            short = r.split(".")[0] + "." + r.rsplit(".", 1)[-1]
            if short != r:
                refs.setdefault(short, p)
        for m in self.modules:
            apis, _ = self.code_analyzer.get_all_public_apis(m, self.ignore_submodules)
            for api in apis:
                if not api.docstring:
                    continue
                fqn, base = f"{api.module}.{api.name}", refs.get(
                    f"{api.module}.{api.name}", docs
                )
                for link in self.md_parser.parse_local_links_in_text(api.docstring, base):
                    fp = link.path.split("#")[0]
                    if not self._resolve_ds_link(fp, base, docs):
                        report.broken_local_links.append(
                            {
                                "path": link.path,
                                "location": f"{fqn} (docstring):{link.line_number}",
                                "text": link.text,
                            }
                        )

    def _resolve_ds_link(self, fp: str, base: Path, docs: Path) -> Path | None:
        """Resolve a docstring link using multiple base directories.

        Tries: (1) relative from base (API's doc page dir), (2) ../ from
        docs root, (3) absolute from project root. Returns first match.
        """
        for b, pre in [(base, ""), (docs, ".."), (self.root_path, "/")]:
            if not pre or fp.startswith(pre):
                r = (b / (fp.lstrip("/") if pre == "/" else fp)).resolve()
                if r.exists():
                    return r
        return None

    def _check_external_links(self, report: DriftReport, verbose: bool) -> None:
        """Validate external HTTP/HTTPS links via async requests.

        Uses LinkChecker with aiohttp (or urllib fallback). Broken links
        appended to report.broken_external_links with status code/error.
        """
        if verbose:
            print("Finding external links...")
        links = self.md_parser.find_external_links()
        if verbose:
            print(f"Found {len(links)} links, checking...")
        for r in self.link_checker.check_links(links, verbose):
            if r.is_broken:
                report.broken_external_links.append(
                    {
                        "url": r.link.url,
                        "status": r.status_code or r.error,
                        "location": f"{r.link.file_path}:{r.link.line_number}",
                        "text": r.link.text,
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
        """Evaluate docstring quality using LLM.

        Lazily imports QualityChecker to avoid hard deps. Supports ollama
        (default: qwen2.5:3b) and openai (default: gpt-4o-mini) backends.
        Issues appended to report.quality_issues.
        """
        try:
            from .llm_checker import QualityChecker
        except ImportError as e:
            report.warnings.append(
                f"Quality checks skipped: {e}. Install with: pip install doc-checker[llm]"
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
            print(f"LLM quality checks ({backend}, {checker.backend.model})...")
        for m in self.modules:
            report.quality_issues.extend(
                checker.check_module_quality(m, verbose, sample_rate)
            )
