"""Tag a native-OTel backend's root span so it lines up with ai-team's own export.

Strands and Agent Framework emit OpenTelemetry themselves. Their spans reach the same collector
as ``evals trace export-otel``; this helper puts ``ai_team.run_id`` (and friends) on the
backend's top-level span, so one filter in the viewer shows both accounts of a run.

No OpenTelemetry import here: the backend passes in its framework's tracer.
Spec: ``.kiro/specs/otel-observability/`` R4.2.
"""

from __future__ import annotations

from contextlib import AbstractContextManager, nullcontext
from typing import Any

PROJECT_NAME = "ai-team"


def run_attributes(*, run_id: str, backend: str) -> dict[str, str]:
    """Attributes every framework root span carries."""
    return {
        "ai_team.run_id": run_id,
        "ai_team.backend": backend,
        "ai_team.source": "framework",
        "openinference.project.name": PROJECT_NAME,
    }


def tag_root_span(
    tracer: Any, *, run_id: str, backend: str, name: str = "ai_team.run"
) -> AbstractContextManager[Any]:
    """Start the backend's root span with the run attributes.

    Args:
        tracer: An OpenTelemetry-API tracer (anything with ``start_as_current_span``), or
            ``None`` when the framework has tracing off.
        run_id: The ai-team run id (``output/runs/<run_id>``).
        backend: The backend name, e.g. ``strands``.
        name: Span name.

    Returns:
        A context manager; use it around the whole run.
    """
    if tracer is None or not hasattr(tracer, "start_as_current_span"):
        return nullcontext()
    span_cm: AbstractContextManager[Any] = tracer.start_as_current_span(
        name, attributes=run_attributes(run_id=run_id, backend=backend)
    )
    return span_cm
