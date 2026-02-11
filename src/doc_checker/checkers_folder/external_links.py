from __future__ import annotations

from typing import Any, Iterator

from doc_checker.link_checker import LinkChecker
from doc_checker.models import DriftReport, LinkCheckResult
from doc_checker.parsers import MarkdownParser

from .base import DocArtifactChecker


class ExternalLinksChecker(DocArtifactChecker):
    """Check external HTTP links in documentation for validity."""

    def __init__(
        self, md_parser: MarkdownParser, link_checker: LinkChecker, verbose: bool = False
    ):
        self.md_parser = md_parser
        self.link_checker = link_checker
        self.verbose = verbose

    def collect(self) -> Iterator[Any]:
        yield from self.link_checker.check_links(self._links, self.verbose)

    def validate(self, result: LinkCheckResult, report: DriftReport) -> None:
        if result.is_broken:
            report.broken_external_links.append(
                {
                    "url": result.link.url,
                    "status": result.status_code or result.error,
                    "location": f"{result.link.file_path}:{result.link.line_number}",
                    "text": result.link.text,
                }
            )

    def check(self, report: DriftReport) -> None:
        if self.verbose:
            print("Finding external links...")
        self._links = self.md_parser.find_external_links()
        report.total_external_links = len(self._links)
        if self.verbose:
            print(f"Found {len(self._links)} links, checking...")
        super().check(report)  # runs collect and validate loop
