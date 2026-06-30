"""Tests for coverage data path helpers."""

from __future__ import annotations

from pathlib import Path

from ai_team.utils.coverage_paths import (
    coverage_data_dir,
    coverage_subprocess_env,
    ensure_coverage_data_dir,
)


def test_coverage_data_dir_under_base(tmp_path: Path) -> None:
    assert coverage_data_dir(tmp_path) == tmp_path / ".coverage-data"


def test_ensure_creates_directory(tmp_path: Path) -> None:
    data_dir = ensure_coverage_data_dir(tmp_path)
    assert data_dir.is_dir()


def test_subprocess_env_points_under_data_dir(tmp_path: Path) -> None:
    env = coverage_subprocess_env(tmp_path)
    assert "COVERAGE_FILE" in env
    assert env["COVERAGE_FILE"].startswith(str(tmp_path / ".coverage-data"))
