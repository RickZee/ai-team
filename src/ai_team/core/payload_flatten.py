"""JSON-safe flattening for backend results and transport."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


def json_safe_value(value: Any) -> Any:
    """Recursively convert values to JSON-serializable primitives."""
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(k): json_safe_value(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [json_safe_value(v) for v in value]
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        return dump(mode="json")
    content = getattr(value, "content", None)
    if content is not None:
        return {"type": type(value).__name__, "content": json_safe_value(content)}
    return str(value)


def flatten_state_payload(state: Any) -> dict[str, Any]:
    """Return a JSON-safe dict from LangGraph/CrewAI state objects."""
    safe = json_safe_value(state)
    if isinstance(safe, dict):
        return safe
    return {"value": safe}
