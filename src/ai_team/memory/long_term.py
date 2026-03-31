"""
Long-term cross-session memory (Phase 6 optional extension point).

Production implementations may store successful patterns and architecture decisions
in ChromaDB, SQLite, or LangMem. The default :class:`NullLongTermMemory` is a no-op
so the pipeline runs without extra infrastructure.
"""

from __future__ import annotations

from typing import Any, Protocol

import structlog

logger = structlog.get_logger(__name__)


class LongTermMemoryStore(Protocol):
    """Protocol for durable, searchable memory across runs."""

    def add_pattern(
        self, project_id: str, label: str, content: str, metadata: dict[str, Any]
    ) -> None:
        """Persist a learned pattern or decision."""
        ...

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Retrieve similar entries for planning or development context."""
        ...


class NullLongTermMemory:
    """No-op store (default)."""

    def add_pattern(
        self,
        project_id: str,
        label: str,
        content: str,
        metadata: dict[str, Any],
    ) -> None:
        _ = (project_id, label, content, metadata)
        logger.debug("long_term_memory_skipped", reason="null_store")

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        _ = (query, limit)
        return []


class LongTermMemory:
    """Facade: swap ``_impl`` for a real store when wired."""

    def __init__(self, impl: LongTermMemoryStore | None = None) -> None:
        self._impl: LongTermMemoryStore = impl or NullLongTermMemory()

    def add_pattern(
        self,
        project_id: str,
        label: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._impl.add_pattern(
            project_id,
            label,
            content,
            metadata or {},
        )

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        return self._impl.search(query, limit=limit)


_singleton: LongTermMemory | None = None


def get_long_term_memory() -> LongTermMemory:
    """Process-wide singleton (tests may reset)."""
    global _singleton
    if _singleton is None:
        _singleton = LongTermMemory()
    return _singleton
