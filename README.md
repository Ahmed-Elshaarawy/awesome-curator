<div align="center">

# awesome-curator

**Automatically curate and update Awesome lists from GitHub trending repos.**

[![Python](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square&logo=python)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
[![Ruff](https://img.shields.io/badge/linter-ruff-purple?style=flat-square)](https://docs.astral.sh/ruff/)
[![Docker](https://img.shields.io/badge/Docker-ahmedelshaarawy2%2Fawesome--curator-2496ED?style=flat-square&logo=docker&logoColor=white)](https://hub.docker.com/r/ahmedelshaarawy2/awesome-curator)
[![Update Awesome List](https://github.com/Ahmed-Elshaarawy/awesome-curator/actions/workflows/update.yml/badge.svg)](https://github.com/Ahmed-Elshaarawy/awesome-curator/actions/workflows/update.yml)
[![Awesome](https://awesome.re/badge.svg)](https://awesome.re)

</div>

---

**awesome-curator** fetches trending GitHub repositories by topic, validates
every link asynchronously, and renders a clean Markdown awesome list,
updated daily via GitHub Actions with zero manual effort.

**Demo output** → [AWESOME.md](output/AWESOME.md) · [AWESOME.pdf](output/AWESOME.pdf)

---

## Supported Niches

| Niche key | Name | Categories |
|-----------|------|-----------|
| `ai_llm` | Awesome AI & LLM Tools | LLM Frameworks, AI Agents, Vector Databases, Fine-tuning, Evaluation, Deployment, RAG, Multimodal |
| `ml_tools` | Awesome Machine Learning Tools | ML Frameworks, MLOps, AutoML, Data Processing, Interpretability, Computer Vision, NLP, Time Series |

> New niches can be added by editing `curator/config.yaml` — no Python code needed.

---

## Features

- **Fully automated** — GitHub Actions runs daily, commits the updated list, and writes a job summary.
- **Topic-driven discovery** — configure topics per category in a single YAML file.
- **Async link validation** — dead links are removed before each publish using `aiohttp`.
- **PDF export** — convert the generated Markdown to a styled PDF with one flag (`--pdf`).
- **Jinja2 templates** — customise the output layout without touching Python code.
- **Multi-niche** — ships with AI/LLM and ML niches; add more by editing `config.yaml`.
- **Docker ready** — run with a single `docker compose` command, no Python install needed.
- **Rate-limit aware** — authenticated with `GITHUB_TOKEN` for 5,000 requests/hour; auto-sleeps on rate-limit hits.
- **Type-hinted, well-documented** — every module is fully annotated and documented.

---

## Project structure

```
awesome-curator/
├── curator/
│   ├── __init__.py
│   ├── __main__.py        # CLI entry point
│   ├── fetcher.py         # GitHub API → RepoInfo via PyGitHub
│   ├── checker.py         # Async dead-link detector via aiohttp
│   ├── generator.py       # Jinja2 Markdown renderer
│   ├── pdf_exporter.py    # Markdown → styled PDF via weasyprint
│   ├── config.yaml        # All niche/category/topic configuration
│   └── templates/
│       └── awesome_list.md.j2  # Jinja2 template for the output
├── tests/
│   ├── conftest.py
│   ├── test_fetcher.py
│   ├── test_checker.py
│   └── test_generator.py
├── .github/workflows/
│   └── update.yml         # Daily schedule + auto-commit workflow
├── Dockerfile             # Container image definition
├── docker-compose.yml     # Convenience services (curator, ml, pdf, ml-pdf)
├── output/                # All generated files land here
│   ├── AWESOME.md         # Generated Markdown list (auto-updated daily)
│   └── AWESOME.pdf        # Generated PDF export (auto-updated daily)
├── pyproject.toml
├── CONTRIBUTING.md
└── LICENSE
```

---

## Quick start

```bash
# 1. Clone
git clone https://github.com/Ahmed-Elshaarawy/awesome-curator.git
cd awesome-curator

# 2. Add your GitHub token
cp .env.example .env
# edit .env → GITHUB_TOKEN=ghp_...

# 3. Run — the image is pulled automatically from Docker Hub
docker compose run curator             # AI/LLM → output/AWESOME.md
docker compose run ml                  # ML     → output/AWESOME.md
docker compose run pdf                 # AI/LLM → output/AWESOME.md + AWESOME.pdf
docker compose run ml-pdf              # ML     → output/AWESOME.md + AWESOME.pdf
```

> **Tip:** append `--no-check` to skip link validation and run faster:
> `docker compose run pdf --no-check`

---

## CLI reference

```
python -m curator [OPTIONS]

  --niche KEY          Niche to curate: ai_llm (default) or ml_tools
  --no-check           Skip async link validation (faster)
  --dry-run            Print output to stdout, don't write files
  --pdf                Also export a styled PDF after generating Markdown
  --pdf-output PATH    Custom path for the PDF (default: output/AWESOME.pdf)
  --output-dir PATH    Override output directory (Docker uses /output)
  --config PATH        Path to a custom config.yaml
  --list-niches        List all configured niches and exit
```

**Examples:**

```bash
python -m curator                                        # AI/LLM → output/AWESOME.md
python -m curator --niche ml_tools                       # ML     → output/AWESOME.md
python -m curator --pdf --no-check                       # generate Markdown + PDF
python -m curator --dry-run --no-check                   # preview without writing
python -m curator --niche ai_llm --pdf --pdf-output report.pdf
```

---

## Configuration

All configuration lives in `curator/config.yaml`. No Python changes required.

```yaml
niches:
  ai_llm:                          # ← key used with --niche
    name: "Awesome AI & LLM Tools"
    tagline: "A curated list of awesome AI and LLM tools"
    description: "Full description here"
    categories:
      - id: llm_frameworks
        name: "LLM Frameworks & Libraries"
        description: "Core frameworks for building LLM applications"
        topics:             # GitHub topics to search
          - llm
          - langchain
        min_stars: 500      # Minimum stars to include a repo
        max_repos: 12       # Maximum repos per category
    settings:
      exclude_archived: true
      exclude_forks: true
      deduplicate: true           # Each repo appears in at most one category
      link_check_timeout: 10      # Seconds per link check
      link_check_concurrency: 20  # Max simultaneous checks

  ml_tools:                        # ← second niche, same structure
    name: "Awesome Machine Learning Tools"
    categories:
      - id: ml_frameworks
        name: "ML Frameworks & Libraries"
        topics:
          - machine-learning
          - pytorch
          - tensorflow
        min_stars: 1000
        max_repos: 12

output:
  directory: "output"              # All generated files go into output/
  filename: "AWESOME.md"
```

### Adding a new niche

1. Add a block under `niches` in `config.yaml`.
2. Preview: `python -m curator --niche your_key --dry-run --no-check`
3. Commit and push — GitHub Actions picks it up automatically.

See [CONTRIBUTING.md](CONTRIBUTING.md) for a full walkthrough.

---

## GitHub Actions — monitoring & triggering

The workflow runs at **06:00 UTC every day** automatically. Here's how to track it:

### See if it's running after a push

1. Go to your repo on GitHub
2. Click the **Actions** tab
3. You'll see a list of workflow runs — green ✅ means success, yellow 🟡 means running, red ❌ means failed

The green/red badge at the top of this README also reflects the last run status in real time.

### Trigger it manually (without waiting for 6 AM)

1. Go to **Actions → Update Awesome List**
2. Click **Run workflow** (top right)
3. Choose a niche key (`ai_llm` or `ml_tools`) and click **Run workflow**
4. Refresh the page — you'll see it appear as a yellow 🟡 running job

### Get email notifications on failure

1. Go to **GitHub → Settings → Notifications**
2. Under **Actions** → enable **"Send notifications for failed workflows only"**
3. You'll get an email if a daily run fails

### Read the job summary after a run

Click any completed run → click the **curate** job → scroll to the bottom to see the full summary table (repos per category, dead links removed, output file path).

---

## Running tests

```bash
pytest                    # Full suite with coverage report
pytest --no-cov -v        # Verbose, no coverage overhead
```

Tests mock all external calls (GitHub API, HTTP) — no token required.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for:
- How to add a new niche (pure YAML, no Python needed)
- Development setup and code style (Ruff)
- PR checklist

---

## License

[MIT](LICENSE) — auto-generated content retains each repository's own license.
