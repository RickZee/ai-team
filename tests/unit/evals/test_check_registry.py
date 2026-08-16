"""Check registry and taxonomy coverage validation (tasks 3.2 / 3.5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from evals.checks import all_checks, checks_for, validate_registry_against_taxonomy
from evals.checks.registry import ensure_checks_loaded
from evals.taxonomy.loader import load_taxonomy, write_coverage_md

pytestmark = pytest.mark.eval_unit


class TestCheckRegistry:
    def test_registry_populated(self) -> None:
        ensure_checks_loaded()
        ids = sorted(c.id for c in all_checks())
        assert "CHK-tool-call-emitted" in ids
        assert "CHK-hallucination-density" in ids
        assert len(ids) >= 13

    def test_checks_for_fm001(self) -> None:
        found = checks_for("FM-001")
        assert [c.id for c in found] == ["CHK-tool-call-emitted"]

    def test_validate_registry_against_taxonomy_passes(self) -> None:
        """After 3.3–3.5, every detection:check FM has a registered implementation."""
        errors = validate_registry_against_taxonomy()
        assert errors == [], errors

    def test_coverage_md_lists_all_fms(self, tmp_path: Path) -> None:
        tax = load_taxonomy()
        by_fm: dict[str, list[str]] = {}
        for chk in all_checks():
            if chk.failure_mode_id:
                by_fm.setdefault(chk.failure_mode_id, []).append(chk.id)
        out = write_coverage_md(tax, check_ids_by_fm=by_fm, out_path=tmp_path / "COVERAGE.md")
        text = out.read_text(encoding="utf-8")
        for i in range(1, 11):
            assert f"FM-{i:03d}" in text
        assert "Uncovered" in text
        assert "None" in text or "every check-detected" in text
