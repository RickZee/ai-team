"""LangChain chat models for LangGraph (OpenRouter via ChatOpenAI-compatible API)."""

from __future__ import annotations

import os

import structlog
from ai_team.config.models import OpenRouterSettings
from langchain_openai import ChatOpenAI

logger = structlog.get_logger(__name__)


def create_chat_model_for_role(
    role: str,
    settings: OpenRouterSettings | None = None,
    *,
    model_id_override: str | None = None,
) -> ChatOpenAI:
    """
    Build a ``ChatOpenAI`` pointed at OpenRouter for the given agent role.

    When ``model_id_override`` is set (from ``TeamProfile.model_overrides``),
    it replaces the model ID that would normally come from ``OpenRouterSettings``.

    Model IDs in settings use the ``openrouter/<provider>/<model>`` prefix; the
    OpenRouter HTTP API expects the ID without that prefix.
    """
    if settings is None:
        settings = OpenRouterSettings.model_validate(
            {"OPENROUTER_API_KEY": os.environ.get("OPENROUTER_API_KEY", "")},
        )
    rc = settings.get_model_for_role(role)
    model_id = model_id_override or rc.model_id
    if model_id.startswith("openrouter/"):
        model_id = model_id[len("openrouter/") :]
    llm = ChatOpenAI(
        model=model_id,
        temperature=rc.temperature,
        max_tokens=min(rc.max_tokens, 8192),
        openai_api_key=settings.openrouter_api_key,
        openai_api_base=settings.openrouter_api_base.rstrip("/"),
    )  # type: ignore[call-arg]
    logger.debug(
        "langgraph_chat_model_created",
        role=role,
        model=model_id,
        override=model_id_override is not None,
    )
    return llm
