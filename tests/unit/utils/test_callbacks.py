"""Unit tests for callback system: MetricsReport and AITeamCallback."""

import asyncio
from typing import Any
from unittest.mock import MagicMock

import pytest

from ai_team.utils.callbacks import AITeamCallback, MetricsReport


# -----------------------------------------------------------------------------
# MetricsReport
# -----------------------------------------------------------------------------


def test_metrics_report_to_dict_empty() -> None:
    """Empty MetricsReport serializes to dict with default fields."""
    r = MetricsReport()
    d = r.to_dict()
    assert isinstance(d, dict)
    assert d["task_durations_seconds"] == {}
    assert d["task_failure_count"] == 0


def test_metrics_report_to_dict_populated() -> None:
    """Populated MetricsReport round-trips via to_dict."""
    r = MetricsReport(
        task_durations_seconds={"task_a": 1.5},
        token_usage_per_agent={"architect": 100},
        retry_counts_per_task={"task_a": 2},
        guardrail_trigger_count={"code_safety": 1},
        tool_call_counts_per_agent={"backend_dev": 3},
        task_failure_count=1,
    )
    d = r.to_dict()
    assert d["task_durations_seconds"]["task_a"] == 1.5
    assert d["token_usage_per_agent"]["architect"] == 100
    assert d["task_failure_count"] == 1


def test_metrics_report_to_table_empty() -> None:
    """Empty MetricsReport to_table includes header and task failures line."""
    r = MetricsReport()
    t = r.to_table()
    assert "MetricsReport" in t
    assert "Task failures: 0" in t


def test_metrics_report_to_table_populated() -> None:
    """Populated MetricsReport to_table includes all sections."""
    r = MetricsReport(
        task_durations_seconds={"design": 2.0},
        token_usage_per_agent={"po": 50},
        retry_counts_per_phase={"planning": 1},
        tool_call_counts_per_agent={"architect": 2},
    )
    t = r.to_table()
    assert "Task durations" in t
    assert "design" in t
    assert "Token usage" in t
    assert "po" in t
    assert "Retries per phase" in t
    assert "planning" in t
    assert "Tool calls per agent" in t


# -----------------------------------------------------------------------------
# AITeamCallback
# -----------------------------------------------------------------------------


def _make_task(description: str, agent: Any = None) -> Any:
    t = MagicMock()
    t.description = description
    t.agent = agent
    return t


def _make_agent(role: str) -> Any:
    a = MagicMock()
    a.role = role
    return a


def test_callback_on_task_start_and_complete_records_duration() -> None:
    """on_task_start then on_task_complete records task duration in metrics."""
    cb = AITeamCallback(project_id="proj1", phase="planning")
    task = _make_task("Gather requirements")
    agent = _make_agent("product_owner")
    cb.on_task_start(task, agent)
    cb.on_task_complete(task, agent, "Output text here")
    metrics = cb.get_metrics()
    assert "Gather requirements" in metrics.task_durations_seconds
    assert metrics.task_durations_seconds["Gather requirements"] >= 0
    assert metrics.token_usage_per_agent.get("product_owner", 0) > 0


def test_callback_on_task_error_increments_failure_count() -> None:
    """on_task_error increments task_failure_count."""
    cb = AITeamCallback()
    task = _make_task("Some task")
    agent = _make_agent("architect")
    cb.on_task_error(task, agent, ValueError("test error"))
    assert cb.get_metrics().task_failure_count == 1


def test_callback_on_agent_action_increments_tool_calls() -> None:
    """on_agent_action increments tool call count for agent."""
    cb = AITeamCallback()
    agent = _make_agent("backend_dev")
    tool = MagicMock()
    tool.name = "write_file"
    cb.on_agent_action(agent, {"path": "/tmp/x"}, tool)
    cb.on_agent_action(agent, {"path": "/tmp/y"}, tool)
    assert cb.get_metrics().tool_call_counts_per_agent.get("backend_dev", 0) == 2


def test_callback_on_guardrail_trigger_increments_count() -> None:
    """on_guardrail_trigger increments guardrail trigger count."""
    cb = AITeamCallback()
    guardrail = MagicMock()
    guardrail.__name__ = "code_safety_guardrail"
    result = MagicMock()
    result.status = "pass"
    result.message = "OK"
    cb.on_guardrail_trigger(guardrail, result)
    cb.on_guardrail_trigger(guardrail, result)
    assert cb.get_metrics().guardrail_trigger_count.get("code_safety_guardrail", 0) == 2


def test_callback_record_retry() -> None:
    """record_retry updates retry counts for task and phase."""
    cb = AITeamCallback()
    cb.record_retry(task="task_1", phase="development")
    cb.record_retry(task="task_1", phase="development")
    metrics = cb.get_metrics()
    assert metrics.retry_counts_per_task.get("task_1", 0) == 2
    assert metrics.retry_counts_per_phase.get("development", 0) == 2


def test_callback_get_task_callback_invokes_on_task_complete() -> None:
    """get_task_callback() returns a callable that calls on_task_complete."""
    cb = AITeamCallback()
    task = _make_task("Design API", agent=_make_agent("architect"))
    fn = cb.get_task_callback()
    fn(task, "Crew output")
    metrics = cb.get_metrics()
    assert metrics.token_usage_per_agent.get("architect", 0) > 0


@pytest.mark.asyncio
async def test_callback_async_crew_start_complete() -> None:
    """Async crew start/complete do not raise and log."""
    cb = AITeamCallback(project_id="p1", phase="planning", webhook_enabled=False)
    crew = MagicMock()
    crew.name = "PlanningCrew"
    await cb.on_crew_start_async(crew)
    await cb.on_crew_complete_async(crew, "Requirements and architecture done")


@pytest.mark.asyncio
async def test_callback_async_task_lifecycle() -> None:
    """Async task start/complete/error and agent_action work."""
    cb = AITeamCallback()
    task = _make_task("Implement backend")
    agent = _make_agent("backend_dev")
    await cb.on_task_start_async(task, agent)
    await cb.on_task_complete_async(task, agent, "Code written")
    metrics = cb.get_metrics()
    assert "Implement backend" in metrics.task_durations_seconds
    assert metrics.token_usage_per_agent.get("backend_dev", 0) > 0
