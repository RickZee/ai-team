"""Unit tests for evals.provenance.collect (task 0.3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from evals.provenance import Provenance, collect

pytestmark = pytest.mark.eval_unit


def test_collect_in_repo_populates_all_fields() -> None:
    """In this git repo every provenance field must be populated."""
    prov = collect(cwd=Path.cwd())
    assert isinstance(prov, Provenance)
    assert prov.git_sha and prov.git_sha != "unknown"
    assert isinstance(prov.git_dirty, bool)
    assert prov.python_version
    assert prov.platform
    assert prov.harness_version == "0.1.0"
    assert prov.taxonomy_version
    assert prov.pricing_table_version


def test_collect_without_git_degrades_gracefully(tmp_path: Path) -> None:
    """A directory with no .git yields unknown sha and dirty=True."""
    prov = collect(cwd=tmp_path)
    assert prov.git_sha == "unknown"
    assert prov.git_dirty is True
    assert prov.harness_version == "0.1.0"
    assert prov.python_version
    assert prov.platform
