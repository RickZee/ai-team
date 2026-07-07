"""Per-run context for LangGraph: identity, workspace scoping, and post-run policy."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog
from ai_team.backends.langgraph_backend.graphs.state import LangGraphProjectState
from ai_team.config.settings import scoped_workspace_dir
from langchain_core.runnables import RunnableConfig

logger = structlog.get_logger(__name__)

_run_session: ContextVar[RunSession | None] = ContextVar("langgraph_run_session", default=None)


@dataclass(frozen=True)
class RunSession:
    """Active LangGraph run: canonical id, workspace path, and post-run flags."""

    run_id: str
    workspace_dir: Path
    skip_post_run: bool = False

    @classmethod
    @contextmanager
    def open(
        cls,
        *,
        run_id: str,
        workspace_root: Path | None = None,
        workspace_dir: Path | None = None,
        skip_post_run: bool | None = None,
    ) -> Iterator[RunSession]:
        """Scope workspace and expose run identity for graph nodes and persistence."""
        if workspace_dir is not None:
            ws = workspace_dir.resolve()
        else:
            root = (workspace_root or Path("./workspace")).resolve()
            ws = root / run_id

        skip = (
            skip_post_run
            if skip_post_run is not None
            else bool(os.environ.get("AI_TEAM_SKIP_POST_RUN"))
        )
        session = cls(run_id=run_id, workspace_dir=ws, skip_post_run=skip)
        token = _run_session.set(session)
        with scoped_workspace_dir(str(ws)):
            try:
                yield session
            finally:
                _run_session.reset(token)


def current_run_session() -> RunSession | None:
    """Return the active :class:`RunSession`, if any."""
    return _run_session.get()


def require_run_id(
    config: RunnableConfig | None,
    state: LangGraphProjectState | dict[str, Any],
) -> str:
    """Resolve canonical run id: ``configurable.thread_id`` wins over state/session."""
    conf = (config or {}).get("configurable") or {}
    thread_id = str(conf.get("thread_id") or "").strip()
    if thread_id:
        state_pid = str(state.get("project_id") or "").strip()
        if state_pid and state_pid != thread_id:
            logger.warning(
                "project_id_thread_mismatch",
                project_id=state_pid,
                thread_id=thread_id,
            )
        return thread_id

    session = current_run_session()
    if session is not None:
        return session.run_id

    state_pid = str(state.get("project_id") or "").strip()
    if state_pid:
        logger.warning("run_id_from_state_only", project_id=state_pid)
        return state_pid

    raise ValueError("run_id required: set configurable.thread_id or open RunSession")
