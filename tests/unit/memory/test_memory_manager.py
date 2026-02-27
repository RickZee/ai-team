"""Unit tests for MemoryManager (long-term store round-trip; no embedder)."""

from pathlib import Path

import pytest

from ai_team.config.settings import MemorySettings
from ai_team.memory.memory_config import MemoryManager


class TestMemoryManagerLongTerm:
    """Long-term (SQLite) store/retrieve round-trip without embedding network."""

    def test_long_term_store_and_retrieve_round_trip(self, tmp_path: Path) -> None:
        """Store a conversation in long_term and retrieve it via MemoryManager."""
        chroma_path = str(tmp_path / "chroma")
        # Use :memory: so long_term store and retrieve share one connection (avoids file commit timing)
        sqlite_path = ":memory:"
        settings = MemorySettings(
            chromadb_path=chroma_path,
            sqlite_path=sqlite_path,
            memory_enabled=True,
            retention_days=90,
        )
        manager = MemoryManager()
        manager.initialize(settings)
        assert manager.is_initialized

        project_id = "test-proj"
        stored = manager.store(
            key="conv1",
            value={"role": "user", "content": "We use PostgreSQL for the user database."},
            memory_type="long_term",
            project_id=project_id,
        )
        assert stored is not None

        results = manager.retrieve(
            query="database",
            memory_type="long_term",
            top_k=5,
            project_id=project_id,
        )
        assert len(results) >= 1, "expected at least one long_term conversation after store"
        assert results[0]["type"] == "conversation"
        assert "PostgreSQL" in results[0]["data"]["content"]
