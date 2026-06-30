"""Coverage.py data file paths — keep ``.coverage.*`` out of repo / workspace roots."""

from __future__ import annotations

from pathlib import Path

COVERAGE_DATA_DIRNAME = ".coverage-data"
COVERAGE_DATA_BASENAME = ".coverage"


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


def coverage_subprocess_env(base_dir: Path | None = None, *, suffix: str = "") -> dict[str, str]:
    """Env vars for subprocess pytest/coverage so data lands under ``.coverage-data/``."""
    ensure_coverage_data_dir(base_dir)
    return {"COVERAGE_FILE": str(coverage_data_file(base_dir, suffix=suffix))}
