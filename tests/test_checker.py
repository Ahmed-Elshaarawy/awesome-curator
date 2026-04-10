"""
tests/test_checker.py
=====================
Unit tests for curator/checker.py.

aiohttp calls are mocked via aioresponses so no real network requests occur.
"""

from __future__ import annotations

import pytest
from aioresponses import aioresponses

from curator.checker import CheckResult, LinkChecker
from tests.conftest import make_repo


# ─────────────────────────────────────────────────────────────────────────────
# check_all — alive URLs
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_check_all_alive_returns_alive():
    """URLs that return HTTP 200 should be marked as alive."""
    checker = LinkChecker(timeout=5, concurrency=2)
    urls = [
        "https://github.com/owner/repo1",
        "https://github.com/owner/repo2",
    ]

    with aioresponses() as mock:
        for url in urls:
            mock.head(url, status=200)

        results = await checker.check_all(urls)

    assert all(r.is_alive for r in results.values())
    assert all(r.status_code == 200 for r in results.values())


@pytest.mark.asyncio
async def test_check_all_403_treated_as_alive():
    """HTTP 403 (auth required) is treated as alive — the resource exists."""
    checker = LinkChecker(timeout=5, concurrency=2)
    url = "https://github.com/private/repo"

    with aioresponses() as mock:
        mock.head(url, status=403)

        results = await checker.check_all([url])

    assert results[url].is_alive is True
    assert results[url].status_code == 403


@pytest.mark.asyncio
async def test_check_all_301_redirect_treated_as_alive():
    """HTTP 301 redirects are treated as alive (resource moved, not gone)."""
    checker = LinkChecker(timeout=5, concurrency=2)
    url = "https://github.com/old/repo"

    with aioresponses() as mock:
        mock.head(url, status=301)

        results = await checker.check_all([url])

    assert results[url].is_alive is True


# ─────────────────────────────────────────────────────────────────────────────
# check_all — dead URLs
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_check_all_404_is_dead():
    """HTTP 404 means the resource is gone — should be marked dead."""
    checker = LinkChecker(timeout=5, concurrency=2)
    url = "https://github.com/deleted/repo"

    with aioresponses() as mock:
        # HEAD returns 404; GET fallback also returns 404
        mock.head(url, status=404)
        mock.get(url, status=404)

        results = await checker.check_all([url])

    assert results[url].is_alive is False


@pytest.mark.asyncio
async def test_check_all_connection_error_is_dead():
    """Connection errors should mark a URL as dead with an error message."""
    import aiohttp

    checker = LinkChecker(timeout=5, concurrency=2)
    url = "https://nonexistent-domain-xyz.example"

    with aioresponses() as mock:
        mock.head(url, exception=aiohttp.ClientConnectionError("refused"))

        results = await checker.check_all([url])

    assert results[url].is_alive is False
    assert results[url].error is not None


@pytest.mark.asyncio
async def test_check_all_timeout_is_dead():
    """Timeout errors should mark a URL as dead."""
    import asyncio

    checker = LinkChecker(timeout=5, concurrency=2)
    url = "https://slow-server.example"

    with aioresponses() as mock:
        mock.head(url, exception=asyncio.TimeoutError())

        results = await checker.check_all([url])

    assert results[url].is_alive is False
    assert results[url].error == "Timeout"


# ─────────────────────────────────────────────────────────────────────────────
# check_all — edge cases
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_check_all_empty_list():
    """Passing an empty list should return an empty dict without errors."""
    checker = LinkChecker(timeout=5, concurrency=2)
    results = await checker.check_all([])
    assert results == {}


@pytest.mark.asyncio
async def test_check_all_deduplicates_urls():
    """Each URL key in results should be unique."""
    checker = LinkChecker(timeout=5, concurrency=2)
    urls = ["https://github.com/owner/repo"] * 3  # same URL three times

    with aioresponses() as mock:
        for _ in urls:
            mock.head("https://github.com/owner/repo", status=200)

        results = await checker.check_all(urls)

    # The dict key deduplicates, but all three tasks should complete
    assert "https://github.com/owner/repo" in results


# ─────────────────────────────────────────────────────────────────────────────
# run_check (sync wrapper)
# ─────────────────────────────────────────────────────────────────────────────


def test_run_check_sync_wrapper():
    """run_check should work identically to check_all from a sync context."""
    checker = LinkChecker(timeout=5, concurrency=2)
    url = "https://github.com/owner/repo"

    with aioresponses() as mock:
        mock.head(url, status=200)
        results = checker.run_check([url])

    assert results[url].is_alive is True


# ─────────────────────────────────────────────────────────────────────────────
# filter_alive
# ─────────────────────────────────────────────────────────────────────────────


def test_filter_alive_splits_correctly():
    """filter_alive should separate alive repos from dead ones."""
    repo_alive = make_repo("alive-repo", stars=500)
    repo_dead = make_repo("dead-repo", stars=200)

    check_results = {
        repo_alive.url: CheckResult(url=repo_alive.url, is_alive=True, status_code=200, error=None),
        repo_dead.url: CheckResult(url=repo_dead.url, is_alive=False, status_code=404, error=None),
    }

    alive, dead = LinkChecker.filter_alive([repo_alive, repo_dead], check_results)

    assert repo_alive in alive
    assert repo_dead in dead
    assert repo_alive not in dead
    assert repo_dead not in alive


def test_filter_alive_missing_result_treated_as_alive():
    """A repo whose URL has no check result is conservatively kept alive."""
    repo = make_repo("unknown-repo")
    alive, dead = LinkChecker.filter_alive([repo], check_results={})

    assert repo in alive
    assert dead == []
