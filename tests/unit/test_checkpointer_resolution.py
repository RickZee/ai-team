"""Checkpointer resolution for LangGraph."""

from __future__ import annotations

import os
import sqlite3

from ai_team.backends.langgraph_backend.checkpointer import resolve_sqlite_checkpointer


def test_resolve_sqlite_uses_explicit_connection() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    saver = resolve_sqlite_checkpointer(conn)
    assert saver is not None


def test_resolve_sqlite_memory_when_no_env() -> None:
    os.environ.pop("AI_TEAM_LANGGRAPH_SQLITE_PATH", None)
    saver = resolve_sqlite_checkpointer(None)
    assert saver is not None
