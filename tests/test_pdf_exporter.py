"""
tests/test_pdf_exporter.py
==========================
Unit tests for curator/pdf_exporter.py markdown cleanup logic.
"""

from __future__ import annotations

from curator.pdf_exporter import _clean_for_pdf


def test_clean_for_pdf_converts_badge_markdown_to_html():
    md = '[![Build](https://img.shields.io/badge/build-passing-brightgreen)](https://example.com)'
    cleaned = _clean_for_pdf(md)

    assert '[![' not in cleaned
    assert '<a class="pdf-badge" href="https://example.com">Build</a>' in cleaned


def test_clean_for_pdf_merges_consecutive_badge_lines_inline():
    md = "\n".join(
        [
            '[![Build](https://img.shields.io/badge/build-passing-brightgreen)](https://example.com/build)',
            '[![License](https://img.shields.io/badge/license-MIT-blue)](https://example.com/license)',
        ],
    )
    cleaned = _clean_for_pdf(md)

    assert cleaned.count('<p class="pdf-badges">') == 1
    assert 'href="https://example.com/build">Build</a>' in cleaned
    assert 'href="https://example.com/license">License</a>' in cleaned


def test_clean_for_pdf_removes_div_wrappers_but_keeps_heading():
    md = "\n".join(
        [
            '<div align="center">',
            "# Awesome Curator",
            '[![Build](https://img.shields.io/badge/build-passing-brightgreen)](https://example.com/build)',
            "</div>",
        ],
    )
    cleaned = _clean_for_pdf(md)

    assert "<div" not in cleaned
    assert "</div>" not in cleaned
    assert "# Awesome Curator" in cleaned
    assert '<a class="pdf-badge" href="https://example.com/build">Build</a>' in cleaned
