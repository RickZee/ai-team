"""Unit tests for ``llm_factory`` (embedder config, LLM construction)."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from ai_team.config.llm_factory import create_llm_for_role, get_embedder_config
from ai_team.config.models import OpenRouterSettings


class TestGetEmbedderConfig:
    def test_returns_openai_provider_shape(self) -> None:
        cfg = get_embedder_config()
        assert cfg["provider"] == "openai"
        assert "config" in cfg
        assert "model_name" in cfg["config"]

    def test_sets_openai_env_when_key_present(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENROUTER_API_KEY", "k")
        monkeypatch.setenv("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1")
        get_embedder_config()
        assert os.environ.get("OPENAI_API_KEY") == "k"


class TestCreateLlmForRole:
    def test_creates_llm_instance(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        settings = OpenRouterSettings(
            openrouter_api_key="sk-test",
            openrouter_api_base="https://openrouter.ai/api/v1",
        )
        with patch("ai_team.config.llm_factory.LLM") as mock_llm_cls:
            mock_llm = MagicMock()
            mock_llm_cls.return_value = mock_llm
            llm = create_llm_for_role("manager", settings)
            mock_llm_cls.assert_called_once()
            assert llm is mock_llm
