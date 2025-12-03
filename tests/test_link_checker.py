"""Tests for link_checker module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from doc_checker.link_checker import LinkChecker
from doc_checker.models import ExternalLink

try:
    import aiohttp

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

        result = await checker._check_one(
            mock_session, sample_links[0], semaphore, False
        )

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

        result = await checker._check_one(
            mock_session, sample_links[0], semaphore, False
        )

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
