"""Broader unit tests for ``memory.lessons`` (T1.14): synthetic failures, infra, backlog, thresholds."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from ai_team.config.settings import reload_settings
from ai_team.memory.lessons import (
    FAILURE_PATTERN_TYPE,
    INFRA_PATTERN_TYPE,
    LESSON_PATTERN_TYPE,
    extract_lessons,
    load_role_lessons,
    record_run_failures,
    write_infra_backlog,
)
from ai_team.memory.memory_config import LongTermStore


@pytest.fixture
def tmp_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Temp SQLite path via env (same pattern as ``test_lessons``)."""
    db = tmp_path / "memory.db"
    monkeypatch.setenv("MEMORY_SQLITE_PATH", str(db))
    monkeypatch.setenv("MEMORY_RETENTION_DAYS", "7")
    reload_settings()
    return db


def _failure_record(
    *,
    run_id: str,
    phase: str = "testing",
    error_type: str = "RuntimeError",
    message: str = "boom",
    agent_role: str | None = "backend_developer",
    guardrail: dict | None = None,
    test_signals: dict | None = None,
) -> dict:
    return {
        "run_id": run_id,
        "timestamp": "t",
        "backend": "langgraph",
        "team_profile": "full",
        "phase": phase,
        "agent_role": agent_role,
        "error_type": error_type,
        "message": message,
        "guardrail": guardrail,
        "test_signals": test_signals or {},
        "retry_count": 0,
        "max_retries": 3,
    }


class TestRecordRunFailuresExtended:
    def test_synthetic_record_when_tests_fail_without_errors(self, tmp_settings: Path) -> None:
        state = {
            "current_phase": "testing",
            "errors": [],
            "test_results": {"passed": False, "tests": {"ok": False, "returncode": 1}},
        }
        n = record_run_failures(run_id="s1", backend="langgraph", team_profile="full", state=state)
        assert n == 1
        store = LongTermStore(sqlite_path=str(tmp_settings), retention_days=7)
        rows = store.get_patterns(pattern_type=FAILURE_PATTERN_TYPE, limit=10)
        assert len(rows) == 1
        data = json.loads(rows[0]["content"])
        assert data["error_type"] == "TestFailure"
        assert data["phase"] == "testing"

    def test_multiple_errors_each_persisted(self, tmp_settings: Path) -> None:
        state = {
            "current_phase": "development",
            "errors": [
                {"phase": "development", "type": "A", "message": "first"},
                {"phase": "development", "type": "B", "message": "second"},
            ],
        }
        n = record_run_failures(run_id="m1", backend="crewai", team_profile="full", state=state)
        assert n == 2


class TestExtractLessonsInfraAndThreshold:
    def test_infra_bucket_from_pytest_module_error(self, tmp_settings: Path) -> None:
        store = LongTermStore(sqlite_path=str(tmp_settings), retention_days=7)
        ts = {
            "pytest": {
                "ok": False,
                "output_snippet": "ModuleNotFoundError: No module named 'app'",
            }
        }
        fr = _failure_record(
            run_id="i1",
            message="tests failed",
            test_signals=ts,
        )
        store.add_pattern(FAILURE_PATTERN_TYPE, json.dumps(fr))
        store.add_pattern(FAILURE_PATTERN_TYPE, json.dumps(fr | {"run_id": "i2"}))

        res = extract_lessons(promote_threshold=2, limit=50)
        assert res["infra_flagged"] >= 1
        assert res["promoted"] == 0
        infra = store.get_patterns(pattern_type=INFRA_PATTERN_TYPE, limit=10)
        assert infra

    def test_below_threshold_does_not_promote_lesson(self, tmp_settings: Path) -> None:
        store = LongTermStore(sqlite_path=str(tmp_settings), retention_days=7)
        fr = _failure_record(run_id="u1", message="unique failure")
        store.add_pattern(FAILURE_PATTERN_TYPE, json.dumps(fr))
        res = extract_lessons(promote_threshold=5, limit=50)
        assert res["promoted"] == 0
        lessons = store.get_patterns(pattern_type=LESSON_PATTERN_TYPE, limit=10)
        assert lessons == []


class TestWriteInfraBacklog:
    def test_writes_jsonl_lines(self, tmp_settings: Path, tmp_path: Path) -> None:
        store = LongTermStore(sqlite_path=str(tmp_settings), retention_days=7)
        payload = {"id": "x", "status": "open", "description": "test"}
        store.add_pattern(INFRA_PATTERN_TYPE, json.dumps(payload))
        out = tmp_path / "infra.jsonl"
        n = write_infra_backlog(path=str(out), limit=50)
        assert n == 1
        text = out.read_text(encoding="utf-8").strip()
        assert "open" in text
        roundtrip = json.loads(text)
        assert roundtrip["id"] == "x"


class TestLoadRoleLessonsEdgeCases:
    def test_unknown_role_returns_empty(self, tmp_settings: Path) -> None:
        assert load_role_lessons(agent_role="nonexistent_role_xyz", limit=10) == []
