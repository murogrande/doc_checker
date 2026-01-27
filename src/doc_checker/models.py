"""Data models for documentation checker."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SignatureInfo:
    """Extracted signature information from a Python function, method, or class.

    Populated by CodeAnalyzer when introspecting Python modules via importlib/inspect.

    Args:
        name: The identifier name (e.g., "MPS", "solve", "__init__").
        module: Fully qualified module path (e.g., "emu_mps", "emu_mps.mps").
        parameters: List of formatted parameter strings including type hints and defaults
            (e.g., ["tensors: list[Tensor]", "chi: int = 64"]).
        return_annotation: String representation of return type, or None if not annotated.
        docstring: The object's docstring (via inspect.getdoc), or None if missing.
        is_public: True if name doesn't start with underscore.
        kind: One of "function", "method", or "class".
    """

    name: str
    module: str
    parameters: list[str]
    return_annotation: str | None
    docstring: str | None
    is_public: bool
    kind: str


@dataclass
class DocReference:
    """A mkdocstrings reference found in documentation markdown files.

    Represents a `::: module.ClassName` directive that tells mkdocstrings
    to auto-generate documentation for that Python object.

    Args:
        reference: The dotted path being documented (e.g., "emu_mps.MPS").
        file_path: Absolute path to the markdown file containing this reference.
        line_number: 1-based line number where the reference appears.
    """

    reference: str
    file_path: Path
    line_number: int


@dataclass
class ExternalLink:
    """An external HTTP/HTTPS link found in documentation.

    Extracted from markdown links like `[text](https://...)` or bare URLs.
    Found in both .md files and Jupyter notebooks (.ipynb).

    Args:
        url: The full URL (e.g., "https://pytorch.org/docs").
        text: The link text/label, or empty string for bare URLs.
        file_path: Absolute path to the file containing this link.
        line_number: 1-based line number (or cell index for notebooks).
    """

    url: str
    text: str
    file_path: Path
    line_number: int


@dataclass
class LocalLink:
    """A local file link found in documentation markdown.

    Extracted from markdown links pointing to local files like
    `[source](../src/utils.py)` or `[notebook](examples/demo.ipynb)`.

    Args:
        path: The relative path as written in markdown (e.g., "../src/utils.py").
        text: The link text/label.
        file_path: Absolute path to the markdown file containing this link.
        line_number: 1-based line number where the link appears.
    """

    path: str
    text: str
    file_path: Path
    line_number: int


@dataclass
class LinkCheckResult:
    """Result of validating an external HTTP link.

    Produced by LinkChecker after making HEAD/GET requests to verify URLs.

    Args:
        link: The original ExternalLink that was checked.
        status_code: HTTP status code (200, 404, etc.), or None if request failed.
        error: Error message if request failed (timeout, DNS error, etc.), or None.
        is_broken: True if link is unreachable or returns 4xx/5xx status.
    """

    link: ExternalLink
    status_code: int | None
    error: str | None
    is_broken: bool


@dataclass
class QualityIssue:
    """A documentation quality problem detected by LLM analysis.

    Produced by QualityChecker when an LLM evaluates docstring quality
    for grammar, completeness, accuracy, and clarity.

    Args:
        api_name: Fully qualified name of the API (e.g., "emu_mps.MPS.__init__").
        severity: Issue severity level - "critical" (must fix), "warning" (should fix),
            or "suggestion" (nice to have).
        category: Issue type - "grammar", "params", "completeness", "accuracy", "clarity".
        message: Human-readable explanation of the problem.
        suggestion: Recommended fix with example if applicable.
        line_reference: Specific text snippet with the issue, or None.
    """

    api_name: str
    severity: str
    category: str
    message: str
    suggestion: str
    line_reference: str | None


@dataclass
class DriftReport:
    """Aggregated results from all documentation drift checks.

    The final output of DriftDetector.check_all(), containing all detected issues
    organized by category. Used by formatters to render text/JSON output.

    Args:
        missing_in_docs: Public APIs in code but not documented
            (e.g., ["emu_mps.MPS.canonical_form"]).
        signature_mismatches: APIs where docs don't match code signature (reserved).
        broken_references: mkdocstrings refs pointing to non-existent code
            (e.g., ["emu_mps.OldClass in docs/api.md:42"]).
        broken_external_links: HTTP URLs that return errors. Each dict has keys:
            url, status, location, text.
        broken_local_links: File paths that don't exist. Each dict has keys:
            path, location, text, reason (optional).
        broken_mkdocs_paths: Nav entries in mkdocs.yml pointing to missing files.
            Each dict has keys: path, location.
        undocumented_params: Functions with params not mentioned in docstring.
            Each dict has keys: name, params.
        quality_issues: LLM-detected docstring quality problems.
        warnings: Non-fatal messages (e.g., "LLM checks skipped: ollama not installed").
    """

    missing_in_docs: list[str] = field(default_factory=list)
    signature_mismatches: list[dict[str, Any]] = field(default_factory=list)
    broken_references: list[str] = field(default_factory=list)
    broken_external_links: list[dict[str, Any]] = field(default_factory=list)
    broken_local_links: list[dict[str, Any]] = field(default_factory=list)
    broken_mkdocs_paths: list[dict[str, Any]] = field(default_factory=list)
    undocumented_params: list[dict[str, Any]] = field(default_factory=list)
    quality_issues: list[QualityIssue] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def has_issues(self) -> bool:
        """Return True if any documentation issues were detected (excluding warnings)."""
        return bool(
            self.missing_in_docs
            or self.signature_mismatches
            or self.broken_references
            or self.broken_external_links
            or self.broken_local_links
            or self.broken_mkdocs_paths
            or self.undocumented_params
            or self.quality_issues
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert report to JSON-serializable dictionary for --json output."""
        return {
            "missing_in_docs": self.missing_in_docs,
            "signature_mismatches": self.signature_mismatches,
            "broken_references": self.broken_references,
            "broken_external_links": self.broken_external_links,
            "broken_local_links": self.broken_local_links,
            "broken_mkdocs_paths": self.broken_mkdocs_paths,
            "undocumented_params": self.undocumented_params,
            "quality_issues": [
                {
                    "api_name": issue.api_name,
                    "severity": issue.severity,
                    "category": issue.category,
                    "message": issue.message,
                    "suggestion": issue.suggestion,
                    "line_reference": issue.line_reference,
                }
                for issue in self.quality_issues
            ],
            "warnings": self.warnings,
            "has_issues": self.has_issues(),
        }
