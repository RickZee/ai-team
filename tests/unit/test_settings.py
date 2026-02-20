"""
Unit tests for Pydantic settings: loading from env, model assignment per role,
validation errors for missing or invalid fields.
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from ai_team.config.settings import (
    Settings,
    OllamaSettings,
    GuardrailSettings,
    MemorySettings,
    get_settings,
    reload_settings,
)


# -----------------------------------------------------------------------------
# Pydantic settings loading from env
# -----------------------------------------------------------------------------


class TestSettingsLoadFromEnv:
    def test_default_settings_load_without_env(self) -> None:
        """With no .env, Settings() uses defaults."""
        with patch.dict(os.environ, {}, clear=False):
            # Clear only our prefixes to avoid side effects
            s = Settings()
        assert s.ollama.base_url == "http://localhost:11434"
        assert s.ollama.default_model == "qwen3:14b"
        assert s.memory.memory_enabled is True
        assert s.guardrails.security_enabled is True

    def test_ollama_base_url_from_env(self) -> None:
        with patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://127.0.0.1:11434"}):
            o = OllamaSettings()
        assert o.base_url == "http://127.0.0.1:11434"

    def test_memory_chromadb_path_from_env(self) -> None:
        with patch.dict(os.environ, {"MEMORY_CHROMADB_PATH": "/tmp/chroma"}):
            m = MemorySettings()
        assert m.chromadb_path == "/tmp/chroma"

    def test_guardrail_test_coverage_min_from_env(self) -> None:
        with patch.dict(os.environ, {"GUARDRAIL_TEST_COVERAGE_MIN": "0.75"}):
            g = GuardrailSettings()
        assert g.test_coverage_min == 0.75


# -----------------------------------------------------------------------------
# Model assignment per role
# -----------------------------------------------------------------------------


class TestModelAssignmentPerRole:
    def test_get_model_for_role_returns_default_for_known_roles(self) -> None:
        o = OllamaSettings()
        assert o.get_model_for_role("manager") == "qwen3:14b"
        assert o.get_model_for_role("architect") == "deepseek-r1:14b"
        assert o.get_model_for_role("backend_dev") == "deepseek-coder-v2:16b"
        assert o.get_model_for_role("qa") == "qwen3:14b"

    def test_get_model_for_role_unknown_returns_default_model(self) -> None:
        o = OllamaSettings()
        result = o.get_model_for_role("unknown_role")
        assert result == o.default_model

    def test_32gb_preset_returns_smaller_models(self) -> None:
        with patch.dict(os.environ, {"OLLAMA_MEMORY_PRESET": "32gb"}):
            o = OllamaSettings()
        assert o.memory_preset == "32gb"
        model = o.get_model_for_role("manager")
        assert "8b" in model or "7b" in model


# -----------------------------------------------------------------------------
# Validation errors for missing or invalid fields
# -----------------------------------------------------------------------------


class TestSettingsValidationErrors:
    def test_ollama_request_timeout_bounds(self) -> None:
        with pytest.raises(Exception):  # Pydantic ValidationError
            OllamaSettings(request_timeout=0)
        with pytest.raises(Exception):
            OllamaSettings(request_timeout=4000)

    def test_guardrail_test_coverage_min_bounds(self) -> None:
        with pytest.raises(Exception):
            GuardrailSettings(test_coverage_min=1.5)
        with pytest.raises(Exception):
            GuardrailSettings(test_coverage_min=-0.1)

    def test_memory_retention_days_bounds(self) -> None:
        with pytest.raises(Exception):
            MemorySettings(retention_days=0)
        with pytest.raises(Exception):
            MemorySettings(retention_days=5000)


# -----------------------------------------------------------------------------
# get_settings and reload_settings
# -----------------------------------------------------------------------------


class TestGetSettings:
    def test_get_settings_returns_singleton(self) -> None:
        a = get_settings()
        b = get_settings()
        assert a is b

    def test_reload_settings_creates_new_instance(self) -> None:
        a = get_settings()
        b = reload_settings()
        assert a is not b
        c = get_settings()
        assert c is b
