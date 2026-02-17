from __future__ import annotations

from typing import Iterator

from doc_checker.models import DriftReport
from doc_checker.utils.parsers import YamlParser

from .base import DocArtifactChecker


class NavPathsChecker(DocArtifactChecker):
    """Detect mkdocs.yml nav entries pointing to missing files."""

    def __init__(self, yaml_parser: YamlParser):
        self.yaml_parser = yaml_parser

    def collect(self) -> Iterator[str]:
        """Yield file paths from mkdocs.yml nav section."""
        nav = self.yaml_parser._load_nav()
        if nav is None:
            return
        yield from self.yaml_parser._collect_nav_paths(nav)

    def validate(self, path: str, report: DriftReport) -> None:
        """Append missing nav path to report.broken_mkdocs_paths."""
        if not (self.yaml_parser.docs_path / path).exists():
            report.broken_mkdocs_paths.append({"path": path, "location": "mkdocs.yml"})
