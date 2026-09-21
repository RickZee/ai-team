"""Coverage.py data file paths — keep ``.coverage.*`` out of repo / workspace roots."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

COVERAGE_DATA_DIRNAME = ".coverage-data"
COVERAGE_DATA_BASENAME = ".coverage"

# pytest-cov (COV_CORE_*) and coverage.py (COVERAGE_*) leak into child pytest
# via os.environ. Nested runs then write *statement* data into the parent's
# *branch* file and ``coverage combine`` raises DataError.
PARENT_COVERAGE_ENV_KEYS = (
    "COVERAGE_FILE",
    "COVERAGE_PROCESS_START",
    "COV_CORE_SOURCE",
    "COV_CORE_CONFIG",
    "COV_CORE_DATAFILE",
    "COV_CORE_BRANCH",
    "COV_CORE_CONTEXT",
)


def coverage_data_dir(base_dir: Path | None = None) -> Path:
    """Directory for coverage data under *base_dir* (default: cwd)."""
    root = (base_dir or Path.cwd()).resolve()
    return root / COVERAGE_DATA_DIRNAME


def coverage_data_file(base_dir: Path | None = None, *, suffix: str = "") -> Path:
    """Path to the coverage data file (``COVERAGE_FILE`` target)."""
    return coverage_data_dir(base_dir) / f"{COVERAGE_DATA_BASENAME}{suffix}"


def ensure_coverage_data_dir(base_dir: Path | None = None) -> Path:
    """Create ``.coverage-data/`` and return its path."""
    data_dir = coverage_data_dir(base_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def strip_parent_coverage_env(env: Mapping[str, str] | None = None) -> dict[str, str]:
    """Copy *env* (default: ``os.environ``) without parent-suite coverage vars."""
    cleaned = dict(os.environ if env is None else env)
    for key in PARENT_COVERAGE_ENV_KEYS:
        cleaned.pop(key, None)
    return cleaned


def coverage_subprocess_env(base_dir: Path | None = None, *, suffix: str = "") -> dict[str, str]:
    """Env vars for subprocess pytest/coverage so data lands under ``.coverage-data/``."""
    ensure_coverage_data_dir(base_dir)
    env = {key: "" for key in PARENT_COVERAGE_ENV_KEYS}
    env["COVERAGE_FILE"] = str(coverage_data_file(base_dir, suffix=suffix))
    return env
