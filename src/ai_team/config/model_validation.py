"""
Pre-flight validation of OpenRouter model IDs before a run.

Checks that all chat models (from OpenRouterSettings for the current env) and
the embedding model (from MemorySettings) exist or are reachable on OpenRouter,
so we fail fast with a clear message instead of failing mid-run.
"""

from __future__ import annotations

import os

import httpx
import structlog
from ai_team.config.models import OpenRouterSettings
from ai_team.config.settings import MemorySettings

logger = structlog.get_logger(__name__)

_VALIDATION_TIMEOUT = 10.0
_OPENROUTER_MODELS_PATH = "/models"
_OPENROUTER_EMBEDDINGS_PATH = "/embeddings"


class ModelValidationError(Exception):
    """Raised when one or more required models are not available on OpenRouter."""

    def __init__(self, missing: list[str], message: str = "") -> None:
        self.missing = missing
        self._message = message or (
            "The following models are not available on OpenRouter: "
            + "; ".join(missing)
            + ". Check OPENROUTER_EMBEDDING_MODEL and your env's model IDs in config."
        )
        super().__init__(self._message)

    def __str__(self) -> str:
        return self._message


def _collect_chat_model_ids(openrouter_settings: OpenRouterSettings) -> set[str]:
    """Return unique chat model IDs that will be used for the current env."""
    models = openrouter_settings.get_models()
    return {cfg.model_id for cfg in models.values()}


def _fetch_available_chat_models(api_base: str, api_key: str) -> set[str]:
    """GET OpenRouter /models and return set of available model IDs."""
    url = api_base.rstrip("/") + _OPENROUTER_MODELS_PATH
    with httpx.Client(timeout=_VALIDATION_TIMEOUT) as client:
        resp = client.get(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
        )
        resp.raise_for_status()
    data = resp.json()
    ids: set[str] = set()
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and "id" in item:
                raw = str(item["id"])
                ids.add(raw)
                if not raw.startswith("openrouter/"):
                    ids.add("openrouter/" + raw)
    elif isinstance(data, dict) and "data" in data:
        for item in data["data"] or []:
            if isinstance(item, dict) and "id" in item:
                raw = str(item["id"])
                ids.add(raw)
                if not raw.startswith("openrouter/"):
                    ids.add("openrouter/" + raw)
    return ids


def _validate_embedding_model(
    api_base: str,
    api_key: str,
    embedding_model: str,
) -> None:
    """
    Validate embedding model by POSTing a minimal embeddings request.
    Raises ModelValidationError if the model does not exist (400 with message).
    """
    url = api_base.rstrip("/") + _OPENROUTER_EMBEDDINGS_PATH
    with httpx.Client(timeout=_VALIDATION_TIMEOUT) as client:
        resp = client.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": embedding_model,
                "input": "validate",
            },
        )
    if resp.status_code == 200:
        return
    if resp.status_code == 400:
        body = resp.text
        if "does not exist" in body.lower() or "not found" in body.lower() or "400" in body:
            raise ModelValidationError(
                [embedding_model],
                message=f"Embedding model '{embedding_model}' is not available on OpenRouter (400). "
                "Check OPENROUTER_EMBEDDING_MODEL / MEMORY_EMBEDDING_MODEL.",
            )
    resp.raise_for_status()


def validate_models_before_run(
    openrouter_settings: OpenRouterSettings,
    memory_settings: MemorySettings,
) -> None:
    """
    Ensure all chat models and the embedding model exist on OpenRouter.

    :param openrouter_settings: Current OpenRouter env and API config.
    :param memory_settings: Memory config containing embedding model.
    :raises ModelValidationError: If any required model is missing, with list of missing IDs.
    """
    api_key = openrouter_settings.openrouter_api_key or os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key or api_key == "dummy":
        logger.warning("model_validation_skipped", reason="no_openrouter_api_key")
        return

    api_base = openrouter_settings.openrouter_api_base or "https://openrouter.ai/api/v1"
    missing: list[str] = []

    # Chat models
    required_chat = _collect_chat_model_ids(openrouter_settings)
    if required_chat:
        try:
            available = _fetch_available_chat_models(api_base, api_key)
        except httpx.HTTPError as e:
            logger.warning("model_validation_chat_fetch_failed", error=str(e))
            raise ModelValidationError(
                list(required_chat),
                message=f"Could not fetch OpenRouter models list: {e}. Check API key and network.",
            ) from e
        for mid in required_chat:
            if mid not in available:
                missing.append(mid)

    # Embedding model
    embedding_model = memory_settings.embedding_model
    embed_base = memory_settings.embedding_api_base or api_base
    try:
        _validate_embedding_model(embed_base, api_key, embedding_model)
    except ModelValidationError:
        missing.append(embedding_model)
    except httpx.HTTPError as e:
        logger.warning("model_validation_embed_failed", error=str(e), model=embedding_model)
        missing.append(embedding_model)

    if missing:
        raise ModelValidationError(
            missing,
            message=(
                "The following models are not available on OpenRouter: "
                + "; ".join(missing)
                + ". Check OPENROUTER_EMBEDDING_MODEL and your env's model IDs in config."
            ),
        )

    logger.info(
        "model_validation_passed",
        chat_models=sorted(required_chat) if required_chat else [],
        embedding_model=embedding_model,
    )
