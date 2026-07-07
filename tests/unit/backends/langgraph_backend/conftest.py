"""LangGraph test isolation: skip post-run writes and redirect output dir."""

from __future__ import annotations

from pathlib import Path

import pytest
from ai_team.config.settings import reload_settings


@pytest.fixture(autouse=True)
def _langgraph_test_isolation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AI_TEAM_SKIP_POST_RUN", "1")
    out = tmp_path / "output"
    out.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PROJECT_OUTPUT_DIR", str(out))
    reload_settings()
