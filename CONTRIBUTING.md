# Contributing to awesome-curator

Thank you for considering a contribution! This document covers everything
you need to know to get started.

---

## Table of Contents

1. [Adding a new niche](#adding-a-new-niche)
2. [Adding repositories to an existing category](#adding-repositories-to-an-existing-category)
3. [Development setup](#development-setup)
4. [Running tests](#running-tests)
5. [Code style](#code-style)
6. [Submitting a pull request](#submitting-a-pull-request)

---

## Adding a new niche

Awesome-curator is designed to be extended with zero Python code — just edit
`curator/config.yaml`.

1. Open `curator/config.yaml`.
2. Add a new block under the top-level `niches` key:

```yaml
niches:
  # … existing niches …

  devops_tools:                          # ← your new niche key (snake_case)
    name: "Awesome DevOps Tools"
    tagline: "A curated list of awesome DevOps tools and platforms"
    description: |
      A curated collection of DevOps tools …

    categories:
      - id: ci_cd
        name: "CI/CD Pipelines"
        description: "Tools for continuous integration and deployment"
        topics:
          - ci-cd
          - continuous-integration
          - github-actions
        min_stars: 500
        max_repos: 10

    settings:
      exclude_archived: true
      exclude_forks: true
      deduplicate: true
      link_check_timeout: 10
      link_check_concurrency: 20
```

3. Run a dry-run to preview the output:

```bash
python -m curator --niche devops_tools --dry-run
```

4. Open a pull request with your new config block and a short description
   of why this niche is valuable.

---

## Adding repositories to an existing category

If you want a specific repository to reliably appear in a category, add its
primary GitHub topic to that category's `topics` list in `config.yaml`. The
curator always fetches the top repos by stars for each topic.

---

## Development setup

```bash
# 1. Clone the repo
git clone https://github.com/Ahmed-Elshaarawy/awesome-curator.git
cd awesome-curator

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install the package in editable mode with dev extras
pip install -e ".[dev]"

# 4. Copy the example env file and add your GitHub token
cp .env.example .env
# Edit .env and set GITHUB_TOKEN=ghp_…
```

---

## Running tests

```bash
# Run the full test suite with coverage
pytest

# Run a specific test file
pytest tests/test_generator.py -v

# Skip the coverage report for a quick run
pytest --no-cov
```

Tests use `unittest.mock` for GitHub API calls and `aioresponses` for HTTP
calls — no real network requests are made.

---

## Code style

This project uses [Ruff](https://docs.astral.sh/ruff/) for linting and
formatting.

```bash
# Check for style issues
ruff check .

# Auto-fix fixable issues
ruff check . --fix

# Format code
ruff format .
```

Key conventions:
- All public functions and classes must have docstrings.
- Use type hints throughout.
- Keep lines under 100 characters.
- No hardcoded tokens or secrets anywhere in the codebase.

---

## Submitting a pull request

1. Fork the repository and create a branch: `git checkout -b feat/my-feature`.
2. Make your changes, add/update tests as needed.
3. Ensure `pytest` passes with no failures.
4. Ensure `ruff check .` reports no issues.
5. Open a pull request describing **what** you changed and **why**.

We review PRs promptly. Thank you for improving awesome-curator! 🚀
