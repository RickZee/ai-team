"""
Unit tests for Pydantic settings: loading from env,
validation errors for missing or invalid fields.
"""

import os
from unittest.mock import patch

import pytest
from ai_team.config.settings import (
    GuardrailSettings,
    MemorySettings,
    Settings,
    get_settings,
    reload_settings,
    scoped_workspace_dir,
)
from pydantic import ValidationError

# -----------------------------------------------------------------------------
# Pydantic settings loading from env
# -----------------------------------------------------------------------------


class TestSettingsLoadFromEnv:
    def test_default_settings_load_without_env(self) -> None:
        """With no .env, Settings() uses defaults."""
        env = {k: v for k, v in os.environ.items() if k != "MEMORY_MEMORY_ENABLED"}
        with patch.dict(os.environ, env, clear=True):
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
        with pytest.raises(ValidationError):
            GuardrailSettings(test_coverage_min=1.5)
        with pytest.raises(ValidationError):
            GuardrailSettings(test_coverage_min=-0.1)

    def test_memory_retention_days_bounds(self) -> None:
        with pytest.raises(ValidationError):
            MemorySettings(retention_days=0)
        with pytest.raises(ValidationError):
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


# -----------------------------------------------------------------------------
# scoped_workspace_dir
# -----------------------------------------------------------------------------


class TestScopedWorkspaceDir:
    """Regression coverage for a real bug: backends set PROJECT_WORKSPACE_DIR
    with a bare os.environ write and no restore, so one run's workspace path
    leaked into any later call in the same process that didn't override it
    (observed as stray workspace/<value>/ directories accumulating). All
    backends now use scoped_workspace_dir instead.
    """

    def test_sets_workspace_dir_inside_block(self) -> None:
        with scoped_workspace_dir("/tmp/scoped-test-a"):
            assert os.environ.get("PROJECT_WORKSPACE_DIR") == "/tmp/scoped-test-a"
            assert get_settings().project.workspace_dir == "/tmp/scoped-test-a"

    def test_restores_prior_value_on_exit(self) -> None:
        with patch.dict(os.environ, {"PROJECT_WORKSPACE_DIR": "/tmp/prior"}, clear=False):
            with scoped_workspace_dir("/tmp/scoped-test-b"):
                assert os.environ.get("PROJECT_WORKSPACE_DIR") == "/tmp/scoped-test-b"
            assert os.environ.get("PROJECT_WORKSPACE_DIR") == "/tmp/prior"

    def test_unsets_when_previously_absent(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "PROJECT_WORKSPACE_DIR"}
        with patch.dict(os.environ, env, clear=True):
            with scoped_workspace_dir("/tmp/scoped-test-c"):
                assert os.environ.get("PROJECT_WORKSPACE_DIR") == "/tmp/scoped-test-c"
            assert "PROJECT_WORKSPACE_DIR" not in os.environ

    def test_restores_on_exception(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "PROJECT_WORKSPACE_DIR"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="boom"), scoped_workspace_dir("/tmp/scoped-test-d"):
                assert os.environ.get("PROJECT_WORKSPACE_DIR") == "/tmp/scoped-test-d"
                raise ValueError("boom")
            assert "PROJECT_WORKSPACE_DIR" not in os.environ

    def test_nested_scopes_restore_correctly(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "PROJECT_WORKSPACE_DIR"}
        with patch.dict(os.environ, env, clear=True):
            with scoped_workspace_dir("/tmp/outer"):
                with scoped_workspace_dir("/tmp/inner"):
                    assert os.environ.get("PROJECT_WORKSPACE_DIR") == "/tmp/inner"
                assert os.environ.get("PROJECT_WORKSPACE_DIR") == "/tmp/outer"
            assert "PROJECT_WORKSPACE_DIR" not in os.environ
