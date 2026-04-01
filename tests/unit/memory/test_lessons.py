from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from ai_team.config.settings import reload_settings
from ai_team.memory.lessons import (
    FAILURE_PATTERN_TYPE,
    LESSON_PATTERN_TYPE,
    extract_lessons,
    load_role_lessons,
    record_run_failures,
)
from ai_team.memory.memory_config import LongTermStore


@pytest.fixture
def tmp_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Point memory.sqlite_path to a temp DB via env var used by get_settings().
    monkeypatch.setenv("MEMORY_SQLITE_PATH", str(tmp_path / "memory.db"))
    monkeypatch.setenv("MEMORY_RETENTION_DAYS", "7")
    reload_settings()


def test_record_run_failures_persists_failure_records(tmp_settings: None) -> None:
    state = {
        "current_phase": "testing",
        "errors": [
            {
                "phase": "testing",
                "type": "GuardrailError",
                "message": "QA Engineer should only write test code, not modify production source.",
                "guardrail": {"phase": "behavioral", "details": {"agent_role": "qa_engineer"}},
            }
        ],
        "test_results": {
            "passed": False,
            "tests": {"returncode": 2, "output": "No module named 'app'"},
        },
    }
    n = record_run_failures(
        run_id="r1", backend="langgraph", team_profile="backend-api", state=state
    )
    assert n == 1

    sqlite_path = os.environ["MEMORY_SQLITE_PATH"]
    store = LongTermStore(sqlite_path=sqlite_path, retention_days=7)
    rows = store.get_patterns(pattern_type=FAILURE_PATTERN_TYPE, limit=10)
    assert rows


def test_extract_lessons_promotes_recurring_failures(
    tmp_settings: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Use the configured sqlite path
    sqlite_path = os.environ["MEMORY_SQLITE_PATH"]
    store = LongTermStore(sqlite_path=sqlite_path, retention_days=7)

    fr = {
        "run_id": "r1",
        "timestamp": "t",
        "backend": "langgraph",
        "team_profile": "backend-api",
        "phase": "testing",
        "agent_role": "qa_engineer",
        "error_type": "GuardrailError",
        "message": "QA Engineer should only write test code, not modify production source.",
        "guardrail": {"phase": "behavioral", "details": {"agent_role": "qa_engineer"}},
        "test_signals": {},
        "retry_count": 0,
        "max_retries": 3,
    }
    store.add_pattern(FAILURE_PATTERN_TYPE, json.dumps(fr))
    store.add_pattern(FAILURE_PATTERN_TYPE, json.dumps(fr | {"run_id": "r2"}))

    res = extract_lessons(promote_threshold=2, limit=50)
    assert res["promoted"] >= 1

    lessons = store.get_patterns(pattern_type=LESSON_PATTERN_TYPE, limit=20)
    assert lessons


def test_load_role_lessons_filters_by_role(
    tmp_settings: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    sqlite_path = os.environ["MEMORY_SQLITE_PATH"]
    store = LongTermStore(sqlite_path=sqlite_path, retention_days=7)
    store.add_pattern(
        LESSON_PATTERN_TYPE,
        json.dumps(
            {
                "lesson_id": "k1",
                "agent_role": "qa_engineer",
                "title": "t",
                "text": "Keep output test-focused.",
                "created_at": "t",
                "evidence_count": 2,
            }
        ),
    )
    store.add_pattern(
        LESSON_PATTERN_TYPE,
        json.dumps(
            {
                "lesson_id": "k2",
                "agent_role": "backend_developer",
                "title": "t",
                "text": "Run pytest in workspace.",
                "created_at": "t",
                "evidence_count": 2,
            }
        ),
    )
    qa = load_role_lessons(agent_role="qa_engineer", limit=10)
    assert len(qa) == 1
    assert qa[0].agent_role == "qa_engineer"
