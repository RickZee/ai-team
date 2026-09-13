"""Backend-neutral CrewAI Flow listener introspection (eval contract, R10.2).

Evals must not import ``ai_team.backends.crewai_backend.flows``. The CrewAI flow class registers itself
here at import time; checks introspect whatever is registered.
"""

from __future__ import annotations

from typing import Any

_FLOW_CLS: type[Any] | None = None


def register_flow_class(flow_cls: type[Any]) -> None:
    """Record the live Flow subclass for listener self-trigger checks."""
    global _FLOW_CLS
    _FLOW_CLS = flow_cls


def get_registered_flow_class() -> type[Any] | None:
    """Return the registered Flow class, or None if no backend loaded it."""
    return _FLOW_CLS


def flow_trigger_map(flow_cls: type[Any]) -> dict[str, tuple[list[str], bool]]:
    """Map method name → ``(trigger names, is_router)`` for Flow-decorated methods.

    Args:
        flow_cls: A CrewAI ``Flow`` subclass (e.g. ``AITeamFlow``).

    Returns:
        Dict keyed by method name. Each value is the list of trigger strings the
        method listens to, plus whether the method is a ``@router``.
    """
    out: dict[str, tuple[list[str], bool]] = {}
    for name in dir(flow_cls):
        attr = getattr(flow_cls, name, None)
        triggers = getattr(attr, "__trigger_methods__", None)
        if triggers is None:
            continue
        is_router = bool(getattr(attr, "__is_router__", False))
        out[name] = ([str(t) for t in triggers], is_router)
    return out


def self_triggering_listeners(flow_cls: type[Any]) -> list[str]:
    """Return method names that listen to their own name (infinite self-trigger).

    Args:
        flow_cls: A CrewAI ``Flow`` subclass to introspect.

    Returns:
        Sorted list of offending method names (empty when wiring is safe).
    """
    offenders = [
        name for name, (triggers, _) in flow_trigger_map(flow_cls).items() if name in triggers
    ]
    return sorted(offenders)
