"""Run results bundle: per-run artifacts and traceability."""

from ai_team.core.results.cleanup import RunDeletionResult, delete_run, delete_runs
from ai_team.core.results.models import GeneratedFileEntry, RunMetadata, Scorecard
from ai_team.core.results.writer import (
    ResultsBundle,
    rebuild_registry,
    scorecard_from_langgraph_state,
    scorecard_from_project_state,
)

__all__ = [
    "GeneratedFileEntry",
    "RunDeletionResult",
    "RunMetadata",
    "ResultsBundle",
    "Scorecard",
    "delete_run",
    "delete_runs",
    "rebuild_registry",
    "scorecard_from_langgraph_state",
    "scorecard_from_project_state",
]
