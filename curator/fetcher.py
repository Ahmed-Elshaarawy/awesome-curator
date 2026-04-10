"""
curator/fetcher.py
==================
Fetches trending GitHub repositories using PyGitHub.

Searches the GitHub API by topic, applies configurable filters
(min stars, archived, forks), deduplicates across categories, and
returns typed RepoInfo dataclasses ready for the generator.

Authentication
--------------
Reads GITHUB_TOKEN from the environment (set via .env locally or
secrets.GITHUB_TOKEN in GitHub Actions). Authenticated requests
receive 5,000 API calls/hour; unauthenticated calls get only 60/hour.
"""

from __future__ import annotations

import itertools
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from github import Github, GithubException, RateLimitExceededException
from github.Repository import Repository as GHRepo

# Load .env if present (no-op in CI where the var is already in the environment)
load_dotenv()

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class RepoInfo:
    """Structured, serialisable representation of a GitHub repository."""

    name: str
    full_name: str          # "owner/repo"
    description: str
    url: str                # HTML URL for the repo
    stars: int
    forks: int
    last_updated: datetime
    topics: list[str]
    language: Optional[str]
    category_id: str        # Which config category this repo belongs to


# ─────────────────────────────────────────────────────────────────────────────
# Fetcher
# ─────────────────────────────────────────────────────────────────────────────


class GitHubFetcher:
    """
    Fetches trending repositories from GitHub for a configured niche.

    Parameters
    ----------
    token:
        GitHub Personal Access Token. If *None*, falls back to the
        ``GITHUB_TOKEN`` environment variable.

    Raises
    ------
    EnvironmentError
        When no token is found in either the argument or the environment.
    """

    def __init__(self, token: Optional[str] = None) -> None:
        resolved = token or os.getenv("GITHUB_TOKEN")
        if not resolved:
            raise EnvironmentError(
                "GITHUB_TOKEN is not set. "
                "Copy .env.example to .env and add your Personal Access Token, "
                "or set the GITHUB_TOKEN environment variable."
            )
        self._github = Github(resolved)
        logger.info("GitHub client initialised (authenticated).")

    # ── Public API ────────────────────────────────────────────────────────────

    def fetch_niche(self, niche_config: dict) -> dict[str, list[RepoInfo]]:
        """
        Fetch all repositories for a niche, organised by category.

        Iterates over each category defined in *niche_config["categories"]*,
        searches GitHub by the category's topics, and deduplicates repos that
        appear in multiple categories (keeping the first occurrence by config
        order).

        Parameters
        ----------
        niche_config:
            The niche's config block as loaded from config.yaml.

        Returns
        -------
        dict[str, list[RepoInfo]]
            Mapping of ``category_id -> list[RepoInfo]``, sorted by stars desc.
        """
        settings: dict = niche_config.get("settings", {})
        results: dict[str, list[RepoInfo]] = {}
        seen_full_names: set[str] = set()  # for cross-category deduplication

        for category in niche_config.get("categories", []):
            cat_id: str = category["id"]
            logger.info("Fetching category: '%s' …", category["name"])

            repos = self._fetch_category(
                category=category,
                exclude_archived=settings.get("exclude_archived", True),
                exclude_forks=settings.get("exclude_forks", True),
                deduplicate=settings.get("deduplicate", True),
                seen_full_names=seen_full_names,
            )
            results[cat_id] = repos
            logger.info("  → %d repo(s) collected for '%s'.", len(repos), category["name"])

        return results

    def get_rate_limit_status(self) -> dict:
        """Return current API rate-limit stats (useful for diagnostics)."""
        rl = self._github.get_rate_limit()
        return {
            "core": {
                "remaining": rl.core.remaining,
                "limit": rl.core.limit,
                "reset_utc": rl.core.reset.isoformat(),
            },
            "search": {
                "remaining": rl.search.remaining,
                "limit": rl.search.limit,
                "reset_utc": rl.search.reset.isoformat(),
            },
        }

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _fetch_category(
        self,
        category: dict,
        *,
        exclude_archived: bool,
        exclude_forks: bool,
        deduplicate: bool,
        seen_full_names: set[str],
    ) -> list[RepoInfo]:
        """
        Search GitHub for each topic in a category and collect unique repos.

        Stops collecting topics early once we have 2× the target count so
        that we always have enough candidates after filtering.
        """
        min_stars: int = category.get("min_stars", 100)
        max_repos: int = category.get("max_repos", 10)
        topics: list[str] = category.get("topics", [])
        cat_id: str = category["id"]

        # Use a dict keyed by full_name so each repo appears at most once
        candidates: dict[str, RepoInfo] = {}

        for topic in topics:
            if len(candidates) >= max_repos * 3:
                break  # Enough candidates; avoid unnecessary API calls

            query = f"topic:{topic} stars:>={min_stars}"
            try:
                search_results = self._github.search_repositories(
                    query=query,
                    sort="stars",
                    order="desc",
                )
                # islice fetches pages lazily and handles fewer-than-max results safely
                for gh_repo in itertools.islice(search_results, max_repos):
                    if gh_repo.full_name in candidates:
                        continue
                    if deduplicate and gh_repo.full_name in seen_full_names:
                        continue
                    if exclude_archived and gh_repo.archived:
                        continue
                    if exclude_forks and gh_repo.fork:
                        continue

                    candidates[gh_repo.full_name] = self._to_repo_info(gh_repo, cat_id)

            except RateLimitExceededException:
                self._wait_for_rate_limit_reset()

            except GithubException as exc:
                logger.error("GitHub API error searching topic '%s': %s", topic, exc)
                # Continue to next topic rather than crashing the whole run

        # Sort by stars descending, cap at max_repos
        sorted_repos = sorted(
            candidates.values(), key=lambda r: r.stars, reverse=True
        )[:max_repos]

        # Register in the global seen set so other categories skip these repos
        for repo in sorted_repos:
            seen_full_names.add(repo.full_name)

        return sorted_repos

    def _wait_for_rate_limit_reset(self) -> None:
        """Sleep until the search rate limit resets, then resume."""
        try:
            reset_time = self._github.get_rate_limit().search.reset
            wait_secs = max(0, (reset_time - datetime.now(timezone.utc)).total_seconds()) + 5
        except GithubException:
            wait_secs = 60  # Fallback if we can't even check the rate limit

        logger.warning(
            "Search rate limit exceeded. Sleeping for %.0f seconds …", wait_secs
        )
        time.sleep(wait_secs)

    @staticmethod
    def _to_repo_info(gh_repo: GHRepo, category_id: str) -> RepoInfo:
        """
        Convert a PyGitHub Repository object into a RepoInfo dataclass.

        Truncates overly long descriptions and replaces missing ones with
        a sensible placeholder so the template never receives ``None``.
        """
        raw_desc: str = (gh_repo.description or "").strip()
        max_len = 200
        if len(raw_desc) > max_len:
            raw_desc = raw_desc[:max_len].rstrip() + "…"

        return RepoInfo(
            name=gh_repo.name,
            full_name=gh_repo.full_name,
            description=raw_desc or "No description provided.",
            url=gh_repo.html_url,
            stars=gh_repo.stargazers_count,
            forks=gh_repo.forks_count,
            last_updated=gh_repo.updated_at,
            topics=list(gh_repo.get_topics()),
            language=gh_repo.language,
            category_id=category_id,
        )
