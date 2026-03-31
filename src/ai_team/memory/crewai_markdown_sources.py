"""
Optional CrewAI ``TextFileKnowledgeSource`` entries for static markdown under ``knowledge/``.

Use when constructing crews that support ``knowledge_sources=`` (CrewAI 1.x API).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_KNOWLEDGE_ROOT = Path(__file__).resolve().parent.parent / "knowledge"


def iter_markdown_knowledge_paths(root: Path | None = None) -> list[Path]:
    """Return sorted ``*.md`` paths under ``src/ai_team/knowledge`` (or ``root``)."""
    base = root if root is not None else _KNOWLEDGE_ROOT
    if not base.is_dir():
        return []
    return sorted(p for p in base.rglob("*.md") if p.is_file())


def build_text_file_knowledge_sources(
    root: Path | None = None,
) -> list[Any]:
    """
    Build CrewAI ``TextFileKnowledgeSource`` for each markdown file (best-effort).

    Returns an empty list if CrewAI knowledge API is unavailable.
    """
    try:
        from crewai.knowledge.source.text_file_knowledge_source import (
            TextFileKnowledgeSource,
        )
    except ImportError:
        logger.debug("crewai_text_file_knowledge_unavailable")
        return []
    out: list[Any] = []
    for path in iter_markdown_knowledge_paths(root):
        try:
            out.append(TextFileKnowledgeSource(file_path=str(path)))
        except Exception as e:
            logger.warning("crewai_knowledge_file_skip", path=str(path), error=str(e))
    return out
