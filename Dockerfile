# ─────────────────────────────────────────────────────────────────────────────
# awesome-curator Dockerfile
#
# Build:  docker build -t awesome-curator .
# Run:    docker run --rm -e GITHUB_TOKEN=ghp_... -v "$(pwd):/output" awesome-curator
# ─────────────────────────────────────────────────────────────────────────────

# Use a slim official Python image to keep the final image small
FROM python:3.11-slim

# Metadata
LABEL org.opencontainers.image.title="awesome-curator" \
      org.opencontainers.image.description="Automatically curate Awesome lists from GitHub" \
      org.opencontainers.image.licenses="MIT"

# Don't write .pyc files and don't buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# ── System dependencies for weasyprint (PDF export) ──────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf-xlib-2.0-0 \
        libffi-dev \
        shared-mime-info \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# ── Install Python dependencies ───────────────────────────────────────────────
# Copy the dependency spec AND README (hatchling reads it during build)
COPY pyproject.toml README.md ./

# Install runtime deps only (no pytest/ruff in the image)
# Non-editable install is correct for a container image
RUN pip install --no-cache-dir "."

# ── Copy source ───────────────────────────────────────────────────────────────
COPY curator/  ./curator/

# ── Output volume ─────────────────────────────────────────────────────────────
# Mount your host directory here to receive the generated AWESOME.md
VOLUME ["/output"]

# GITHUB_TOKEN is injected at runtime via -e or --env-file — never baked in.

# ── Entry point ───────────────────────────────────────────────────────────────
# Default: curate ai_llm niche and write to the mounted /output volume.
# Override any flag by appending arguments to `docker run`.
ENTRYPOINT ["python", "-m", "curator", "--output-dir", "/output"]
CMD ["--niche", "ai_llm"]
