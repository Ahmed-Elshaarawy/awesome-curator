"""
tests/conftest.py
=================
Shared pytest fixtures for the awesome-curator test suite.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from curator.fetcher import RepoInfo


# ─────────────────────────────────────────────────────────────────────────────
# RepoInfo factory
# ─────────────────────────────────────────────────────────────────────────────


def make_repo(
    name: str = "test-repo",
    owner: str = "owner",
    stars: int = 1_000,
    forks: int = 50,
    description: str = "A test repository",
    language: str | None = "Python",
    category_id: str = "test_cat",
    topics: list[str] | None = None,
    last_updated: datetime | None = None,
) -> RepoInfo:
    """Factory that creates a RepoInfo for use in tests."""
    return RepoInfo(
        name=name,
        full_name=f"{owner}/{name}",
        description=description,
        url=f"https://github.com/{owner}/{name}",
        stars=stars,
        forks=forks,
        last_updated=last_updated or datetime(2024, 6, 15, tzinfo=timezone.utc),
        topics=topics or ["ai", "llm"],
        language=language,
        category_id=category_id,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Niche config fixture
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_niche_config() -> dict:
    """A minimal niche configuration dict for testing the generator."""
    return {
        "name": "Test Niche",
        "tagline": "A tagline for tests",
        "description": "A description for tests.",
        "categories": [
            {
                "id": "cat_alpha",
                "name": "Alpha Category",
                "description": "The first category.",
                "topics": ["alpha"],
                "min_stars": 100,
                "max_repos": 5,
            },
            {
                "id": "cat_beta",
                "name": "Beta Category",
                "description": "The second category.",
                "topics": ["beta"],
                "min_stars": 50,
                "max_repos": 3,
            },
        ],
        "settings": {
            "exclude_archived": True,
            "exclude_forks": True,
            "deduplicate": True,
            "link_check_timeout": 5,
            "link_check_concurrency": 5,
        },
    }


@pytest.fixture
def sample_repos_by_category() -> dict[str, list[RepoInfo]]:
    """A sample repos_by_category mapping for testing the generator."""
    return {
        "cat_alpha": [
            make_repo("alpha-repo-1", stars=5_000),
            make_repo("alpha-repo-2", stars=2_000),
        ],
        "cat_beta": [
            make_repo("beta-repo-1", stars=800, language="TypeScript", category_id="cat_beta"),
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Mock GitHub repo object
# ─────────────────────────────────────────────────────────────────────────────


def make_gh_repo(
    name: str = "gh-repo",
    owner: str = "owner",
    stars: int = 1_000,
    forks: int = 20,
    description: str = "A GitHub repo",
    language: str | None = "Python",
    topics: list[str] | None = None,
    archived: bool = False,
    fork: bool = False,
) -> MagicMock:
    """Factory that creates a mock PyGitHub Repository object."""
    mock = MagicMock()
    mock.name = name
    mock.full_name = f"{owner}/{name}"
    mock.description = description
    mock.html_url = f"https://github.com/{owner}/{name}"
    mock.stargazers_count = stars
    mock.forks_count = forks
    mock.updated_at = datetime(2024, 6, 15, tzinfo=timezone.utc)
    mock.get_topics.return_value = topics or ["ai"]
    mock.language = language
    mock.archived = archived
    mock.fork = fork
    return mock
