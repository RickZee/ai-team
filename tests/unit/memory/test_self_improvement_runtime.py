"""Tests for the self-improvement runtime wiring (audit gaps #1 and #3).

Covers happy paths, the env-flag toggles, and the adversarial requirement that a
broken self-improvement subsystem never breaks a run.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from ai_team.config.settings import reload_settings
from ai_team.core.result import ProjectResult
from ai_team.memory.memory_config import LongTermStore
from ai_team.memory.self_improvement_runtime import (
    _env_flag,
    _metrics_from_result,
    maybe_extract_lessons_at_startup,
    persist_run_metrics,
)


@pytest.fixture
def tmp_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    sqlite_path = str(tmp_path / "memory.db")
    monkeypatch.setenv("MEMORY_SQLITE_PATH", sqlite_path)
    monkeypatch.setenv("MEMORY_RETENTION_DAYS", "7")
    monkeypatch.setenv("MEMORY_MEMORY_ENABLED", "true")
    reload_settings()
    return sqlite_path


# ---- env flag parsing -------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1", True),
        ("true", True),
        ("YES", True),
        ("on", True),
        ("0", False),
        ("false", False),
        ("no", False),
        ("off", False),
    ],
)
def test_env_flag_parsing(monkeypatch: pytest.MonkeyPatch, value: str, expected: bool) -> None:
    monkeypatch.setenv("AI_TEAM_X", value)
    assert _env_flag("AI_TEAM_X", default=not expected) is expected


def test_env_flag_default_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AI_TEAM_X", raising=False)
    assert _env_flag("AI_TEAM_X", default=True) is True
    assert _env_flag("AI_TEAM_X", default=False) is False


def test_env_flag_garbage_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_TEAM_X", "maybe-ish")
    assert _env_flag("AI_TEAM_X", default=True) is True


# ---- gap #1: auto-extract ---------------------------------------------------


def test_auto_extract_disabled_returns_none(
    tmp_settings: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AI_TEAM_SI_AUTO_EXTRACT", "false")
    assert maybe_extract_lessons_at_startup() is None


def test_auto_extract_enabled_returns_counters(
    tmp_settings: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AI_TEAM_SI_AUTO_EXTRACT", "true")
    result = maybe_extract_lessons_at_startup()
    assert result is not None
    assert {"scanned", "promoted", "infra_flagged"} <= set(result)


def test_auto_extract_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    # Adversarial: extraction itself blows up -> must be swallowed, return None.
    monkeypatch.setenv("AI_TEAM_SI_AUTO_EXTRACT", "true")
    import ai_team.memory.lessons as lessons_mod

    def boom(**_: object) -> dict[str, int]:
        raise RuntimeError("db exploded")

    monkeypatch.setattr(lessons_mod, "extract_lessons", boom)
    assert maybe_extract_lessons_at_startup() is None


# ---- gap #3: metrics extraction + persistence -------------------------------


def test_metrics_from_result_reads_kpis() -> None:
    pr = ProjectResult(
        backend_name="crewai",
        success=True,
        team_profile="smoke",
        raw={"kpis": {"files_generated": 2, "tests_total": 10, "tests_passed_count": 10}},
    )
    metrics = _metrics_from_result(pr)
    assert metrics["run_success"] == 1.0
    assert metrics["files_generated"] == 2.0
    assert metrics["test_pass_rate"] == 1.0


def test_metrics_from_result_handles_partial_pass() -> None:
    pr = ProjectResult(
        backend_name="langgraph",
        success=False,
        raw={"state": {"kpis": {"tests_total": 4, "tests_passed_count": 3}}},
    )
    metrics = _metrics_from_result(pr)
    assert metrics["run_success"] == 0.0
    assert metrics["test_pass_rate"] == 0.75


def test_metrics_from_result_no_division_by_zero() -> None:
    pr = ProjectResult(backend_name="crewai", raw={"kpis": {"tests_total": 0}})
    metrics = _metrics_from_result(pr)
    assert "test_pass_rate" not in metrics


def test_persist_run_metrics_writes_rows(tmp_settings: str) -> None:
    pr = ProjectResult(
        backend_name="crewai",
        success=True,
        raw={"kpis": {"files_generated": 3, "duration_seconds": 42.5}},
    )
    written = persist_run_metrics(pr)
    assert written >= 3  # run_success + files_generated + duration_seconds

    store = LongTermStore(sqlite_path=tmp_settings, retention_days=7)
    series = store.get_metrics_timeseries(metric_name="files_generated")
    assert series and series[-1]["value"] == 3.0
    assert series[-1]["model"] == "crewai"


def test_persist_run_metrics_disabled(tmp_settings: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_TEAM_SI_PERSIST_METRICS", "false")
    pr = ProjectResult(backend_name="crewai", raw={"kpis": {"files_generated": 1}})
    assert persist_run_metrics(pr) == 0


def test_persist_run_metrics_skipped_when_memory_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MEMORY_SQLITE_PATH", str(tmp_path / "m.db"))
    monkeypatch.setenv("MEMORY_MEMORY_ENABLED", "false")
    reload_settings()
    pr = ProjectResult(backend_name="crewai", raw={"kpis": {"files_generated": 1}})
    assert persist_run_metrics(pr) == 0


def test_persist_run_metrics_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    # Adversarial: settings access blows up -> swallowed, returns 0.
    def boom() -> object:
        raise RuntimeError("settings exploded")

    monkeypatch.setattr("ai_team.config.settings.get_settings", boom)
    pr = ProjectResult(backend_name="crewai", raw={"kpis": {"files_generated": 1}})
    assert persist_run_metrics(pr) == 0


def test_timeseries_preserves_order(tmp_settings: str) -> None:
    store = LongTermStore(sqlite_path=tmp_settings, retention_days=7)
    for v in (0.5, 0.75, 1.0):
        store.add_metric(agent_role="_run", model="crewai", metric_name="test_pass_rate", value=v)
    series = store.get_metrics_timeseries(metric_name="test_pass_rate")
    values = [r["value"] for r in series]
    assert values == sorted(values)  # ascending by created_at
    assert os.environ["MEMORY_SQLITE_PATH"] == tmp_settings
