"""
LLM factory for OpenRouter inference and local Ollama embeddings.

create_llm_for_role() builds CrewAI LLM instances from OpenRouterSettings (openrouter/
prefixed model IDs). get_embedder_config() returns Ollama embedder config for CrewAI
memory so embeddings stay local while inference goes through OpenRouter.
"""

from __future__ import annotations

import os
from typing import Any, Dict

import structlog
from crewai import LLM

from ai_team.config.models import OpenRouterSettings

logger = structlog.get_logger(__name__)

_DEFAULT_OLLAMA_BASE = "http://localhost:11434"
_DEFAULT_EMBEDDING_MODEL = "nomic-embed-text"


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
    llm = LLM(
        model=role_config.model_id,
        temperature=role_config.temperature,
        max_tokens=role_config.max_tokens,
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
    Return Ollama embedder config for CrewAI memory.

    Uses OLLAMA_BASE_URL and OLLAMA_EMBEDDING_MODEL from the environment.
    Embeddings stay local (Ollama); only inference goes through OpenRouter.

    :return: Dict with 'provider' and 'config' for CrewAI embedder (ollama model_name + url).
    """
    base_url = os.environ.get("OLLAMA_BASE_URL", _DEFAULT_OLLAMA_BASE)
    model = os.environ.get("OLLAMA_EMBEDDING_MODEL", _DEFAULT_EMBEDDING_MODEL)
    return {
        "provider": "ollama",
        "config": {
            "model_name": model,
            "url": base_url.rstrip("/"),
        },
    }
