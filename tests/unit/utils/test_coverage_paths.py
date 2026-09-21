"""Tests for coverage data path helpers."""

from __future__ import annotations

import os
from pathlib import Path

from ai_team.tools.coverage_paths import (
    coverage_data_dir,
    coverage_subprocess_env,
    ensure_coverage_data_dir,
    strip_parent_coverage_env,
)


def test_coverage_data_dir_under_base(tmp_path: Path) -> None:
    assert coverage_data_dir(tmp_path) == tmp_path / ".coverage-data"


def test_ensure_creates_directory(tmp_path: Path) -> None:
    data_dir = ensure_coverage_data_dir(tmp_path)
    assert data_dir.is_dir()


def test_subprocess_env_points_under_data_dir(tmp_path: Path) -> None:
    env = coverage_subprocess_env(tmp_path)
    assert env["COVERAGE_FILE"].startswith(str(tmp_path / ".coverage-data"))
    assert env["COV_CORE_DATAFILE"] == ""
    assert env["COVERAGE_PROCESS_START"] == ""


def test_strip_parent_coverage_env_drops_pytest_cov_leaks() -> None:
    dirty = {
        "PATH": "/usr/bin",
        "COV_CORE_DATAFILE": "/tmp/.coverage.parent",
        "COVERAGE_FILE": "/tmp/.coverage.parent",
        "COV_CORE_BRANCH": "enabled",
    }
    cleaned = strip_parent_coverage_env(dirty)
    assert cleaned == {"PATH": "/usr/bin"}
    assert "COV_CORE_DATAFILE" not in strip_parent_coverage_env(os.environ)
