"""
LLM factory for OpenRouter inference and embeddings.

create_llm_for_role() builds CrewAI LLM instances from OpenRouterSettings (openrouter/
prefixed model IDs). get_embedder_config() returns embedder config for CrewAI memory
using OpenRouter's embeddings API (OpenAI-compatible; one API key for all).
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import structlog
from crewai import LLM

from ai_team.config.models import OpenRouterSettings

logger = structlog.get_logger(__name__)

# OpenRouter embeddings: use provider/model (e.g. openai/...) not openrouter/openai/...
_DEFAULT_EMBEDDING_MODEL = "openai/text-embedding-3-small"
_OPENROUTER_EMBED_BASE = "https://openrouter.ai/api/v1"


def create_llm_for_role(role: str, settings: OpenRouterSettings) -> LLM:
    """
    Create a CrewAI LLM for the given agent role using OpenRouter.

    Sets OPENROUTER_API_KEY, OPENROUTER_API_BASE, OR_SITE_URL, and OR_APP_NAME
    in the environment so LiteLLM (used by CrewAI) can route requests to OpenRouter.
    Model ID is read from OpenRouterSettings and is already in openrouter/<provider>/<model>
    format.

    :param role: Agent role name (e.g. 'manager', 'backend_developer', 'devops_engineer').
    :param settings: OpenRouter and environment settings.
    :return: Configured CrewAI LLM instance.
    """
    os.environ["OPENROUTER_API_KEY"] = settings.openrouter_api_key
    os.environ["OPENROUTER_API_BASE"] = settings.openrouter_api_base
    if settings.or_site_url:
        os.environ["OR_SITE_URL"] = settings.or_site_url
    if settings.or_app_name:
        os.environ["OR_APP_NAME"] = settings.or_app_name

    role_config = settings.get_model_for_role(role)
    # Cap max_tokens so requests stay within OpenRouter key limits (402 = credits/max_tokens)
    max_tokens = min(role_config.max_tokens, 8192)
    llm = LLM(
        model=role_config.model_id,
        temperature=role_config.temperature,
        max_tokens=max_tokens,
    )
    logger.debug(
        "llm_factory_created",
        role=role,
        model=role_config.model_id,
        temperature=role_config.temperature,
    )
    return llm


def get_embedder_config() -> Dict[str, Any]:
    """
    Return OpenRouter-backed embedder config for CrewAI memory.

    Uses OPENROUTER_API_KEY and optional OPENROUTER_EMBEDDING_MODEL / OPENROUTER_API_BASE.
    Sets OPENAI_API_KEY and OPENAI_API_BASE so CrewAI's OpenAI provider routes to OpenRouter
    (one API key for LLM and embeddings).

    :return: Dict with 'provider' and 'config' for CrewAI embedder (openai-compatible).
    """
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    base_url = os.environ.get("OPENROUTER_API_BASE", _OPENROUTER_EMBED_BASE).rstrip("/")
    model = os.environ.get("OPENROUTER_EMBEDDING_MODEL", _DEFAULT_EMBEDDING_MODEL)
    if api_key:
        os.environ["OPENAI_API_KEY"] = api_key
        os.environ["OPENAI_API_BASE"] = base_url
    return {
        "provider": "openai",
        "config": {
            "model_name": model,
        },
    }


def complete_with_openrouter(
    prompt: str,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
) -> str:
    """
    One-shot completion via OpenRouter HTTP API (for tools that need a simple LLM call).

    :param prompt: User prompt text.
    :param model: OpenRouter model ID (e.g. openrouter/deepseek/...). If None, uses manager model from settings.
    :param api_key: API key; if None, uses OPENROUTER_API_KEY from env.
    :param api_base: API base URL; if None, uses OPENROUTER_API_BASE from env or default.
    :return: Assistant content string, or empty string on failure.
    """
    import httpx

    key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        logger.warning("complete_with_openrouter_skip", reason="OPENROUTER_API_KEY not set")
        return ""
    base = (api_base or os.environ.get("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1")).rstrip("/")
    if model is None:
        settings = OpenRouterSettings()
        model = settings.get_model_for_role("manager").model_id
    url = f"{base}/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1024,
    }
    try:
        with httpx.Client(timeout=60.0) as client:
            r = client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
            choices = data.get("choices", [])
            if not choices:
                return ""
            content = choices[0].get("message", {}).get("content", "")
            return (content or "").strip()
    except Exception as e:
        logger.warning("complete_with_openrouter_failed", error=str(e))
        return ""
