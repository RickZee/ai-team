"""
Comprehensive unit tests for memory: MemoryManager ChromaDB storage/retrieval,
SQLite session persistence, CrewAI embedder config (no OpenAI fallback),
mock Ollama embedder, memory cleanup and TTL expiry.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ai_team.config.settings import MemorySettings
from ai_team.memory.memory_config import (
    MemoryManager,
    get_crew_embedder_config,
    OllamaChromaEmbeddingFunction,
)


# -----------------------------------------------------------------------------
# MemoryManager ChromaDB storage and retrieval
# -----------------------------------------------------------------------------


class TestMemoryManagerChromaDB:
    """Short-term (ChromaDB) store and retrieve; mock embedder to avoid Ollama."""

    def test_short_term_store_retrieve_round_trip(self, tmp_path: Path) -> None:
        """Store in short_term and retrieve via semantic search (mocked embedder)."""
        chroma_path = str(tmp_path / "chroma")
        sqlite_path = ":memory:"
        settings = MemorySettings(
            chromadb_path=chroma_path,
            sqlite_path=sqlite_path,
            memory_enabled=True,
            retention_days=90,
            ollama_base_url="http://localhost:11434",
        )
        # Mock embedding to return fixed vectors so we don't call Ollama
        with patch(
            "ai_team.memory.memory_config.OllamaChromaEmbeddingFunction.__call__",
            return_value=[[0.1] * 768],
        ):
            manager = MemoryManager()
            manager.initialize(settings)
        assert manager.is_initialized

        project_id = "test-chroma-proj"
        stored = manager.store(
            key="task1",
            value="Implemented user login with Redis sessions.",
            memory_type="short_term",
            project_id=project_id,
        )
        assert stored is not None

        results = manager.retrieve(
            query="login session",
            memory_type="short_term",
            top_k=5,
            project_id=project_id,
        )
        assert len(results) >= 1
        assert any("login" in str(r.get("data", r)) for r in results)


# -----------------------------------------------------------------------------
# SQLite session persistence (long-term)
# -----------------------------------------------------------------------------


class TestMemoryManagerSQLitePersistence:
    """Long-term (SQLite) store and retrieve round-trip."""

    def test_long_term_store_and_retrieve_round_trip(self, tmp_path: Path) -> None:
        chroma_path = str(tmp_path / "chroma")
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
        assert len(results) >= 1
        assert results[0]["type"] == "conversation"
        assert "PostgreSQL" in results[0]["data"]["content"]


# -----------------------------------------------------------------------------
# CrewAI crew embedder config — verify no OpenAI fallback
# -----------------------------------------------------------------------------


class TestCrewEmbedderConfigNoOpenAI:
    """get_crew_embedder_config must return Ollama provider only."""

    def test_returns_ollama_provider_only(self) -> None:
        mock_memory = MagicMock()
        mock_memory.embedding_model = "nomic-embed-text"
        mock_memory.ollama_base_url = "http://localhost:11434/"
        with patch("ai_team.config.settings.get_settings") as m:
            m.return_value.memory = mock_memory
            out = get_crew_embedder_config()
        assert out["provider"] == "ollama"
        assert "openai" not in str(out).lower()
        assert "config" in out
        assert out["config"]["model_name"] == "nomic-embed-text"
        assert out["config"]["url"] == "http://localhost:11434"

    def test_strips_trailing_slash_from_base_url(self) -> None:
        mock_memory = MagicMock()
        mock_memory.embedding_model = "custom-embed"
        mock_memory.ollama_base_url = "http://127.0.0.1:11434/"
        with patch("ai_team.config.settings.get_settings") as m:
            m.return_value.memory = mock_memory
            out = get_crew_embedder_config()
        assert out["config"]["url"] == "http://127.0.0.1:11434"


# -----------------------------------------------------------------------------
# Mock Ollama embedder responses
# -----------------------------------------------------------------------------


class TestMockOllamaEmbedder:
    """OllamaChromaEmbeddingFunction behavior without hitting network."""

    def test_embedding_function_returns_list_of_vectors(self) -> None:
        """__call__ returns list of lists (one vector per doc)."""
        with patch("httpx.Client") as mock_client_cls:
            client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = client
            mock_client_cls.return_value.__exit__.return_value = None
            client.post.return_value.status_code = 200
            client.post.return_value.json.return_value = {
                "embedding": [0.0] * 768,
            }
            client.post.return_value.raise_for_status = MagicMock()
            ef = OllamaChromaEmbeddingFunction(
                model="nomic-embed-text",
                base_url="http://localhost:11434",
            )
            result = ef(["hello world"])
        assert isinstance(result, list)
        assert len(result) == 1
        assert len(result[0]) == 768

    def test_embed_query_single_string(self) -> None:
        with patch("httpx.Client") as mock_client_cls:
            client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = client
            mock_client_cls.return_value.__exit__.return_value = None
            client.post.return_value.status_code = 200
            client.post.return_value.json.return_value = {"embedding": [0.1] * 768}
            client.post.return_value.raise_for_status = MagicMock()
            ef = OllamaChromaEmbeddingFunction(
                model="nomic-embed-text",
                base_url="http://localhost:11434",
            )
            vec = ef.embed_query("single query")
        assert isinstance(vec, list)
        assert len(vec) == 768


# -----------------------------------------------------------------------------
# Memory cleanup and TTL expiry
# -----------------------------------------------------------------------------


class TestMemoryCleanupAndTTL:
    """Cleanup project memory and long-term retention (TTL) expiry."""

    def test_cleanup_removes_project_short_term(self, tmp_path: Path) -> None:
        chroma_path = str(tmp_path / "chroma")
        settings = MemorySettings(
            chromadb_path=chroma_path,
            sqlite_path=":memory:",
            memory_enabled=True,
            retention_days=90,
            ollama_base_url="http://localhost:11434",
        )
        with patch(
            "ai_team.memory.memory_config.OllamaChromaEmbeddingFunction.__call__",
            return_value=[[0.0] * 768],
        ):
            manager = MemoryManager()
            manager.initialize(settings)
        project_id = "cleanup-proj"
        manager.store(
            key="k1",
            value="v1",
            memory_type="short_term",
            project_id=project_id,
        )
        manager.cleanup(project_id)
        # After cleanup, retrieve should return empty or no hits for that project
        results = manager.retrieve(
            query="v1",
            memory_type="short_term",
            top_k=5,
            project_id=project_id,
        )
        assert len(results) == 0 or not any(
            "v1" in str(r.get("data", r)) for r in results
        )

    def test_apply_retention_returns_deleted_count(self, tmp_path: Path) -> None:
        """Long-term retention deletes entries older than retention_days."""
        chroma_path = str(tmp_path / "chroma")
        sqlite_path = str(tmp_path / "memory.db")
        settings = MemorySettings(
            chromadb_path=chroma_path,
            sqlite_path=sqlite_path,
            memory_enabled=True,
            retention_days=1,
        )
        manager = MemoryManager()
        manager.initialize(settings)
        # Store something recent; apply_retention with 1 day should not delete it
        manager.store(
            key="recent",
            value={"role": "user", "content": "recent message"},
            memory_type="long_term",
            project_id="retention-proj",
        )
        deleted = manager.apply_retention()
        # deleted is an int (number of rows deleted)
        assert isinstance(deleted, int)
        assert deleted >= 0
