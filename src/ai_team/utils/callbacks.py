"""Event callbacks and human-in-the-loop hooks."""

from typing import Any, Callable

def register_callback(event: str, handler: Callable[..., Any]) -> None:
    """Register a callback for flow/crew events."""
    raise NotImplementedError("Callbacks not yet implemented")
