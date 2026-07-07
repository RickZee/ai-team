"""LangGraph post-run persistence (manager self-improvement report)."""

from __future__ import annotations

import os
from typing import Any

import structlog
from ai_team.backends.langgraph_backend.run_session import current_run_session
from ai_team.core.results.writer import ResultsBundle
from ai_team.reports.manager_self_improvement import write_manager_self_improvement_report

logger = structlog.get_logger(__name__)

_TERMINAL_PHASES = frozenset({"complete", "error"})


def write_langgraph_manager_report(run_id: str, state: dict[str, Any]) -> dict[str, Any] | None:
    """Write manager self-improvement artifacts when a run reaches a terminal phase."""
    phase = str(state.get("current_phase") or "")
    if phase not in _TERMINAL_PHASES:
        return None

    session = current_run_session()
    if session and session.skip_post_run:
        logger.debug("manager_report_skipped", reason="run_session_skip_post_run")
        return None
    if os.environ.get("AI_TEAM_SKIP_POST_RUN"):
        logger.debug("manager_report_skipped", reason="AI_TEAM_SKIP_POST_RUN")
        return None

    if not run_id.strip():
        logger.warning("manager_report_skipped", reason="missing_run_id")
        return None

    meta = dict(state.get("metadata") or {})
    team = str(meta.get("team_profile") or "full")
    try:
        if session is not None:
            bundle = ResultsBundle(run_id, workspace_dir=session.workspace_dir)
        else:
            bundle = ResultsBundle(run_id)
        write_manager_self_improvement_report(
            bundle,
            backend="langgraph",
            team_profile=team,
            state=state,
        )
        logger.info("manager_report_written", run_id=run_id, phase=phase)
        return {"manager_self_improvement_report": "reports/manager_self_improvement_report.md"}
    except Exception as e:
        logger.warning("manager_report_failed", error=str(e), run_id=run_id)
        return None
