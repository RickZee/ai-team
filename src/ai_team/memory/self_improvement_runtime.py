"""Runtime wiring for the self-improvement loop.

This module closes two gaps identified in ``docs/SELF_IMPROVEMENT_AUDIT.md``:

* **Gap #1 (open loop):** lessons were only extracted by manually running
  ``scripts/extract_lessons.py`` between runs. :func:`maybe_extract_lessons_at_startup`
  runs the deterministic extraction at the start of every run (gated by
  ``AI_TEAM_SI_AUTO_EXTRACT``, default on) so the loop is closed by default.
* **Gap #3 (metrics never persisted):** the ``performance_metrics`` table had a
  writer (``LongTermStore.add_metric``) but no caller in the run flow.
  :func:`persist_run_metrics` records per-run quality KPIs at run end so the
  question "is the system getting better over time?" becomes answerable.

Both functions follow the project convention that a broken self-improvement
subsystem must **never** break a run: every external call is wrapped and failures
are logged, not raised.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from ai_team.core.result import ProjectResult

logger = structlog.get_logger(__name__)

# Sentinel role for run-level (non-agent) metrics.
_RUN_SCOPE_ROLE = "_run"

_TRUTHY = frozenset({"1", "true", "yes", "on"})
_FALSEY = frozenset({"0", "false", "no", "off"})


def _env_flag(name: str, *, default: bool) -> bool:
    """Parse a boolean environment flag with a default.

    Unrecognized values fall back to ``default`` rather than raising, so a typo
    in configuration can never abort a run.
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    val = raw.strip().lower()
    if val in _TRUTHY:
        return True
    if val in _FALSEY:
        return False
    return default


def maybe_extract_lessons_at_startup(*, promote_threshold: int = 2) -> dict[str, int] | None:
    """Run deterministic lesson extraction at run startup (gap #1).

    Gated by ``AI_TEAM_SI_AUTO_EXTRACT`` (default ``True``). Extraction is a pure
    SQLite operation with no LLM calls, so it is cheap and safe to run on every
    invocation. Returns the extraction counters, or ``None`` when disabled or on
    failure.

    Args:
        promote_threshold: Minimum recurrences before a failure pattern is
            promoted to a lesson. Mirrors ``extract_lessons``' default.

    Returns:
        ``{"scanned", "promoted", "infra_flagged"}`` on success, else ``None``.
    """
    if not _env_flag("AI_TEAM_SI_AUTO_EXTRACT", default=True):
        logger.debug("auto_extract_disabled")
        return None
    try:
        from ai_team.memory.lessons import extract_lessons

        counters = extract_lessons(promote_threshold=promote_threshold)
        logger.info("auto_extract_lessons", **counters)
        return counters
    except Exception as e:  # noqa: BLE001 - SI must never break a run
        logger.warning("auto_extract_failed", error=str(e))
        return None


def _coerce_float(value: Any) -> float | None:
    """Best-effort numeric coercion; returns ``None`` for non-numeric input."""
    if isinstance(value, bool):
        # bool is a subclass of int; treat as 1.0/0.0 explicitly.
        return 1.0 if value else 0.0
    if isinstance(value, int | float):
        return float(value)
    return None


def _metrics_from_result(result: ProjectResult) -> dict[str, float]:
    """Extract numeric run-level KPIs from a :class:`ProjectResult`.

    Reads from the backend payload (``result.raw``) defensively: backends differ
    in exactly what they surface, so every field is optional.
    """
    metrics: dict[str, float] = {}
    metrics["run_success"] = 1.0 if result.success else 0.0

    raw = result.raw if isinstance(result.raw, dict) else {}

    # Scorecard / KPIs live under a few possible keys depending on backend.
    kpi_sources: list[dict[str, Any]] = []
    for key in ("kpis", "scorecard", "result", "state"):
        candidate = raw.get(key)
        if isinstance(candidate, dict):
            kpi_sources.append(candidate)
            nested = candidate.get("kpis")
            if isinstance(nested, dict):
                kpi_sources.append(nested)

    # Known numeric KPI names produced by the results writer.
    wanted = (
        "files_generated",
        "tests_total",
        "tests_passed_count",
        "duration_seconds",
        "coverage_pct",
        "code_quality_score",
        "total_cost_usd",
        "retry_count",
        "error_count",
    )
    for source in kpi_sources:
        for name in wanted:
            if name in metrics:
                continue
            coerced = _coerce_float(source.get(name))
            if coerced is not None:
                metrics[name] = coerced

    # Derived: test pass rate when both counts are present and total > 0.
    total = metrics.get("tests_total")
    passed = metrics.get("tests_passed_count")
    if total and total > 0 and passed is not None:
        metrics["test_pass_rate"] = round(passed / total, 4)

    return metrics


def persist_run_metrics(result: ProjectResult) -> int:
    """Persist per-run quality metrics to ``performance_metrics`` (gap #3).

    Records run-level KPIs (success, tests, coverage, cost, quality, duration)
    against the sentinel role ``_run`` so trend queries can answer whether the
    system is improving over time. Gated by ``AI_TEAM_SI_PERSIST_METRICS``
    (default ``True``).

    Args:
        result: The normalized backend result for the completed run.

    Returns:
        The number of metrics written (``0`` when disabled or on failure).
    """
    if not _env_flag("AI_TEAM_SI_PERSIST_METRICS", default=True):
        logger.debug("persist_metrics_disabled")
        return 0
    try:
        from ai_team.config.settings import get_settings
        from ai_team.memory.memory_config import LongTermStore

        metrics = _metrics_from_result(result)
        if not metrics:
            return 0

        settings = get_settings()
        if not settings.memory.memory_enabled:
            logger.debug("persist_metrics_skipped_memory_disabled")
            return 0

        store = LongTermStore(
            sqlite_path=settings.memory.sqlite_path,
            retention_days=settings.memory.retention_days,
        )
        backend = result.backend_name or "unknown"
        written = 0
        for name, value in metrics.items():
            try:
                store.add_metric(
                    agent_role=_RUN_SCOPE_ROLE,
                    model=backend,
                    metric_name=name,
                    value=value,
                )
                written += 1
            except Exception as e:  # noqa: BLE001 - one bad metric must not abort the rest
                logger.warning("persist_metric_failed", metric=name, error=str(e))
        logger.info("run_metrics_persisted", written=written, backend=backend)
        return written
    except Exception as e:  # noqa: BLE001 - SI must never break a run
        logger.warning("persist_run_metrics_failed", error=str(e))
        return 0
