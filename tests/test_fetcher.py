"""
tests/test_fetcher.py
=====================
Unit tests for curator/fetcher.py.

PyGitHub calls are fully mocked — no real HTTP requests are made.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from curator.fetcher import GitHubFetcher, RepoInfo
from tests.conftest import make_gh_repo


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _patch_github(monkeypatch):
    """
    Patch Github at import time so no real network calls happen.
    Each test that needs a specific search result overrides mock_github.
    """
    with patch("curator.fetcher.Github") as mock_cls:
        yield mock_cls


@pytest.fixture
def token_env(monkeypatch):
    """Set a fake GITHUB_TOKEN in the environment."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_fake_token_for_tests")


# ─────────────────────────────────────────────────────────────────────────────
# Initialisation tests
# ─────────────────────────────────────────────────────────────────────────────


def test_init_raises_without_token(monkeypatch):
    """GitHubFetcher must raise EnvironmentError when no token is available."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(EnvironmentError, match="GITHUB_TOKEN"):
        GitHubFetcher()


def test_init_succeeds_with_env_token(token_env):
    """GitHubFetcher initialises successfully when GITHUB_TOKEN is set."""
    fetcher = GitHubFetcher()
    assert fetcher is not None


def test_init_succeeds_with_explicit_token():
    """GitHubFetcher accepts an explicit token argument (overrides env)."""
    fetcher = GitHubFetcher(token="explicit_token")
    assert fetcher is not None


# ─────────────────────────────────────────────────────────────────────────────
# _to_repo_info tests
# ─────────────────────────────────────────────────────────────────────────────


def test_to_repo_info_basic():
    """_to_repo_info correctly maps PyGitHub fields to RepoInfo."""
    gh_repo = make_gh_repo(
        name="awesome-llm",
        owner="ai-org",
        stars=3_000,
        forks=120,
        description="A great LLM framework",
        language="Python",
        topics=["llm", "ai"],
    )
    info = GitHubFetcher._to_repo_info(gh_repo, "llm_frameworks")

    assert info.name == "awesome-llm"
    assert info.full_name == "ai-org/awesome-llm"
    assert info.stars == 3_000
    assert info.forks == 120
    assert info.language == "Python"
    assert info.category_id == "llm_frameworks"
    assert "llm" in info.topics


def test_to_repo_info_truncates_long_description():
    """Descriptions longer than 200 chars should be truncated with an ellipsis."""
    long_desc = "X" * 300
    gh_repo = make_gh_repo(description=long_desc)

    info = GitHubFetcher._to_repo_info(gh_repo, "cat")

    # The ellipsis character "…" is 1 Unicode code point but may be multi-byte.
    # We just check that the visible length doesn't exceed 201 chars.
    assert len(info.description) <= 201
    assert info.description.endswith("…")


def test_to_repo_info_none_description_becomes_placeholder():
    """A None description is replaced with a sensible default string."""
    gh_repo = make_gh_repo(description=None)
    gh_repo.description = None

    info = GitHubFetcher._to_repo_info(gh_repo, "cat")
    assert info.description == "No description provided."


def test_to_repo_info_none_language_preserved():
    """Repos without a primary language should have language=None."""
    gh_repo = make_gh_repo(language=None)

    info = GitHubFetcher._to_repo_info(gh_repo, "cat")
    assert info.language is None


# ─────────────────────────────────────────────────────────────────────────────
# fetch_niche / _fetch_category tests (mocked search)
# ─────────────────────────────────────────────────────────────────────────────


def _make_fetcher_with_results(search_results: list, token_env) -> GitHubFetcher:
    """
    Helper: build a GitHubFetcher whose search_repositories call
    returns the given list of mock GH repos.
    """
    fetcher = GitHubFetcher(token="test_token")
    fetcher._github.search_repositories.return_value = search_results
    return fetcher


def test_fetch_niche_returns_dict_keyed_by_category(token_env):
    """fetch_niche should return a dict of category_id -> list[RepoInfo]."""
    gh_repos = [make_gh_repo(f"repo-{i}", stars=1000 - i * 10) for i in range(3)]
    fetcher = _make_fetcher_with_results(gh_repos, token_env)

    niche_config = {
        "categories": [
            {
                "id": "test_cat",
                "name": "Test",
                "topics": ["llm"],
                "min_stars": 100,
                "max_repos": 5,
            }
        ],
        "settings": {
            "exclude_archived": True,
            "exclude_forks": True,
            "deduplicate": True,
        },
    }

    result = fetcher.fetch_niche(niche_config)

    assert "test_cat" in result
    assert len(result["test_cat"]) == 3


def test_fetch_niche_excludes_archived(token_env):
    """Archived repos must be filtered out when exclude_archived=True."""
    gh_repos = [
        make_gh_repo("live-repo", archived=False),
        make_gh_repo("dead-repo", archived=True),
    ]
    fetcher = _make_fetcher_with_results(gh_repos, token_env)

    niche_config = {
        "categories": [
            {"id": "cat", "name": "Cat", "topics": ["t"], "min_stars": 0, "max_repos": 10}
        ],
        "settings": {"exclude_archived": True, "exclude_forks": True, "deduplicate": True},
    }

    result = fetcher.fetch_niche(niche_config)
    names = [r.name for r in result["cat"]]
    assert "live-repo" in names
    assert "dead-repo" not in names


def test_fetch_niche_excludes_forks(token_env):
    """Forked repos must be filtered out when exclude_forks=True."""
    gh_repos = [
        make_gh_repo("original", fork=False),
        make_gh_repo("a-fork", fork=True),
    ]
    fetcher = _make_fetcher_with_results(gh_repos, token_env)

    niche_config = {
        "categories": [
            {"id": "cat", "name": "Cat", "topics": ["t"], "min_stars": 0, "max_repos": 10}
        ],
        "settings": {"exclude_archived": True, "exclude_forks": True, "deduplicate": True},
    }

    result = fetcher.fetch_niche(niche_config)
    names = [r.name for r in result["cat"]]
    assert "original" in names
    assert "a-fork" not in names


def test_fetch_niche_deduplicates_across_categories(token_env):
    """The same repo should not appear in more than one category."""
    shared_repo = make_gh_repo("shared-repo")
    fetcher = _make_fetcher_with_results([shared_repo], token_env)

    niche_config = {
        "categories": [
            {"id": "cat_a", "name": "A", "topics": ["t1"], "min_stars": 0, "max_repos": 5},
            {"id": "cat_b", "name": "B", "topics": ["t2"], "min_stars": 0, "max_repos": 5},
        ],
        "settings": {"exclude_archived": True, "exclude_forks": True, "deduplicate": True},
    }

    result = fetcher.fetch_niche(niche_config)
    cat_a_names = {r.name for r in result["cat_a"]}
    cat_b_names = {r.name for r in result["cat_b"]}
    # shared-repo should appear in exactly one category
    assert len(cat_a_names & cat_b_names) == 0


def test_fetch_niche_respects_max_repos(token_env):
    """Results must be capped at max_repos even if more are returned."""
    gh_repos = [make_gh_repo(f"repo-{i}", stars=1000 - i) for i in range(20)]
    fetcher = _make_fetcher_with_results(gh_repos, token_env)

    niche_config = {
        "categories": [
            {"id": "cat", "name": "Cat", "topics": ["t"], "min_stars": 0, "max_repos": 5}
        ],
        "settings": {"exclude_archived": False, "exclude_forks": False, "deduplicate": False},
    }

    result = fetcher.fetch_niche(niche_config)
    assert len(result["cat"]) <= 5
