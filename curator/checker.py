"""
curator/checker.py
==================
Asynchronous link validator using aiohttp.

Checks all repository URLs concurrently, detects dead links (timeouts,
4xx/5xx errors, connection refused), and exposes a helper to split a
list of RepoInfo objects into alive vs. dead.

Design notes
------------
- A semaphore caps concurrent requests to avoid hammering GitHub or CDNs.
- HEAD is tried first (cheap); if the server rejects HEAD we fall back to GET.
- HTTP 403 / 429 are treated as *alive* — the resource exists but requires
  auth or is rate-limited, which is expected for GitHub repos.
- SSL verification is disabled for link checking only (many mirrors use
  self-signed certs). Authentication credentials are never sent.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

import aiohttp

if TYPE_CHECKING:
    from .fetcher import RepoInfo

logger = logging.getLogger(__name__)

# HTTP statuses we consider "the resource exists"
_ALIVE_STATUSES: frozenset[int] = frozenset(
    {200, 201, 204, 301, 302, 307, 308, 403, 429}
)

_DEFAULT_TIMEOUT = 10      # seconds per request
_DEFAULT_CONCURRENCY = 20  # max simultaneous open connections

_USER_AGENT = (
    "Mozilla/5.0 (compatible; awesome-curator/1.0; "
    "+https://github.com/your-org/awesome-curator)"
)


# ─────────────────────────────────────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class CheckResult:
    """Result of a single URL validation attempt."""

    url: str
    is_alive: bool
    status_code: Optional[int]
    error: Optional[str]


# ─────────────────────────────────────────────────────────────────────────────
# Checker
# ─────────────────────────────────────────────────────────────────────────────


class LinkChecker:
    """
    Validates a list of URLs concurrently using aiohttp.

    Parameters
    ----------
    timeout:
        Per-request timeout in seconds.
    concurrency:
        Maximum number of simultaneous HTTP connections.
    """

    def __init__(
        self,
        timeout: int = _DEFAULT_TIMEOUT,
        concurrency: int = _DEFAULT_CONCURRENCY,
    ) -> None:
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._concurrency = concurrency

    # ── Public API ────────────────────────────────────────────────────────────

    async def check_all(self, urls: list[str]) -> dict[str, CheckResult]:
        """
        Validate all URLs concurrently.

        Parameters
        ----------
        urls:
            List of URLs to check.

        Returns
        -------
        dict[str, CheckResult]
            Mapping of URL → CheckResult for every URL provided.
        """
        if not urls:
            return {}

        semaphore = asyncio.Semaphore(self._concurrency)
        connector = aiohttp.TCPConnector(ssl=False, limit=self._concurrency)
        headers = {"User-Agent": _USER_AGENT}

        async with aiohttp.ClientSession(
            connector=connector,
            headers=headers,
            timeout=self._timeout,
        ) as session:
            tasks = [self._check_one(session, semaphore, url) for url in urls]
            results: list[CheckResult] = await asyncio.gather(*tasks)

        return {r.url: r for r in results}

    def run_check(self, urls: list[str]) -> dict[str, CheckResult]:
        """
        Synchronous wrapper around ``check_all``.

        Use this when calling from a non-async context (e.g., the CLI).
        """
        return asyncio.run(self.check_all(urls))

    @staticmethod
    def filter_alive(
        repos: list[RepoInfo],
        check_results: dict[str, CheckResult],
    ) -> tuple[list[RepoInfo], list[RepoInfo]]:
        """
        Split a list of repos into alive and dead based on check results.

        Repos whose URL is not present in *check_results* (e.g., the check
        was skipped) are conservatively treated as alive.

        Returns
        -------
        tuple[list[RepoInfo], list[RepoInfo]]
            ``(alive_repos, dead_repos)``
        """
        alive: list[RepoInfo] = []
        dead: list[RepoInfo] = []

        for repo in repos:
            result = check_results.get(repo.url)
            if result is None or result.is_alive:
                alive.append(repo)
            else:
                logger.warning(
                    "Dead link removed: %s  [%s]",
                    repo.url,
                    result.error or f"HTTP {result.status_code}",
                )
                dead.append(repo)

        return alive, dead

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _check_one(
        self,
        session: aiohttp.ClientSession,
        semaphore: asyncio.Semaphore,
        url: str,
    ) -> CheckResult:
        """
        Check a single URL, honouring the semaphore to cap concurrency.

        Strategy:
        1. Try HEAD (no body downloaded).
        2. If the server responds with a non-alive status, retry with GET
           because some servers (e.g. GitHub raw) reject HEAD requests.
        """
        async with semaphore:
            try:
                async with session.head(url, allow_redirects=True) as resp:
                    if resp.status in _ALIVE_STATUSES:
                        return CheckResult(
                            url=url,
                            is_alive=True,
                            status_code=resp.status,
                            error=None,
                        )
                    # HEAD rejected — retry with GET (read only first chunk)
                    async with session.get(url, allow_redirects=True) as get_resp:
                        is_alive = get_resp.status in _ALIVE_STATUSES
                        return CheckResult(
                            url=url,
                            is_alive=is_alive,
                            status_code=get_resp.status,
                            error=None,
                        )

            except aiohttp.ClientError as exc:
                logger.debug("Link check failed for %s: %s", url, exc)
                return CheckResult(url=url, is_alive=False, status_code=None, error=str(exc))

            except asyncio.TimeoutError:
                logger.debug("Link check timed out for %s", url)
                return CheckResult(url=url, is_alive=False, status_code=None, error="Timeout")
