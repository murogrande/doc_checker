"""Tests for ExternalLinksChecker."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from doc_checker.checkers_folder.external_links import ExternalLinksChecker
from doc_checker.models import DriftReport, ExternalLink, LinkCheckResult


@pytest.fixture
def ext_link() -> ExternalLink:
    return ExternalLink(
        url="https://example.com",
        text="Example",
        file_path=Path("docs/index.md"),
        line_number=5,
    )


@pytest.fixture
def broken_link() -> ExternalLink:
    return ExternalLink(
        url="https://broken.invalid/page",
        text="Broken",
        file_path=Path("docs/api.md"),
        line_number=12,
    )


class TestExternalLinksChecker:
    def test_check_sets_total_links(self, ext_link: ExternalLink):
        md_parser = MagicMock()
        md_parser.find_external_links.return_value = [ext_link]
        link_checker = MagicMock()
        link_checker.check_links.return_value = []

        report = DriftReport()
        ExternalLinksChecker(md_parser, link_checker).check(report)

        assert report.total_external_links == 1

    def test_check_no_links(self):
        md_parser = MagicMock()
        md_parser.find_external_links.return_value = []
        link_checker = MagicMock()
        link_checker.check_links.return_value = []

        report = DriftReport()
        ExternalLinksChecker(md_parser, link_checker).check(report)

        assert report.total_external_links == 0
        assert report.broken_external_links == []

    def test_check_all_links_ok(self, ext_link: ExternalLink):
        ok_result = LinkCheckResult(
            link=ext_link, status_code=200, error=None, is_broken=False
        )
        md_parser = MagicMock()
        md_parser.find_external_links.return_value = [ext_link]
        link_checker = MagicMock()
        link_checker.check_links.return_value = [ok_result]

        report = DriftReport()
        ExternalLinksChecker(md_parser, link_checker).check(report)

        assert report.total_external_links == 1
        assert report.broken_external_links == []

    def test_check_broken_link_status_code(self, broken_link: ExternalLink):
        result = LinkCheckResult(
            link=broken_link, status_code=404, error=None, is_broken=True
        )
        md_parser = MagicMock()
        md_parser.find_external_links.return_value = [broken_link]
        link_checker = MagicMock()
        link_checker.check_links.return_value = [result]

        report = DriftReport()
        ExternalLinksChecker(md_parser, link_checker).check(report)

        assert len(report.broken_external_links) == 1
        entry = report.broken_external_links[0]
        assert entry["url"] == "https://broken.invalid/page"
        assert entry["status"] == 404
        assert entry["location"] == "docs/api.md:12"
        assert entry["text"] == "Broken"

    def test_check_broken_link_error_string(self, broken_link: ExternalLink):
        result = LinkCheckResult(
            link=broken_link, status_code=None, error="Timeout", is_broken=True
        )
        md_parser = MagicMock()
        md_parser.find_external_links.return_value = [broken_link]
        link_checker = MagicMock()
        link_checker.check_links.return_value = [result]

        report = DriftReport()
        ExternalLinksChecker(md_parser, link_checker).check(report)

        assert len(report.broken_external_links) == 1
        assert report.broken_external_links[0]["status"] == "Timeout"

    def test_check_mixed_results(self, ext_link: ExternalLink, broken_link: ExternalLink):
        ok = LinkCheckResult(link=ext_link, status_code=200, error=None, is_broken=False)
        bad = LinkCheckResult(
            link=broken_link, status_code=500, error=None, is_broken=True
        )
        md_parser = MagicMock()
        md_parser.find_external_links.return_value = [ext_link, broken_link]
        link_checker = MagicMock()
        link_checker.check_links.return_value = [ok, bad]

        report = DriftReport()
        ExternalLinksChecker(md_parser, link_checker).check(report)

        assert report.total_external_links == 2
        assert len(report.broken_external_links) == 1
        assert report.broken_external_links[0]["url"] == broken_link.url

    def test_verbose_passed_to_link_checker(self, ext_link: ExternalLink):
        md_parser = MagicMock()
        md_parser.find_external_links.return_value = [ext_link]
        link_checker = MagicMock()
        link_checker.check_links.return_value = []

        report = DriftReport()
        ExternalLinksChecker(md_parser, link_checker, verbose=True).check(report)

        link_checker.check_links.assert_called_once_with([ext_link], True)

    def test_validate_not_broken_skipped(self, ext_link: ExternalLink):
        ok = LinkCheckResult(link=ext_link, status_code=200, error=None, is_broken=False)
        checker = ExternalLinksChecker(MagicMock(), MagicMock())
        report = DriftReport()

        checker.validate(ok, report)

        assert report.broken_external_links == []

    def test_validate_broken_appends(self, broken_link: ExternalLink):
        bad = LinkCheckResult(
            link=broken_link, status_code=404, error=None, is_broken=True
        )
        checker = ExternalLinksChecker(MagicMock(), MagicMock())
        report = DriftReport()

        checker.validate(bad, report)

        assert len(report.broken_external_links) == 1

    def test_collect_delegates_to_link_checker(self, ext_link: ExternalLink):
        ok = LinkCheckResult(link=ext_link, status_code=200, error=None, is_broken=False)
        link_checker = MagicMock()
        link_checker.check_links.return_value = [ok]

        checker = ExternalLinksChecker(MagicMock(), link_checker)
        checker._links = [ext_link]

        results = list(checker.collect())
        assert results == [ok]
