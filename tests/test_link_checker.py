"""Tests for link_checker module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from doc_checker.models import ExternalLink
from doc_checker.utils.link_checker import LinkChecker

try:
    import aiohttp  # noqa: F401

    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False


@pytest.fixture
def sample_links() -> list[ExternalLink]:
    """Create sample external links."""
    return [
        ExternalLink(
            url="https://example.com",
            text="Example",
            file_path=Path("test.md"),
            line_number=1,
        ),
        ExternalLink(
            url="https://github.com",
            text="GitHub",
            file_path=Path("test.md"),
            line_number=2,
        ),
        ExternalLink(
            url="https://example.com",  # Duplicate
            text="Example Again",
            file_path=Path("test.md"),
            line_number=3,
        ),
    ]


class TestLinkChecker:
    """Test LinkChecker."""

    def test_deduplicate(self, sample_links: list[ExternalLink]):
        checker = LinkChecker()
        unique = checker._deduplicate(sample_links)

        assert len(unique) == 2
        assert unique[0].url == "https://example.com"
        assert unique[1].url == "https://github.com"

    def test_should_skip_domain(self):
        checker = LinkChecker()

        assert checker._should_skip("https://pasqalworkspace.slack.com/foo", False)
        assert checker._should_skip("https://cdn.jsdelivr.net/package", False)
        assert not checker._should_skip("https://example.com", False)

    @pytest.mark.skipif(not AIOHTTP_AVAILABLE, reason="aiohttp not available")
    @pytest.mark.asyncio
    async def test_check_one_success(self, sample_links: list[ExternalLink]):
        """Test successful link check."""
        checker = LinkChecker()

        # Mock aiohttp session
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        mock_session = MagicMock()
        mock_session.head.return_value = mock_response

        semaphore = AsyncMock()
        semaphore.__aenter__.return_value = None
        semaphore.__aexit__.return_value = None

        result = await checker._check_one(mock_session, sample_links[0], semaphore, False)

        assert result.is_broken is False
        assert result.status_code == 200
        assert result.error is None

    @pytest.mark.skipif(not AIOHTTP_AVAILABLE, reason="aiohttp not available")
    @pytest.mark.asyncio
    async def test_check_one_not_found(self, sample_links: list[ExternalLink]):
        """Test 404 link check."""
        checker = LinkChecker()

        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        mock_session = MagicMock()
        mock_session.head.return_value = mock_response

        semaphore = AsyncMock()
        semaphore.__aenter__.return_value = None
        semaphore.__aexit__.return_value = None

        result = await checker._check_one(mock_session, sample_links[0], semaphore, False)

        assert result.is_broken is True
        assert result.status_code == 404

    @pytest.mark.skipif(not AIOHTTP_AVAILABLE, reason="aiohttp not available")
    @pytest.mark.asyncio
    async def test_check_one_acceptable_status(self, sample_links: list[ExternalLink]):
        """Test acceptable status codes (403, 405, 429)."""
        checker = LinkChecker()

        for status in [403, 429]:
            mock_response = AsyncMock()
            mock_response.status = status
            mock_response.__aenter__.return_value = mock_response
            mock_response.__aexit__.return_value = None

            mock_session = MagicMock()
            mock_session.head.return_value = mock_response

            semaphore = AsyncMock()
            semaphore.__aenter__.return_value = None
            semaphore.__aexit__.return_value = None

            result = await checker._check_one(
                mock_session, sample_links[0], semaphore, False
            )

            assert result.is_broken is False
            assert result.status_code == status

    def test_check_links_sync_fallback(self, sample_links: list[ExternalLink]):
        """Test sync fallback when aiohttp unavailable."""
        checker = LinkChecker()

        # Mock urllib
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.getcode.return_value = 200
            mock_urlopen.return_value.__enter__.return_value = mock_response

            results = checker._check_sync(sample_links[:1], False)

            assert len(results) == 1
            assert results[0].is_broken is False
            assert results[0].status_code == 200

    def test_check_links_filters_duplicates(self, sample_links: list[ExternalLink]):
        """Test that check_links deduplicates."""
        checker = LinkChecker()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.getcode.return_value = 200
            mock_urlopen.return_value.__enter__.return_value = mock_response

            results = checker._check_sync(sample_links, False)

            # Should only check 2 unique URLs
            assert len(results) == 2

    def test_empty_link_list(self):
        """Test with empty list."""
        checker = LinkChecker()
        results = checker._check_sync([], False)
        assert results == []


class TestCheckLinksPublicAPI:
    """Test check_links() public API entry point."""

    def test_check_links_uses_sync_fallback_when_no_aiohttp(
        self, sample_links: list[ExternalLink]
    ):
        """check_links() falls back to sync when aiohttp unavailable."""
        checker = LinkChecker()

        with (
            patch.object(checker, "_check_sync", return_value=[]) as mock_sync,
            patch("doc_checker.utils.link_checker.AIOHTTP_AVAILABLE", False),
        ):
            results = checker.check_links(sample_links[:1], verbose=False)

            mock_sync.assert_called_once()
            assert results == []

    def test_check_links_uses_async_when_aiohttp_available(
        self, sample_links: list[ExternalLink]
    ):
        """check_links() uses async path when aiohttp is available."""
        if not AIOHTTP_AVAILABLE:
            pytest.skip("aiohttp not available")

        checker = LinkChecker()

        with patch.object(
            checker, "_check_async", new_callable=AsyncMock, return_value=[]
        ) as mock_async:
            results = checker.check_links(sample_links[:1], verbose=False)

            mock_async.assert_called_once()
            assert results == []

    def test_check_links_empty_list(self):
        """check_links() with empty list returns empty results."""
        checker = LinkChecker()
        results = checker.check_links([], verbose=False)
        assert results == []

    def test_check_links_skips_domains(self, sample_links: list[ExternalLink]):
        """check_links() skips URLs in SKIP_DOMAINS."""
        checker = LinkChecker()
        skip_link = ExternalLink(
            url="https://pasqalworkspace.slack.com/channel",
            text="Slack",
            file_path=Path("test.md"),
            line_number=1,
        )

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.getcode.return_value = 200
            mock_urlopen.return_value.__enter__.return_value = mock_response

            with patch("doc_checker.utils.link_checker.AIOHTTP_AVAILABLE", False):
                results = checker.check_links([skip_link], verbose=False)

            # Slack URL should be skipped, no request made
            assert len(results) == 0
            mock_urlopen.assert_not_called()

    def test_check_links_handles_timeout(self, sample_links: list[ExternalLink]):
        """check_links() handles timeout errors gracefully."""
        import urllib.error

        checker = LinkChecker()

        with (
            patch("urllib.request.urlopen") as mock_urlopen,
            patch("doc_checker.utils.link_checker.AIOHTTP_AVAILABLE", False),
        ):
            mock_urlopen.side_effect = urllib.error.URLError("timed out")
            results = checker.check_links(sample_links[:1], verbose=False)

            assert len(results) == 1
            assert results[0].is_broken is True
            assert "timed out" in str(results[0].error)

    def test_check_links_handles_connection_error(self, sample_links: list[ExternalLink]):
        """check_links() handles connection errors gracefully."""
        import urllib.error

        checker = LinkChecker()

        with (
            patch("urllib.request.urlopen") as mock_urlopen,
            patch("doc_checker.utils.link_checker.AIOHTTP_AVAILABLE", False),
        ):
            mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
            results = checker.check_links(sample_links[:1], verbose=False)

            assert len(results) == 1
            assert results[0].is_broken is True
            assert results[0].error is not None

    def test_check_links_acceptable_status_403(self, sample_links: list[ExternalLink]):
        """check_links() treats 403 as acceptable (not broken)."""
        import urllib.error

        checker = LinkChecker()

        with (
            patch("urllib.request.urlopen") as mock_urlopen,
            patch("doc_checker.utils.link_checker.AIOHTTP_AVAILABLE", False),
        ):
            mock_urlopen.side_effect = urllib.error.HTTPError(
                sample_links[0].url, 403, "Forbidden", {}, None
            )
            results = checker.check_links(sample_links[:1], verbose=False)

            assert len(results) == 1
            assert results[0].is_broken is False
            assert results[0].status_code == 403

    def test_check_links_deduplicates(self, sample_links: list[ExternalLink]):
        """check_links() deduplicates URLs before checking."""
        checker = LinkChecker()

        with (
            patch("urllib.request.urlopen") as mock_urlopen,
            patch("doc_checker.utils.link_checker.AIOHTTP_AVAILABLE", False),
        ):
            mock_response = MagicMock()
            mock_response.getcode.return_value = 200
            mock_urlopen.return_value.__enter__.return_value = mock_response

            # sample_links has 3 items, 2 unique URLs
            results = checker.check_links(sample_links, verbose=False)

            assert len(results) == 2
            assert mock_urlopen.call_count == 2
