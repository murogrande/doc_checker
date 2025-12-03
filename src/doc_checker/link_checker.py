"""External link validation using async HTTP."""

from __future__ import annotations

import asyncio
from urllib.parse import urlparse

from doc_checker.models import ExternalLink, LinkCheckResult

try:
    import aiohttp

    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False


class LinkChecker:
    """Check external HTTP links."""

    SKIP_DOMAINS = {"pasqalworkspace.slack.com", "cdn.jsdelivr.net"}
    ACCEPTABLE_STATUS = {403, 405, 429}  # Blocked but exists
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    def __init__(self, timeout: float = 10.0, max_concurrent: int = 5):
        self.timeout = timeout
        self.max_concurrent = max_concurrent

    def check_links(
        self, links: list[ExternalLink], verbose: bool = False
    ) -> list[LinkCheckResult]:
        """Check links (async if available, fallback to sync)."""
        if not AIOHTTP_AVAILABLE:
            if verbose:
                print("aiohttp not available, install for async checking")
            return self._check_sync(links, verbose)
        return asyncio.run(self._check_async(links, verbose))

    async def _check_async(
        self, links: list[ExternalLink], verbose: bool
    ) -> list[LinkCheckResult]:
        """Async checking with aiohttp."""
        unique = self._deduplicate(links)
        filtered = [l for l in unique if not self._should_skip(l.url, verbose)]

        semaphore = asyncio.Semaphore(self.max_concurrent)
        connector = aiohttp.TCPConnector(limit=self.max_concurrent)

        async with aiohttp.ClientSession(
            connector=connector, headers={"User-Agent": self.USER_AGENT}
        ) as session:
            tasks = [self._check_one(session, link, semaphore, verbose) for link in filtered]
            return await asyncio.gather(*tasks)

    async def _check_one(
        self,
        session: aiohttp.ClientSession,
        link: ExternalLink,
        semaphore: asyncio.Semaphore,
        verbose: bool,
    ) -> LinkCheckResult:
        """Check single link."""
        async with semaphore:
            if verbose:
                print(f"  Checking {link.url}...")
            try:
                # Try HEAD first
                async with session.head(
                    link.url,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                    allow_redirects=True,
                ) as response:
                    status = response.status
                    if status in self.ACCEPTABLE_STATUS:
                        return LinkCheckResult(
                            link=link, status_code=status, error=None, is_broken=False
                        )
                    if status == 405:  # Try GET
                        async with session.get(
                            link.url,
                            timeout=aiohttp.ClientTimeout(total=self.timeout),
                            allow_redirects=True,
                        ) as get_resp:
                            return LinkCheckResult(
                                link=link,
                                status_code=get_resp.status,
                                error=None,
                                is_broken=get_resp.status >= 400,
                            )
                    return LinkCheckResult(
                        link=link, status_code=status, error=None, is_broken=status >= 400
                    )
            except asyncio.TimeoutError:
                return LinkCheckResult(link=link, status_code=None, error="Timeout", is_broken=True)
            except aiohttp.ClientError as e:
                return LinkCheckResult(link=link, status_code=None, error=str(e), is_broken=True)
            except Exception as e:
                return LinkCheckResult(link=link, status_code=None, error=str(e), is_broken=True)

    def _check_sync(
        self, links: list[ExternalLink], verbose: bool
    ) -> list[LinkCheckResult]:
        """Fallback sync checking with urllib."""
        import urllib.error
        import urllib.request

        results: list[LinkCheckResult] = []
        unique = self._deduplicate(links)

        for link in unique:
            if self._should_skip(link.url, verbose):
                continue
            if verbose:
                print(f"  Checking {link.url}...")

            try:
                req = urllib.request.Request(
                    link.url, headers={"User-Agent": self.USER_AGENT}, method="HEAD"
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    status = response.getcode()
                    results.append(
                        LinkCheckResult(
                            link=link, status_code=status, error=None, is_broken=status >= 400
                        )
                    )
            except urllib.error.HTTPError as e:
                if e.code in self.ACCEPTABLE_STATUS:
                    results.append(
                        LinkCheckResult(link=link, status_code=e.code, error=None, is_broken=False)
                    )
                else:
                    results.append(
                        LinkCheckResult(
                            link=link, status_code=e.code, error=str(e.reason), is_broken=True
                        )
                    )
            except urllib.error.URLError as e:
                results.append(
                    LinkCheckResult(link=link, status_code=None, error=str(e.reason), is_broken=True)
                )
            except Exception as e:
                results.append(
                    LinkCheckResult(link=link, status_code=None, error=str(e), is_broken=True)
                )

        return results

    def _deduplicate(self, links: list[ExternalLink]) -> list[ExternalLink]:
        """Keep first occurrence of each URL."""
        seen: set[str] = set()
        unique: list[ExternalLink] = []
        for link in links:
            if link.url not in seen:
                seen.add(link.url)
                unique.append(link)
        return unique

    def _should_skip(self, url: str, verbose: bool) -> bool:
        """Check if URL should be skipped."""
        parsed = urlparse(url)
        if parsed.netloc in self.SKIP_DOMAINS:
            if verbose:
                print(f"  Skipping {url} (domain in skip list)")
            return True
        return False
