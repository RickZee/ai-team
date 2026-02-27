"""
Unit tests for pre-flight model validation (OpenRouter chat + embedding).
"""

import os
from unittest.mock import MagicMock, patch

import httpx
import pytest
from ai_team.config.model_validation import (
    ModelValidationError,
    validate_models_before_run,
)
from ai_team.config.models import OpenRouterSettings, RoleModelConfig
from ai_team.config.settings import MemorySettings


def _role_config(model_id: str) -> RoleModelConfig:
    from ai_team.config.models import ModelPricing

    return RoleModelConfig(
        model_id=model_id,
        pricing=ModelPricing(0.1, 0.1),
        temperature=0.7,
        max_tokens=4096,
    )


class TestModelValidationError:
    """Tests for ModelValidationError."""

    def test_message_includes_missing_ids(self) -> None:
        err = ModelValidationError(["model/a", "model/b"])
        assert "model/a" in str(err)
        assert "model/b" in str(err)

    def test_custom_message(self) -> None:
        err = ModelValidationError(["x"], message="Custom")
        assert str(err) == "Custom"
        assert err.missing == ["x"]


class TestValidateModelsBeforeRun:
    """Tests for validate_models_before_run with mocked HTTP."""

    @pytest.fixture
    def openrouter_settings(self) -> MagicMock:
        s = MagicMock(spec=OpenRouterSettings)
        s.openrouter_api_key = "test-key"
        s.openrouter_api_base = "https://openrouter.example/api/v1"
        s.get_models.return_value = {
            "manager": _role_config("openrouter/openai/gpt-4o-mini"),
            "architect": _role_config("openrouter/openai/gpt-4o-mini"),
        }
        return s

    @pytest.fixture
    def memory_settings(self) -> MemorySettings:
        return MemorySettings(embedding_model="openai/text-embedding-3-small")

    def test_passes_when_all_chat_and_embedding_available(
        self,
        openrouter_settings: MagicMock,
        memory_settings: MemorySettings,
    ) -> None:
        models_response = [{"id": "openrouter/openai/gpt-4o-mini"}, {"id": "openai/text-embedding-3-small"}]
        req_get = httpx.Request("GET", "https://openrouter.example/api/v1/models")
        req_post = httpx.Request("POST", "https://openrouter.example/api/v1/embeddings")

        def fake_get(url: str, **kwargs: object) -> httpx.Response:
            assert "models" in url
            return httpx.Response(200, json={"data": models_response}, request=req_get)

        def fake_post(url: str, **kwargs: object) -> httpx.Response:
            assert "embeddings" in url
            return httpx.Response(
                200, json={"data": [{"embedding": [0.1]}]}, request=req_post
            )

        with patch("ai_team.config.model_validation.httpx.Client") as client_cls:
            client = MagicMock()
            client.get = fake_get
            client.post = fake_post
            client.__enter__ = MagicMock(return_value=client)
            client.__exit__ = MagicMock(return_value=False)
            client_cls.return_value = client

            validate_models_before_run(openrouter_settings, memory_settings)

        openrouter_settings.get_models.assert_called_once()

    def test_raises_when_chat_model_missing(
        self,
        openrouter_settings: MagicMock,
        memory_settings: MemorySettings,
    ) -> None:
        # Only one model in response; we require openrouter/openai/gpt-4o-mini
        models_response = [{"id": "other/model"}]
        req_get = httpx.Request("GET", "https://openrouter.example/api/v1/models")
        req_post = httpx.Request("POST", "https://openrouter.example/api/v1/embeddings")

        def fake_get(url: str, **kwargs: object) -> httpx.Response:
            return httpx.Response(200, json={"data": models_response}, request=req_get)

        def fake_post(url: str, **kwargs: object) -> httpx.Response:
            return httpx.Response(
                200, json={"data": [{"embedding": [0.1]}]}, request=req_post
            )

        with patch("ai_team.config.model_validation.httpx.Client") as client_cls:
            client = MagicMock()
            client.get = fake_get
            client.post = fake_post
            client.__enter__ = MagicMock(return_value=client)
            client.__exit__ = MagicMock(return_value=False)
            client_cls.return_value = client

            with pytest.raises(ModelValidationError) as exc_info:
                validate_models_before_run(openrouter_settings, memory_settings)

        assert "openrouter/openai/gpt-4o-mini" in str(exc_info.value)
        assert exc_info.value.missing

    def test_raises_when_embedding_model_missing(
        self,
        openrouter_settings: MagicMock,
        memory_settings: MemorySettings,
    ) -> None:
        models_response = [{"id": "openrouter/openai/gpt-4o-mini"}]
        req_get = httpx.Request("GET", "https://openrouter.example/api/v1/models")
        req_post = httpx.Request("POST", "https://openrouter.example/api/v1/embeddings")

        def fake_get(url: str, **kwargs: object) -> httpx.Response:
            return httpx.Response(200, json={"data": models_response}, request=req_get)

        def fake_post(url: str, **kwargs: object) -> httpx.Response:
            return httpx.Response(
                400, text="Model does not exist", request=req_post
            )

        with patch("ai_team.config.model_validation.httpx.Client") as client_cls:
            client = MagicMock()
            client.get = fake_get
            client.post = fake_post
            client.__enter__ = MagicMock(return_value=client)
            client.__exit__ = MagicMock(return_value=False)
            client_cls.return_value = client

            with pytest.raises(ModelValidationError) as exc_info:
                validate_models_before_run(openrouter_settings, memory_settings)

        assert memory_settings.embedding_model in str(exc_info.value)
        assert memory_settings.embedding_model in exc_info.value.missing

    def test_skipped_when_no_api_key(
        self,
        openrouter_settings: MagicMock,
        memory_settings: MemorySettings,
    ) -> None:
        openrouter_settings.openrouter_api_key = ""
        with (
            patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}, clear=False),
            patch("ai_team.config.model_validation.httpx.Client") as client_cls,
        ):
            validate_models_before_run(openrouter_settings, memory_settings)
            client_cls.assert_not_called()
