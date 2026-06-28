"""LangChain chat models for LangGraph (OpenRouter via ChatOpenAI-compatible API)."""

from __future__ import annotations

import json
import os

import httpx
import structlog
from ai_team.config.models import OpenRouterSettings
from langchain_core.messages import AIMessage, BaseMessage
from langchain_openai import ChatOpenAI

logger = structlog.get_logger(__name__)


def _fix_tool_call_args(msg: BaseMessage) -> BaseMessage:
    """Ensure tool_calls args are dicts, not JSON strings (some models serialize as string)."""
    if not isinstance(msg, AIMessage) or not msg.tool_calls:
        return msg
    fixed = []
    changed = False
    for tc in msg.tool_calls:
        args = tc.get("args")
        if isinstance(args, str):
            try:
                tc = {**tc, "args": json.loads(args)}
                changed = True
            except (json.JSONDecodeError, ValueError) as e:
                # Malformed tool-call args (e.g. truncated/prose-wrapped JSON from
                # deepseek). Leave the raw string for the agent to handle, but log
                # it — silently swallowing this previously masked QA failures.
                logger.warning(
                    "tool_call_args_unparseable",
                    tool=tc.get("name"),
                    error=str(e),
                    preview=args[:200],
                )
        fixed.append(tc)
    if not changed:
        return msg
    return msg.model_copy(update={"tool_calls": fixed})


def _fix_chat_completion_response(response: httpx.Response) -> None:
    """httpx response event hook: normalise tool_call function.arguments dict→JSON string.

    deepseek-v3 via OpenRouter returns function.arguments as a parsed dict instead of
    the JSON string the OpenAI SDK requires. With openai SDK defer_build=True models,
    this causes a MockValSer/TypeError when model_dump() is called on the ChatCompletion.

    We hook the raw HTTP response, read + rewrite the body before the SDK parses it.
    Event hooks run after the response is received but before the SDK processes it.
    """
    if "chat/completions" not in str(response.request.url):
        return
    response.read()
    try:
        data = json.loads(response.text)
    except (json.JSONDecodeError, ValueError):
        return

    changed = False
    for choice in data.get("choices") or []:
        msg = choice.get("message") or {}
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function") or {}
            args = fn.get("arguments")
            if not isinstance(args, str):
                fn["arguments"] = json.dumps(args)
                changed = True

    if not changed:
        return

    new_body = json.dumps(data).encode()
    response._content = new_body  # type: ignore[attr-defined]
    # Strip content-encoding so the SDK doesn't try to decompress already-decoded content
    headers = {k: v for k, v in response.headers.items() if k.lower() != "content-encoding"}
    response.headers = httpx.Headers(headers)


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

    http_client = httpx.Client(event_hooks={"response": [_fix_chat_completion_response]})
    async_http_client = httpx.AsyncClient(event_hooks={"response": [_fix_chat_completion_response]})

    llm = ChatOpenAI(
        model=model_id,
        temperature=rc.temperature,
        max_tokens=min(rc.max_tokens, 8192),
        openai_api_key=settings.openrouter_api_key,
        openai_api_base=settings.openrouter_api_base.rstrip("/"),
        http_client=http_client,
        http_async_client=async_http_client,
    )  # type: ignore[call-arg]
    logger.debug(
        "langgraph_chat_model_created",
        role=role,
        model=model_id,
        override=model_id_override is not None,
    )
    return llm
