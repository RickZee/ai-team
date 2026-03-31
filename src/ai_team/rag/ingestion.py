"""Chunking strategies for markdown and code files."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    """A chunk of text with optional section metadata."""

    text: str
    source_id: str
    section: str | None = None


def chunk_by_markdown_sections(text: str, source_id: str, max_chars: int) -> list[TextChunk]:
    """Split markdown on ``#`` / ``##`` headings; subdivide long sections by ``max_chars``."""
    lines = text.splitlines()
    chunks: list[TextChunk] = []
    current_title = "preamble"
    buf: list[str] = []

    def flush() -> None:
        nonlocal buf
        body = "\n".join(buf).strip()
        if not body:
            buf = []
            return
        if len(body) <= max_chars:
            chunks.append(TextChunk(text=body, source_id=source_id, section=current_title))
        else:
            for i in range(0, len(body), max_chars):
                part = body[i : i + max_chars]
                chunks.append(
                    TextChunk(
                        text=part,
                        source_id=source_id,
                        section=f"{current_title}_{i // max_chars}",
                    )
                )
        buf = []

    heading = re.compile(r"^(#{1,3})\s+(.+)$")
    for line in lines:
        m = heading.match(line)
        if m:
            flush()
            current_title = m.group(2).strip()
            buf.append(line)
        else:
            buf.append(line)
    flush()
    return chunks


def chunk_plain_text(text: str, source_id: str, max_chars: int) -> list[TextChunk]:
    """Fixed-size windows (e.g. for Python without markdown headings)."""
    t = text.strip()
    if not t:
        return []
    out: list[TextChunk] = []
    for i in range(0, len(t), max_chars):
        out.append(
            TextChunk(
                text=t[i : i + max_chars],
                source_id=source_id,
                section=f"window_{i // max_chars}",
            )
        )
    return out


def chunk_file(path: str, content: str, max_chars: int) -> list[TextChunk]:
    """Choose strategy from file extension."""
    p = path.lower()
    if p.endswith(".py"):
        return chunk_plain_text(content, path, max_chars)
    return chunk_by_markdown_sections(content, path, max_chars)
