"""
curator/generator.py
====================
Renders the curated repository data into a well-formatted Markdown
awesome list using Jinja2 templates.

Template location
-----------------
Templates live in the ``templates/`` directory at the project root
(one level above this package). The default template is
``templates/awesome_list.md.j2``.

Custom filters exposed to templates
------------------------------------
- ``stars_badge(n)``  → "1.5k ⭐" or "500 ⭐"
- ``format_date(dt)`` → "YYYY-MM-DD"
- ``to_anchor(text)`` → GitHub-compatible heading anchor slug
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)

# Resolve the templates/ directory inside the curator package
_TEMPLATES_DIR = Path(__file__).parent / "templates"


# ─────────────────────────────────────────────────────────────────────────────
# Jinja2 filter helpers
# ─────────────────────────────────────────────────────────────────────────────


def _stars_badge(stars: int) -> str:
    """Format a star count as a human-readable string with emoji."""
    if stars >= 1_000:
        return f"{stars / 1_000:.1f}k ⭐"
    return f"{stars} ⭐"


def _format_date(dt: Optional[datetime]) -> str:
    """Format a datetime as ISO date string (YYYY-MM-DD)."""
    if dt is None:
        return "unknown"
    return dt.strftime("%Y-%m-%d")


def _to_anchor(text: str) -> str:
    """
    Convert a heading string to a GitHub Markdown anchor slug.

    Rules (matches GitHub's algorithm):
    - Lowercase everything
    - Keep letters, digits, spaces, hyphens
    - Replace spaces with hyphens
    - Drop all other characters
    """
    lowered = text.lower()
    # Keep alphanumeric, spaces, hyphens
    cleaned = re.sub(r"[^\w\s-]", "", lowered)
    return re.sub(r"\s+", "-", cleaned.strip())


# ─────────────────────────────────────────────────────────────────────────────
# Generator
# ─────────────────────────────────────────────────────────────────────────────


class AwesomeListGenerator:
    """
    Renders the awesome list README from a Jinja2 template.

    Parameters
    ----------
    templates_dir:
        Directory containing Jinja2 template files.
        Defaults to ``<project_root>/templates/``.
    """

    def __init__(self, templates_dir: Optional[Path] = None) -> None:
        templates_path = templates_dir or _TEMPLATES_DIR
        self._env = Environment(
            loader=FileSystemLoader(str(templates_path)),
            autoescape=select_autoescape([]),  # Plain Markdown — no HTML escaping
            trim_blocks=True,    # Remove the newline after a block tag
            lstrip_blocks=True,  # Strip leading whitespace from block tags
            keep_trailing_newline=True,
        )
        # Register custom filters so templates can call them
        self._env.filters["stars_badge"] = _stars_badge
        self._env.filters["format_date"] = _format_date
        self._env.filters["to_anchor"] = _to_anchor

    # ── Public API ────────────────────────────────────────────────────────────

    def generate(
        self,
        niche_config: dict,
        repos_by_category: dict[str, list],
        dead_links: Optional[list[str]] = None,
        template_name: str = "awesome_list.md.j2",
    ) -> str:
        """
        Render the awesome list as a Markdown string.

        Parameters
        ----------
        niche_config:
            The niche's configuration block from config.yaml.
        repos_by_category:
            Mapping of ``category_id -> list[RepoInfo]``.
        dead_links:
            Optional list of URLs that were removed as dead. Passed to the
            template so it can optionally display a "removed links" section.
        template_name:
            Filename of the Jinja2 template to use.

        Returns
        -------
        str
            The fully rendered Markdown document.
        """
        template = self._env.get_template(template_name)

        # Build a category-id → category-meta lookup for easy template access
        categories_meta: dict[str, dict] = {
            cat["id"]: cat for cat in niche_config.get("categories", [])
        }

        total_repos = sum(len(repos) for repos in repos_by_category.values())

        context = {
            "niche": niche_config,
            "categories": categories_meta,
            "repos_by_category": repos_by_category,
            "dead_links": dead_links or [],
            "generated_at": datetime.now(timezone.utc),
            "total_repos": total_repos,
        }

        rendered = template.render(**context)
        logger.info(
            "Template rendered: %d categories, %d total repos.",
            len(repos_by_category),
            total_repos,
        )
        return rendered

    def write(self, content: str, output_path: Path) -> None:
        """
        Write the rendered Markdown to disk.

        Creates any missing parent directories automatically.

        Parameters
        ----------
        content:
            The Markdown string to write.
        output_path:
            Destination file path.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        logger.info("Awesome list written → %s", output_path.resolve())
