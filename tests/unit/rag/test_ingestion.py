"""Unit tests for RAG chunking."""

from __future__ import annotations

from ai_team.rag.ingestion import chunk_by_markdown_sections, chunk_file


def test_chunk_markdown_sections_splits_on_headings() -> None:
    text = "# A\n\nintro\n\n## B\n\nbody\n"
    chunks = chunk_by_markdown_sections(text, "t.md", max_chars=500)
    assert len(chunks) >= 2
    assert any("intro" in c.text for c in chunks)


def test_chunk_file_md_uses_markdown() -> None:
    md = "# Title\n\nHello world.\n"
    chunks = chunk_file("x.md", md, max_chars=100)
    assert chunks and "Hello" in chunks[0].text


def test_chunk_file_py_windows() -> None:
    py = "def foo():\n    return 1\n"
    chunks = chunk_file("x.py", py, max_chars=50)
    assert chunks
