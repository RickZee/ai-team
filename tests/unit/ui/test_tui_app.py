"""Textual TUI tests for ``AITeamTUI``."""

from __future__ import annotations

import pytest
from ai_team.ui.tui.app import AITeamTUI
from textual.widgets import Header, Select, TabbedContent


class TestTUIStartup:
    async def test_app_starts_and_shows_header(self) -> None:
        app = AITeamTUI()
        async with app.run_test():
            assert app.query_one(Header)

    async def test_tab_navigation(self) -> None:
        app = AITeamTUI()
        async with app.run_test() as pilot:
            await pilot.press("r")
            tc = app.query_one(TabbedContent)
            assert tc.active == "run"
            await pilot.press("d")
            assert tc.active == "dashboard"


class TestTUIBackendDefault:
    async def test_defaults_to_crewai(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AI_TEAM_BACKEND", raising=False)
        app = AITeamTUI()
        async with app.run_test():
            select = app.query_one("#backend-select", Select)
            assert select.value == "crewai"

    async def test_respects_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AI_TEAM_BACKEND", "langgraph")
        app = AITeamTUI()
        async with app.run_test():
            select = app.query_one("#backend-select", Select)
            assert select.value == "langgraph"
