"""Writes are drafts until commit_pending_drafts promotes them."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conformance.conftest import BACKENDS

pytestmark = pytest.mark.parametrize("thin_run", BACKENDS, indirect=True)


def test_drafts_are_committed(thin_run) -> None:
    workspace = Path(str(thin_run.raw["workspace_dir"]))
    assert (workspace / "calc.py").read_text(encoding="utf-8").startswith("def add")
    assert (workspace / "tests" / "test_calc.py").is_file()
    drafts = workspace / ".harness" / "drafts"
    if drafts.is_dir():
        assert not list(drafts.glob("*.manifest.json"))
    rows_path = workspace / "logs" / "audit.jsonl"
    text = rows_path.read_text(encoding="utf-8")
    assert "commit_write" in text
    assert '"code": "drafted"' in text or '"code":"drafted"' in text
