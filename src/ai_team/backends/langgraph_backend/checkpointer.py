"""
LangGraph checkpointer helpers: SQLite (dev / default) and Postgres (production).

Environment:
    AI_TEAM_LANGGRAPH_POSTGRES_URI: Use ``PostgresSaver`` (LangGraph backend wraps invoke).
    AI_TEAM_LANGGRAPH_SQLITE_PATH: Persistent SQLite DB for checkpoints (otherwise in-memory
    when compiling without an explicit connection).
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

import structlog
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.sqlite import SqliteSaver

logger = structlog.get_logger(__name__)

T = TypeVar("T")


def build_sqlite_saver(path: str | None) -> SqliteSaver:
    """Create a ``SqliteSaver`` for ``path`` (or in-memory when ``path`` is None)."""
    if path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(p), check_same_thread=False)
        logger.info("langgraph_checkpointer_sqlite_file", path=str(p))
    else:
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        logger.debug("langgraph_checkpointer_sqlite_memory")
    return SqliteSaver(conn)


def resolve_sqlite_checkpointer(
    conn: sqlite3.Connection | None = None,
) -> SqliteSaver:
    """
    Resolve SQLite checkpointer: explicit ``conn``, ``AI_TEAM_LANGGRAPH_SQLITE_PATH``, or memory.
    """
    if conn is not None:
        return SqliteSaver(conn)
    path = (os.environ.get("AI_TEAM_LANGGRAPH_SQLITE_PATH") or "").strip()
    if path:
        return build_sqlite_saver(path)
    return build_sqlite_saver(None)


def run_with_postgres_checkpointer(
    postgres_uri: str,
    fn: Callable[[BaseCheckpointSaver], T],
) -> T:
    """
    Run ``fn(checkpointer)`` inside ``PostgresSaver`` after ``setup()``.

    Use when ``AI_TEAM_LANGGRAPH_POSTGRES_URI`` is set for production.
    """
    from langgraph.checkpoint.postgres import PostgresSaver

    with PostgresSaver.from_conn_string(postgres_uri) as checkpointer:
        checkpointer.setup()
        return fn(checkpointer)
