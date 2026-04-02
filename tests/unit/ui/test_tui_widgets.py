"""Widget render tests for ``ui.tui.widgets``."""

from __future__ import annotations

from ai_team.ui.tui.widgets import (
    AgentTable,
    GuardrailsLog,
    MetricsPanel,
    PhasePipeline,
)
from rich.text import Text


class TestPhasePipeline:
    def test_render_returns_text(self) -> None:
        w = PhasePipeline()
        w.current_phase = "planning"
        r = w.render()
        assert isinstance(r, Text)
        assert len(str(r)) > 0

    def test_error_phase_renders(self) -> None:
        w = PhasePipeline()
        w.current_phase = "error"
        r = w.render()
        assert "ERROR" in str(r) or "\u274c" in str(r)


class TestAgentTable:
    def test_empty_state_message(self) -> None:
        w = AgentTable()
        r = w.render()
        assert "Waiting" in str(r)


class TestMetricsPanel:
    def test_render_without_data(self) -> None:
        w = MetricsPanel()
        r = w.render()
        assert isinstance(r, Text)


class TestGuardrailsLog:
    def test_empty_log(self) -> None:
        w = GuardrailsLog()
        r = w.render()
        assert isinstance(r, Text)
