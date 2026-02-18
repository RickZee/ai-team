"""Unit tests for get_crew_embedder_config (CrewAI embedder dict from MemorySettings)."""

from unittest.mock import MagicMock, patch

import pytest

from ai_team.memory.memory_config import get_crew_embedder_config


class TestGetCrewEmbedderConfig:
    """Structure of the returned embedder dict without touching Ollama."""

    def test_returns_ollama_provider_and_config(self) -> None:
        """Returned dict has provider=ollama and config with model_name and url."""
        mock_memory = MagicMock()
        mock_memory.embedding_model = "nomic-embed-text"
        mock_memory.ollama_base_url = "http://localhost:11434/"
        with patch("ai_team.config.settings.get_settings") as m:
            m.return_value.memory = mock_memory
            out = get_crew_embedder_config()
        assert out["provider"] == "ollama"
        assert "config" in out
        assert out["config"]["model_name"] == "nomic-embed-text"
        assert out["config"]["url"] == "http://localhost:11434"

    def test_strips_trailing_slash_from_base_url(self) -> None:
        """ollama_base_url is normalized to no trailing slash for CrewAI."""
        mock_memory = MagicMock()
        mock_memory.embedding_model = "custom-embed"
        mock_memory.ollama_base_url = "http://127.0.0.1:11434/"
        with patch("ai_team.config.settings.get_settings") as m:
            m.return_value.memory = mock_memory
            out = get_crew_embedder_config()
        assert out["config"]["url"] == "http://127.0.0.1:11434"
