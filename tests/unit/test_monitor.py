"""
Unit tests for the real-time monitor: TeamMonitor event hooks, state updates,
Metrics, and MonitorCallback CrewAI adapter. No live TUI is started in tests.
"""

from unittest.mock import MagicMock, patch

from ai_team.monitor import (
    AGENT_ICONS,
    PHASE_ICONS,
    PHASE_ORDER,
    Metrics,
    MonitorCallback,
    Phase,
    TeamMonitor,
)

# -----------------------------------------------------------------------------
# TeamMonitor — construction and event hooks (no start)
# -----------------------------------------------------------------------------


class TestTeamMonitorState:
    """TeamMonitor state updates via event hooks without starting the display."""

    def test_init_default_project_name(self) -> None:
        monitor = TeamMonitor()
        assert monitor.project_name == "AI-Team Project"
        assert monitor.current_phase == Phase.INTAKE
        assert monitor.agents == {}
        assert monitor.log == []
        assert monitor.guardrail_events == []
        assert monitor._live is None

    def test_init_custom_project_name(self) -> None:
        monitor = TeamMonitor(project_name="My App")
        assert monitor.project_name == "My App"

    def test_on_phase_change_string(self) -> None:
        monitor = TeamMonitor()
        monitor.on_phase_change("planning")
        assert monitor.current_phase == Phase.PLANNING
        assert len(monitor.log) >= 1
        assert any("planning" in e.message.lower() for e in monitor.log)

    def test_on_phase_change_phase_enum(self) -> None:
        monitor = TeamMonitor()
        monitor.on_phase_change(Phase.DEVELOPMENT)
        assert monitor.current_phase == Phase.DEVELOPMENT

    def test_on_phase_change_unknown_phase_does_not_raise(self) -> None:
        monitor = TeamMonitor()
        monitor.on_phase_change("planning")
        monitor.on_phase_change("awaiting_human")  # not in Phase enum
        assert monitor.current_phase == Phase.PLANNING

    def test_on_agent_start_and_finish(self) -> None:
        monitor = TeamMonitor()
        monitor.on_agent_start("architect", "Designing system", "deepseek-r1:14b")
        assert "architect" in monitor.agents
        agent = monitor.agents["architect"]
        assert agent.status == "working"
        assert "Designing" in agent.current_task
        assert agent.model == "deepseek-r1:14b"

        monitor.on_agent_finish("architect", "Design complete")
        assert agent.status == "done"
        assert agent.current_task == ""
        assert agent.tasks_completed == 1
        assert monitor.metrics.tasks_completed == 1

    def test_on_guardrail_updates_metrics(self) -> None:
        monitor = TeamMonitor()
        monitor.on_guardrail("security", "code_safety", "pass")
        monitor.on_guardrail("quality", "syntax", "fail", "invalid")
        assert monitor.metrics.guardrails_passed == 1
        assert monitor.metrics.guardrails_failed == 1
        assert len(monitor.guardrail_events) == 2
        assert monitor.guardrail_events[0].category == "security"
        assert monitor.guardrail_events[1].status == "fail"

    def test_on_retry_increments_metrics(self) -> None:
        monitor = TeamMonitor()
        monitor.on_retry("qa_engineer", "test failed")
        assert monitor.metrics.retries == 1
        assert any("Retry" in e.message for e in monitor.log)

    def test_on_file_generated_increments_metrics(self) -> None:
        monitor = TeamMonitor()
        monitor.on_file_generated("src/app.py")
        assert monitor.metrics.files_generated == 1

    def test_on_test_result_updates_metrics(self) -> None:
        monitor = TeamMonitor()
        monitor.on_test_result(passed=10, failed=2)
        assert monitor.metrics.tests_passed == 10
        assert monitor.metrics.tests_failed == 2

    def test_on_log_adds_entry(self) -> None:
        monitor = TeamMonitor()
        monitor.on_log("system", "Custom message", "info")
        assert len(monitor.log) >= 1
        assert any(e.agent == "system" and "Custom" in e.message for e in monitor.log)

    def test_on_agent_error_updates_agent_and_metrics(self) -> None:
        monitor = TeamMonitor()
        monitor.on_agent_start("backend_developer", "Implementing", "qwen2.5-coder")
        monitor.on_agent_error("backend_developer", "Tool timeout")
        assert monitor.agents["backend_developer"].status == "error"
        assert "ERROR" in monitor.agents["backend_developer"].current_task
        assert monitor.metrics.tasks_failed == 1


# -----------------------------------------------------------------------------
# MonitorCallback — CrewAI adapter
# -----------------------------------------------------------------------------


class TestMonitorCallback:
    """MonitorCallback maps CrewAI step/task outputs to monitor hooks."""

    def test_on_step_calls_on_agent_start(self) -> None:
        monitor = TeamMonitor()
        cb = MonitorCallback(monitor)

        step = MagicMock()
        step.agent = MagicMock(role="Backend Developer")
        step.output = "Implementing /health endpoint"

        cb.on_step(step)
        assert "backend_developer" in monitor.agents
        assert monitor.agents["backend_developer"].status == "working"
        assert "Implementing" in monitor.agents["backend_developer"].current_task

    def test_on_task_calls_on_agent_finish(self) -> None:
        monitor = TeamMonitor()
        monitor.on_agent_start("architect", "Designing", "deepseek-r1")
        cb = MonitorCallback(monitor)

        task = MagicMock()
        task.agent = MagicMock(role="Architect")
        task.description = "Produce architecture document"

        cb.on_task(task)
        assert monitor.agents["architect"].status == "done"
        assert monitor.metrics.tasks_completed == 1

    def test_on_step_handles_missing_agent_gracefully(self) -> None:
        monitor = TeamMonitor()
        cb = MonitorCallback(monitor)
        step = object()  # no agent, no output → fallback role "agent"
        cb.on_step(step)
        assert "agent" in monitor.agents


# -----------------------------------------------------------------------------
# Metrics
# -----------------------------------------------------------------------------


class TestMetrics:
    """Metrics elapsed and elapsed_str."""

    def test_elapsed_before_start(self) -> None:
        m = Metrics()
        assert m.start_time is None
        assert m.elapsed.total_seconds() == 0
        assert m.elapsed_str == "0s"

    def test_elapsed_after_start_time_set(self) -> None:
        from datetime import datetime, timedelta

        m = Metrics()
        m.start_time = datetime.now() - timedelta(seconds=65)
        assert m.elapsed.total_seconds() >= 64
        assert "m" in m.elapsed_str or "s" in m.elapsed_str


# -----------------------------------------------------------------------------
# Phase and constants
# -----------------------------------------------------------------------------


class TestMonitorPhaseAndConstants:
    """Phase enum and display constants."""

    def test_phase_order_includes_main_phases(self) -> None:
        assert Phase.INTAKE in PHASE_ORDER
        assert Phase.PLANNING in PHASE_ORDER
        assert Phase.DEVELOPMENT in PHASE_ORDER
        assert Phase.TESTING in PHASE_ORDER
        assert Phase.DEPLOYMENT in PHASE_ORDER
        assert Phase.COMPLETE in PHASE_ORDER

    def test_phase_icons_and_agent_icons_non_empty(self) -> None:
        assert len(PHASE_ICONS) >= 6
        assert "architect" in AGENT_ICONS
        assert "qa_engineer" in AGENT_ICONS


# -----------------------------------------------------------------------------
# TeamMonitor start/stop (mocked Live/Console)
# -----------------------------------------------------------------------------


class TestTeamMonitorLifecycle:
    """start/stop with mocked Rich Live and Console to avoid TUI in CI."""

    def test_start_sets_metrics_start_time_and_adds_log(self) -> None:
        monitor = TeamMonitor(project_name="Lifecycle Test")
        with patch("ai_team.monitor.Live") as mock_live:
            monitor.start()
        assert monitor.metrics.start_time is not None
        assert monitor._live is not None
        mock_live.return_value.start.assert_called_once()

    def test_stop_clears_live_and_prints_summary(self) -> None:
        monitor = TeamMonitor(project_name="Stop Test")
        with patch("ai_team.monitor.Live"), patch("ai_team.monitor.Console") as mock_console:
            monitor.start()
            monitor.stop("complete")
        assert monitor._live is None
        mock_console.return_value.print.assert_called()
