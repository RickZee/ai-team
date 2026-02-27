"""Unit tests for get_crew_embedder_config (delegates to llm_factory OpenRouter embedder)."""

from unittest.mock import patch

import pytest

from ai_team.memory.memory_config import get_crew_embedder_config


class TestGetCrewEmbedderConfig:
    """Structure of the returned embedder dict (OpenRouter-backed)."""

    def test_returns_openai_provider_and_config(self) -> None:
        """Returned dict has provider=openai and config with model_name (OpenRouter)."""
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}, clear=False):
            out = get_crew_embedder_config()
        assert out["provider"] == "openai"
        assert "config" in out
        assert "model_name" in out["config"]
        assert "openrouter" in out["config"]["model_name"].lower()

    def test_embedder_config_structure(self) -> None:
        """Config has expected keys for CrewAI embedder."""
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "key"}, clear=False):
            out = get_crew_embedder_config()
        assert "provider" in out
        assert "config" in out
        assert "model_name" in out["config"]
