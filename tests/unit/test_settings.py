"""
Unit tests for Pydantic settings: loading from env,
validation errors for missing or invalid fields.
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from ai_team.config.settings import (
    Settings,
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
            s = Settings()
        assert s.memory.memory_enabled is True
        assert s.memory.embedding_api_base == "https://openrouter.ai/api/v1"
        assert s.guardrails.security_enabled is True

    def test_memory_chromadb_path_from_env(self) -> None:
        with patch.dict(os.environ, {"MEMORY_CHROMADB_PATH": "/tmp/chroma"}):
            m = MemorySettings()
        assert m.chromadb_path == "/tmp/chroma"

    def test_memory_embedding_api_base_from_env(self) -> None:
        with patch.dict(os.environ, {"MEMORY_EMBEDDING_API_BASE": "https://api.example.com/v1"}):
            m = MemorySettings()
        assert m.embedding_api_base == "https://api.example.com/v1"

    def test_guardrail_test_coverage_min_from_env(self) -> None:
        with patch.dict(os.environ, {"GUARDRAIL_TEST_COVERAGE_MIN": "0.75"}):
            g = GuardrailSettings()
        assert g.test_coverage_min == 0.75


# -----------------------------------------------------------------------------
# Validation errors for missing or invalid fields
# -----------------------------------------------------------------------------


class TestSettingsValidationErrors:
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
