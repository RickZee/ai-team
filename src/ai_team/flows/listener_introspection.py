"""Introspect CrewAI Flow listener wiring for self-trigger loops.

CrewAI Flow emits a completed method's own name as the next trigger and clears
completed listeners to allow cycles. A method that ``@listen``s to its own name
therefore re-triggers forever (taxonomy FM-002 / failure-taxonomy §2).

This module is the single source of truth for that introspection — used by the
unit meta-test and by ``CHK-listener-self-trigger``.
"""

from __future__ import annotations

from typing import Any


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
