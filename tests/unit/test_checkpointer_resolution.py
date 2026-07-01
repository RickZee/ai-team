"""Checkpointer resolution for LangGraph."""

from __future__ import annotations

import sqlite3

from ai_team.backends.langgraph_backend.checkpointer import resolve_sqlite_checkpointer


def test_resolve_sqlite_uses_explicit_connection() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    saver = resolve_sqlite_checkpointer(conn)
    assert saver is not None


def test_resolve_sqlite_memory_when_no_env(monkeypatch) -> None:
    # monkeypatch restores the var after the test — a raw os.environ.pop would
    # permanently remove it for the rest of the test session (it's a process-
    # wide singleton set once by ai_team.ui.web.server's import), breaking
    # any later test that depends on that default being present.
    monkeypatch.delenv("AI_TEAM_LANGGRAPH_SQLITE_PATH", raising=False)
    saver = resolve_sqlite_checkpointer(None)
    assert saver is not None
