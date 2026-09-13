"""Trace schema versioning and in-memory migrations (R14.3)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from evals.trace.models import SCHEMA_VERSION


class TraceSchemaError(ValueError):
    """Raised when a trace document cannot be loaded without a missing migration."""


def _identity(doc: dict[str, Any]) -> dict[str, Any]:
    return doc


def _migrate_v2(doc: dict[str, Any]) -> dict[str, Any]:
    """Add optional ``arm_id``; payload ``context_pressure`` is already free-form."""
    out = dict(doc)
    out.setdefault("arm_id", None)
    return out


# Map: target_version -> migration that upgrades FROM target_version-1 TO target_version.
MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {
    1: _identity,
    2: _migrate_v2,
}


def migrate_trace_dict(doc: dict[str, Any]) -> dict[str, Any]:
    """Upgrade *doc* in memory to the current :data:`SCHEMA_VERSION`.

    Raises:
        TraceSchemaError: When the document's version is newer than known, or a
            required intermediate migration is missing.
    """
    raw_version = doc.get("schema_version", 1)
    try:
        version = int(raw_version)
    except (TypeError, ValueError) as exc:
        raise TraceSchemaError(
            f"invalid schema_version {raw_version!r}; migration required"
        ) from exc

    if version > SCHEMA_VERSION:
        raise TraceSchemaError(
            f"trace schema_version={version} is newer than supported "
            f"{SCHEMA_VERSION}; required migration is not available"
        )

    current = dict(doc)
    while version < SCHEMA_VERSION:
        nxt = version + 1
        migrator = MIGRATIONS.get(nxt)
        if migrator is None:
            raise TraceSchemaError(
                f"no migration registered for schema_version {nxt}; "
                f"cannot upgrade from {version}"
            )
        current = migrator(current)
        current["schema_version"] = nxt
        version = nxt
    return current
