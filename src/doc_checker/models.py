"""Data models for documentation checker."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SignatureInfo:
    """Function/method/class signature info."""

    name: str
    module: str
    parameters: list[str]
    return_annotation: str | None
    docstring: str | None
    is_public: bool
    kind: str  # 'function', 'method', 'class'


@dataclass
class DocReference:
    """Mkdocstrings reference in docs."""

    reference: str
    file_path: Path
    line_number: int


@dataclass
class ExternalLink:
    """External HTTP link in docs."""

    url: str
    text: str
    file_path: Path
    line_number: int


@dataclass
class LocalLink:
    """Local file link in docs."""

    path: str
    text: str
    file_path: Path
    line_number: int


@dataclass
class LinkCheckResult:
    """Result of checking external link."""

    link: ExternalLink
    status_code: int | None
    error: str | None
    is_broken: bool


@dataclass
class DriftReport:
    """Documentation drift issues."""

    missing_in_docs: list[str] = field(default_factory=list)
    signature_mismatches: list[dict[str, Any]] = field(default_factory=list)
    broken_references: list[str] = field(default_factory=list)
    broken_external_links: list[dict[str, Any]] = field(default_factory=list)
    broken_local_links: list[dict[str, Any]] = field(default_factory=list)
    broken_mkdocs_paths: list[dict[str, Any]] = field(default_factory=list)
    undocumented_params: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def has_issues(self) -> bool:
        return bool(
            self.missing_in_docs
            or self.signature_mismatches
            or self.broken_references
            or self.broken_external_links
            or self.broken_local_links
            or self.broken_mkdocs_paths
            or self.undocumented_params
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "missing_in_docs": self.missing_in_docs,
            "signature_mismatches": self.signature_mismatches,
            "broken_references": self.broken_references,
            "broken_external_links": self.broken_external_links,
            "broken_local_links": self.broken_local_links,
            "broken_mkdocs_paths": self.broken_mkdocs_paths,
            "undocumented_params": self.undocumented_params,
            "warnings": self.warnings,
            "has_issues": self.has_issues(),
        }
