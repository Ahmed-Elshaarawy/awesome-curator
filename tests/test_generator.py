"""
tests/test_generator.py
=======================
Unit tests for curator/generator.py.

Tests cover the Jinja2 filter helpers and the full render pipeline.
No mocking needed — the generator is pure Markdown rendering.
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from curator.generator import (
    AwesomeListGenerator,
    _format_date,
    _stars_badge,
    _to_anchor,
)


# ─────────────────────────────────────────────────────────────────────────────
# Filter: _stars_badge
# ─────────────────────────────────────────────────────────────────────────────


def test_stars_badge_thousands():
    assert _stars_badge(1_500) == "1.5k ⭐"


def test_stars_badge_exact_thousand():
    assert _stars_badge(1_000) == "1.0k ⭐"


def test_stars_badge_hundreds():
    assert _stars_badge(750) == "750 ⭐"


def test_stars_badge_zero():
    assert _stars_badge(0) == "0 ⭐"


def test_stars_badge_large():
    assert _stars_badge(42_000) == "42.0k ⭐"


# ─────────────────────────────────────────────────────────────────────────────
# Filter: _format_date
# ─────────────────────────────────────────────────────────────────────────────


def test_format_date_standard():
    dt = datetime(2024, 3, 7, 12, 0, tzinfo=timezone.utc)
    assert _format_date(dt) == "2024-03-07"


def test_format_date_none():
    assert _format_date(None) == "unknown"


def test_format_date_single_digit_month_padded():
    dt = datetime(2024, 1, 5, tzinfo=timezone.utc)
    assert _format_date(dt) == "2024-01-05"


# ─────────────────────────────────────────────────────────────────────────────
# Filter: _to_anchor
# ─────────────────────────────────────────────────────────────────────────────


def test_to_anchor_basic():
    assert _to_anchor("Hello World") == "hello-world"


def test_to_anchor_strips_special_chars():
    # & is removed; the two surrounding spaces collapse to one hyphen via \s+
    assert _to_anchor("AI & LLM Tools") == "ai-llm-tools"


def test_to_anchor_multiple_spaces_become_one_hyphen():
    assert _to_anchor("foo   bar") == "foo-bar"


def test_to_anchor_already_lowercase():
    assert _to_anchor("python") == "python"


# ─────────────────────────────────────────────────────────────────────────────
# AwesomeListGenerator.generate
# ─────────────────────────────────────────────────────────────────────────────


def test_generate_contains_niche_name(sample_niche_config, sample_repos_by_category):
    gen = AwesomeListGenerator()
    output = gen.generate(sample_niche_config, sample_repos_by_category)
    assert "Test Niche" in output


def test_generate_contains_category_names(sample_niche_config, sample_repos_by_category):
    gen = AwesomeListGenerator()
    output = gen.generate(sample_niche_config, sample_repos_by_category)
    assert "Alpha Category" in output
    assert "Beta Category" in output


def test_generate_contains_repo_names(sample_niche_config, sample_repos_by_category):
    gen = AwesomeListGenerator()
    output = gen.generate(sample_niche_config, sample_repos_by_category)
    assert "alpha-repo-1" in output
    assert "beta-repo-1" in output


def test_generate_contains_star_badges(sample_niche_config, sample_repos_by_category):
    gen = AwesomeListGenerator()
    output = gen.generate(sample_niche_config, sample_repos_by_category)
    assert "5.0k ⭐" in output  # alpha-repo-1 has 5,000 stars


def test_generate_contains_repo_urls(sample_niche_config, sample_repos_by_category):
    gen = AwesomeListGenerator()
    output = gen.generate(sample_niche_config, sample_repos_by_category)
    assert "https://github.com/owner/alpha-repo-1" in output


def test_generate_with_dead_links_shows_section(sample_niche_config, sample_repos_by_category):
    gen = AwesomeListGenerator()
    dead = ["https://github.com/old/deleted-repo"]
    output = gen.generate(sample_niche_config, sample_repos_by_category, dead_links=dead)
    assert "deleted-repo" in output
    assert "Removed dead links" in output


def test_generate_no_dead_links_hides_section(sample_niche_config, sample_repos_by_category):
    gen = AwesomeListGenerator()
    output = gen.generate(sample_niche_config, sample_repos_by_category, dead_links=[])
    assert "Removed dead links" not in output


def test_generate_empty_category_shows_placeholder(sample_niche_config):
    gen = AwesomeListGenerator()
    repos_by_category = {
        "cat_alpha": [],
        "cat_beta": [],
    }
    output = gen.generate(sample_niche_config, repos_by_category)
    assert "No repositories found" in output


def test_generate_returns_string(sample_niche_config, sample_repos_by_category):
    gen = AwesomeListGenerator()
    output = gen.generate(sample_niche_config, sample_repos_by_category)
    assert isinstance(output, str)
    assert len(output) > 0


# ─────────────────────────────────────────────────────────────────────────────
# AwesomeListGenerator.write
# ─────────────────────────────────────────────────────────────────────────────


def test_write_creates_file(sample_niche_config, sample_repos_by_category):
    gen = AwesomeListGenerator()
    content = gen.generate(sample_niche_config, sample_repos_by_category)

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "AWESOME.md"
        gen.write(content, output_path)

        assert output_path.exists()
        written = output_path.read_text(encoding="utf-8")
        assert written == content


def test_write_creates_missing_parent_dirs(sample_niche_config, sample_repos_by_category):
    gen = AwesomeListGenerator()
    content = gen.generate(sample_niche_config, sample_repos_by_category)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Nested path that does not exist yet
        output_path = Path(tmpdir) / "deep" / "nested" / "AWESOME.md"
        gen.write(content, output_path)

        assert output_path.exists()
