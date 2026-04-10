"""
curator/pdf_exporter.py
=======================
Converts the generated Markdown awesome list to a styled PDF.

Uses the `markdown` library to render Markdown → HTML, then
`weasyprint` to convert HTML → PDF with GitHub-inspired styling.

Usage (CLI):
    python -m curator --pdf
    python -m curator --pdf --pdf-output my_list.pdf

Usage (Python):
    from curator.pdf_exporter import md_to_pdf
    md_to_pdf(Path("AWESOME.md"))
"""

from __future__ import annotations

import logging
import re
from html import escape
from pathlib import Path
from typing import Optional

import markdown

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# PDF stylesheet — GitHub-inspired design
# ─────────────────────────────────────────────────────────────────────────────

_CSS = """
@page {
    margin: 2cm;
    size: A4;

    @bottom-center {
        content: "Page " counter(page) " of " counter(pages);
        font-size: 8pt;
        color: #6a737d;
    }
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    color: #24292e;
    line-height: 1.6;
    font-size: 10pt;
}

h1 {
    color: #0366d6;
    border-bottom: 2px solid #e1e4e8;
    padding-bottom: 0.4em;
    font-size: 20pt;
    page-break-after: avoid;
}

h2 {
    color: #24292e;
    border-bottom: 1px solid #e1e4e8;
    padding-bottom: 0.3em;
    font-size: 14pt;
    margin-top: 1.5em;
    page-break-after: avoid;
}

h3 {
    font-size: 11pt;
    margin-top: 1em;
    page-break-after: avoid;
}

/* ── Tables ── */
table {
    border-collapse: collapse;
    width: 100%;
    margin: 1em 0;
    font-size: 9pt;
    page-break-inside: avoid;
}

th {
    background-color: #0366d6;
    color: white;
    padding: 6px 10px;
    text-align: left;
    font-weight: 600;
}

td {
    padding: 5px 10px;
    border: 1px solid #e1e4e8;
    vertical-align: top;
}

tr:nth-child(even) td {
    background-color: #f6f8fa;
}

/* ── Code ── */
code {
    background-color: #f6f8fa;
    border: 1px solid #e1e4e8;
    padding: 1px 5px;
    border-radius: 3px;
    font-family: 'Courier New', 'Consolas', monospace;
    font-size: 0.88em;
}

pre {
    background-color: #f6f8fa;
    border: 1px solid #e1e4e8;
    padding: 1em;
    border-radius: 6px;
    font-size: 0.85em;
    overflow-x: auto;
    page-break-inside: avoid;
}

pre code {
    border: none;
    padding: 0;
    background: transparent;
}

/* ── Links ── */
a {
    color: #0366d6;
    text-decoration: none;
}

/* ── Blockquotes ── */
blockquote {
    border-left: 4px solid #0366d6;
    margin: 0.5em 0;
    padding: 0.3em 1em;
    color: #6a737d;
    font-style: italic;
    background: #f6f8fa;
    border-radius: 0 4px 4px 0;
}

/* ── Dividers ── */
hr {
    border: none;
    border-top: 1px solid #e1e4e8;
    margin: 1.5em 0;
}

/* ── Details/summary ── */
details {
    background: #f6f8fa;
    border: 1px solid #e1e4e8;
    border-radius: 6px;
    padding: 0.5em 1em;
    margin: 1em 0;
}

/* ── Utility ── */
sub, .footer-note {
    color: #6a737d;
    font-size: 8pt;
}

div[align="center"], p[align="center"] {
    text-align: center;
}

/* Badge images — keep them inline and small */
img {
    max-height: 22px;
    vertical-align: middle;
}

.pdf-badges {
    margin: 0.4em 0;
    text-align: center;
}

.pdf-badge {
    display: inline-block;
    margin: 0 0.25em 0.25em 0;
    padding: 0.2em 0.55em;
    border: 1px solid #d0d7de;
    border-radius: 999px;
    background: #f6f8fa;
    color: #24292e;
    font-size: 8pt;
    font-weight: 600;
}
"""


# ─────────────────────────────────────────────────────────────────────────────
# Markdown pre-processor for PDF
# ─────────────────────────────────────────────────────────────────────────────

def _clean_for_pdf(md_text: str) -> str:
    """
    Strip elements that don't render well in PDF:
    - Shield.io / badge image lines ([![...](url)](link)) — render as raw text in PDF
    - HTML <div> wrappers — markdown library skips Markdown inside HTML blocks

    Keeps all headings, tables, blockquotes, and body text intact.
    """
    badge_pattern = re.compile(r"\[!\[([^\]]*)\]\([^)]+\)\]\(([^)]+)\)")

    def badge_to_html(match: re.Match[str]) -> str:
        label = (match.group(1) or "badge").strip() or "badge"
        href = match.group(2).strip()
        return f'<a class="pdf-badge" href="{escape(href, quote=True)}">{escape(label)}</a>'

    # 1. Convert Markdown badge links to HTML before markdown parsing.
    # 2. Merge consecutive badge-only lines into one inline badge row.
    lines = md_text.splitlines()
    cleaned = []
    pending_badges: list[str] = []

    def flush_badges() -> None:
        if pending_badges:
            cleaned.append(f'<p class="pdf-badges">{" ".join(pending_badges)}</p>')
            pending_badges.clear()

    for line in lines:
        matches = list(badge_pattern.finditer(line))
        if matches:
            line_without_badges = badge_pattern.sub("", line).strip()
            if not line_without_badges:
                pending_badges.extend(badge_to_html(match) for match in matches)
                continue
            flush_badges()
            cleaned.append(badge_pattern.sub(badge_to_html, line))
            continue
        flush_badges()
        cleaned.append(line)
    flush_badges()

    # 3. Remove all <div ...> and </div> tags (keep content between them)
    result = re.sub(
        r"</?div[^>]*>",
        "",
        "\n".join(cleaned),
        flags=re.IGNORECASE,
    )

    # 4. Collapse 3+ consecutive blank lines into 2
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


def md_to_pdf(
    md_path: Path,
    pdf_path: Optional[Path] = None,
) -> Path:
    """
    Convert a Markdown file to a styled PDF document.

    Parameters
    ----------
    md_path:
        Path to the source ``.md`` file (e.g. ``AWESOME.md``).
    pdf_path:
        Destination path for the PDF. Defaults to the same directory
        and filename as *md_path* with a ``.pdf`` extension.

    Returns
    -------
    Path
        The path where the PDF was written.

    Raises
    ------
    FileNotFoundError
        If *md_path* does not exist.
    """
    if not md_path.exists():
        raise FileNotFoundError(f"Markdown source not found: {md_path}")

    out_path = pdf_path or md_path.with_suffix(".pdf")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Converting Markdown → PDF: %s → %s", md_path, out_path)

    md_text = md_path.read_text(encoding="utf-8")

    # Strip badges and bare HTML wrappers before converting
    md_text = _clean_for_pdf(md_text)

    _md_to_pdf_weasyprint(md_text, out_path, md_path.parent, md_path.stem)

    size_kb = out_path.stat().st_size / 1024
    logger.info("PDF written → %s (%.1f KB)", out_path.resolve(), size_kb)
    return out_path


def _md_to_pdf_weasyprint(md_text: str, out_path: Path, base_dir: Path, title: str) -> None:
    """Render cleaned markdown to PDF via markdown + weasyprint."""
    # Import lazily so markdown cleanup logic can be unit-tested
    # without requiring the full PDF backend in the test environment.
    from weasyprint import CSS, HTML

    # Render Markdown → HTML with GitHub-compatible extensions
    html_body = markdown.markdown(
        md_text,
        extensions=[
            "tables",       # GitHub-style | pipe | tables
            "fenced_code",  # ```fenced code blocks```
            "toc",          # [TOC] auto table of contents
            "nl2br",        # Preserve single newlines as <br>
            "sane_lists",   # Better nested list handling
            "attr_list",    # {: .class } attribute syntax
        ],
    )

    # Wrap in a minimal full HTML document
    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
</head>
<body>
{html_body}
</body>
</html>"""

    # base_url lets weasyprint resolve relative image paths
    HTML(string=html_doc, base_url=str(base_dir)).write_pdf(
        target=str(out_path),
        stylesheets=[CSS(string=_CSS)],
    )
