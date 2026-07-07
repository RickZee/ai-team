"""Unit tests for LangGraph run session and identity helpers."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from ai_team.backends.langgraph_backend.run_session import (
    RunSession,
    current_run_session,
    require_run_id,
)


def test_require_run_id_prefers_thread_id() -> None:
    wrong = str(uuid4())
    run_id = require_run_id(
        {"configurable": {"thread_id": "canonical-thread"}},
        {"project_id": wrong},
    )
    assert run_id == "canonical-thread"


def test_require_run_id_uses_session_when_config_missing() -> None:
    with RunSession.open(run_id="session-thread", workspace_root=Path("/tmp/ws")):
        run_id = require_run_id(None, {})
        assert run_id == "session-thread"


def test_run_session_scopes_workspace(tmp_path: Path) -> None:
    ws_root = tmp_path / "workspace"
    with RunSession.open(run_id="run-a", workspace_root=ws_root, skip_post_run=True):
        session = current_run_session()
        assert session is not None
        assert session.run_id == "run-a"
        assert session.workspace_dir == ws_root / "run-a"
        assert session.skip_post_run is True
    assert current_run_session() is None


def test_require_run_id_raises_without_sources() -> None:
    with pytest.raises(ValueError, match="run_id required"):
        require_run_id(None, {})
