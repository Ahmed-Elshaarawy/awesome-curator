"""
curator/__main__.py
===================
CLI entry point for awesome-curator.

Usage
-----
    python -m curator                          # curate the default niche (ai_llm)
    python -m curator --niche ai_llm           # explicit niche key
    python -m curator --no-check               # skip async link validation
    python -m curator --dry-run               # print output to stdout, don't write file
    python -m curator --list-niches            # show available niches and exit
    awesome-curator --help                     # if installed via pyproject.toml scripts

Pipeline
--------
1. Load config.yaml
2. Fetch repos from GitHub via PyGitHub (fetcher.py)
3. Validate all URLs asynchronously (checker.py)
4. Render Markdown via Jinja2 (generator.py)
5. Write output file and emit a job summary (for GitHub Actions)
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Optional

import yaml

from .checker import LinkChecker
from .fetcher import GitHubFetcher
from .generator import AwesomeListGenerator

# ── Logging setup ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("curator")

# Default config path is the config.yaml inside this package
_DEFAULT_CONFIG = Path(__file__).parent / "config.yaml"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def load_config(path: Path = _DEFAULT_CONFIG) -> dict:
    """Load and minimally validate the YAML configuration."""
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    if not isinstance(cfg, dict) or "niches" not in cfg:
        raise ValueError(f"'{path}' must contain a top-level 'niches' mapping.")
    return cfg


def _build_job_summary(
    niche_name: str,
    repos_by_category: dict[str, list],
    dead_count: int,
    output_path: Path,
) -> str:
    """
    Build a Markdown summary string for GitHub Actions job summaries
    (GITHUB_STEP_SUMMARY) or plain console output.
    """
    total = sum(len(v) for v in repos_by_category.values())
    lines = [
        "# Awesome-Curator — Update Summary",
        "",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| **Niche** | {niche_name} |",
        f"| **Total repos** | {total} |",
        f"| **Dead links removed** | {dead_count} |",
        f"| **Output file** | `{output_path}` |",
        "",
        "## Category breakdown",
        "",
    ]
    for cat_id, repos in repos_by_category.items():
        lines.append(f"- `{cat_id}`: **{len(repos)}** repo(s)")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Core pipeline
# ─────────────────────────────────────────────────────────────────────────────


def run(
    niche_key: str,
    config: dict,
    *,
    skip_link_check: bool = False,
    dry_run: bool = False,
    output_dir_override: Optional[str] = None,
    export_pdf: bool = False,
    pdf_output: Optional[str] = None,
) -> None:
    """
    Execute the full curator pipeline for one niche.

    Parameters
    ----------
    niche_key:
        Key into ``config["niches"]``.
    config:
        Full parsed configuration dict.
    skip_link_check:
        When *True*, the async link validation step is skipped.
    dry_run:
        When *True*, the rendered Markdown is printed to stdout and
        **not** written to disk.
    output_dir_override:
        When set, overrides the output directory from config.yaml.
        Useful for Docker volume mounts (e.g. ``/output``).
    export_pdf:
        When *True*, convert the generated Markdown to PDF after writing.
    pdf_output:
        Custom PDF output path. Defaults to same name as the Markdown
        file with a ``.pdf`` extension.
    """
    niche = config["niches"].get(niche_key)
    if niche is None:
        available = ", ".join(config["niches"])
        raise ValueError(f"Niche '{niche_key}' not found. Available: {available}")

    # Resolve output path — CLI flag takes priority over config.yaml
    out_cfg = config.get("output", {})
    out_dir = Path(output_dir_override) if output_dir_override else Path(out_cfg.get("directory", "."))
    output_path = out_dir / out_cfg.get("filename", "AWESOME.md")

    # ── Step 1: Fetch ─────────────────────────────────────────────────────────
    logger.info("=== Step 1 / 3 : Fetching repositories ===")
    fetcher = GitHubFetcher()  # reads GITHUB_TOKEN from env
    repos_by_category = fetcher.fetch_niche(niche)

    total_fetched = sum(len(v) for v in repos_by_category.values())
    logger.info("Fetched %d repo(s) across %d category(ies).", total_fetched, len(repos_by_category))

    # ── Step 2: Validate links ────────────────────────────────────────────────
    dead_urls: list[str] = []

    if not skip_link_check:
        logger.info("=== Step 2 / 3 : Validating links ===")
        settings = niche.get("settings", {})
        checker = LinkChecker(
            timeout=settings.get("link_check_timeout", 10),
            concurrency=settings.get("link_check_concurrency", 20),
        )

        all_urls = [repo.url for repos in repos_by_category.values() for repo in repos]
        check_results = checker.run_check(all_urls)

        cleaned: dict[str, list] = {}
        for cat_id, repos in repos_by_category.items():
            alive, dead = LinkChecker.filter_alive(repos, check_results)
            cleaned[cat_id] = alive
            dead_urls.extend(repo.url for repo in dead)
        repos_by_category = cleaned
        logger.info("Link check complete. %d dead link(s) removed.", len(dead_urls))
    else:
        logger.info("=== Step 2 / 3 : Link check skipped (--no-check) ===")

    # ── Step 3: Generate ──────────────────────────────────────────────────────
    logger.info("=== Step 3 / 3 : Generating awesome list ===")
    generator = AwesomeListGenerator()
    content = generator.generate(
        niche_config=niche,
        repos_by_category=repos_by_category,
        dead_links=dead_urls,
    )

    if dry_run:
        print(content)
        logger.info("Dry-run mode — output not written to disk.")
    else:
        generator.write(content, output_path)

        # ── Step 4: Export PDF (optional) ─────────────────────────────────────
        if export_pdf:
            from .pdf_exporter import md_to_pdf
            pdf_dest = Path(pdf_output) if pdf_output else None
            md_to_pdf(output_path, pdf_dest)

    # ── Job summary ───────────────────────────────────────────────────────────
    summary = _build_job_summary(niche["name"], repos_by_category, len(dead_urls), output_path)
    logger.info("\n%s", summary)

    # Write to GitHub Actions step summary if the env var is present
    step_summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary_path:
        Path(step_summary_path).write_text(summary + "\n", encoding="utf-8")
        logger.info("Job summary written to GITHUB_STEP_SUMMARY.")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    """Parse CLI arguments and execute the curator pipeline."""
    parser = argparse.ArgumentParser(
        prog="awesome-curator",
        description="Automatically curate and update an Awesome list from GitHub.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  awesome-curator                    # curate ai_llm (default)\n"
            "  awesome-curator --niche ai_llm     # explicit niche\n"
            "  awesome-curator --no-check         # skip link validation\n"
            "  awesome-curator --dry-run          # preview without writing\n"
            "  awesome-curator --list-niches      # show available niches\n"
            "  awesome-curator --pdf              # also export AWESOME.pdf\n"
        ),
    )
    parser.add_argument(
        "--niche",
        default="ai_llm",
        metavar="KEY",
        help="Niche key from config.yaml to curate (default: ai_llm).",
    )
    parser.add_argument(
        "--config",
        default=str(_DEFAULT_CONFIG),
        metavar="PATH",
        help="Path to the YAML configuration file.",
    )
    parser.add_argument(
        "--no-check",
        action="store_true",
        help="Skip asynchronous link validation.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the generated Markdown to stdout; do not write to disk.",
    )
    parser.add_argument(
        "--list-niches",
        action="store_true",
        help="List all configured niches and exit.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        metavar="PATH",
        help=(
            "Override the output directory from config.yaml. "
            "Use this with Docker to write files to a mounted volume, e.g. /output."
        ),
    )
    parser.add_argument(
        "--pdf",
        action="store_true",
        help="Convert the generated AWESOME.md to a styled PDF after writing.",
    )
    parser.add_argument(
        "--pdf-output",
        default=None,
        metavar="PATH",
        help="Custom path for the PDF file (default: same as AWESOME.md with .pdf extension).",
    )
    args = parser.parse_args()

    try:
        config = load_config(Path(args.config))
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Configuration error: %s", exc)
        sys.exit(1)

    if args.list_niches:
        print("Available niches:")
        for key, niche in config["niches"].items():
            print(f"  {key:20s}  {niche.get('name', '')}")
        sys.exit(0)

    try:
        run(
            niche_key=args.niche,
            config=config,
            skip_link_check=args.no_check,
            dry_run=args.dry_run,
            output_dir_override=args.output_dir,
            export_pdf=args.pdf,
            pdf_output=args.pdf_output,
        )
    except EnvironmentError as exc:
        # Missing GITHUB_TOKEN — give a clear, actionable message
        logger.error("%s", exc)
        sys.exit(1)
    except ValueError as exc:
        logger.error("Invalid argument: %s", exc)
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
        sys.exit(130)


if __name__ == "__main__":
    main()
