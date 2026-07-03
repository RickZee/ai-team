"""
AI-Team Monitor — thread-safe event collector for multi-agent execution.

Collects agent activity, phase progress, guardrail results, and execution
metrics. Consumers render it themselves (web dashboard serializes it over
WebSocket; the CLI prints a plain summary on stop).

Historical note: this used to be a Rich ``Live`` full-screen terminal
dashboard. The rendering layer was removed with the showcase axe
(SHOWCASE_PLAN 3.3) — Rich live consoles in agent runtimes were the
project's single most persistent bug class (deadlocks and infinite
recursion in non-TTY contexts, see docs/journal/2026-06-25.md and the
CrewAI console saga), and the web dashboard is the demo surface.

Usage::

    from ai_team.monitor import TeamMonitor, MonitorCallback

    monitor = TeamMonitor(project_name="My Project")
    monitor.start()
    # ... run flow, call monitor.on_phase_change(), monitor.on_agent_start(), etc. ...
    monitor.stop()

With CrewAI callback adapter::

    cb = MonitorCallback(monitor)
    crew = Crew(..., step_callback=cb.on_step, task_callback=cb.on_task)
"""

from __future__ import annotations

import contextlib
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class Phase(str, Enum):
    """Monitor pipeline phase (subset of flow phases for display)."""

    INTAKE = "intake"
    PLANNING = "planning"
    DEVELOPMENT = "development"
    TESTING = "testing"
    DEPLOYMENT = "deployment"
    COMPLETE = "complete"
    ERROR = "error"


PHASE_ORDER: list[Phase] = [
    Phase.INTAKE,
    Phase.PLANNING,
    Phase.DEVELOPMENT,
    Phase.TESTING,
    Phase.DEPLOYMENT,
    Phase.COMPLETE,
]
PHASE_ICONS: dict[Phase, str] = {
    Phase.INTAKE: "📥",
    Phase.PLANNING: "📋",
    Phase.DEVELOPMENT: "💻",
    Phase.TESTING: "🧪",
    Phase.DEPLOYMENT: "🚀",
    Phase.COMPLETE: "✅",
    Phase.ERROR: "❌",
}

AGENT_ICONS: dict[str, str] = {
    "manager": "👔",
    "product_owner": "📝",
    "architect": "🏗️",
    "backend_developer": "⚙️",
    "frontend_developer": "🎨",
    "devops": "🔧",
    "cloud_engineer": "☁️",
    "qa_engineer": "🔍",
}


@dataclass
class AgentStatus:
    """Tracks the current state of a single agent."""

    role: str
    status: str = "idle"  # idle | working | done | error
    current_task: str = ""
    tasks_completed: int = 0
    last_active: datetime | None = None
    model: str = ""


@dataclass
class GuardrailEvent:
    """A single guardrail check result."""

    timestamp: datetime
    category: str  # behavioral | security | quality
    name: str
    status: str  # pass | fail | warn
    message: str = ""


@dataclass
class LogEntry:
    """A single activity log line."""

    timestamp: datetime
    agent: str
    message: str
    level: str = "info"  # info | warn | error | success


@dataclass
class Metrics:
    """Aggregate execution metrics."""

    start_time: datetime | None = None
    total_tasks: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    guardrails_passed: int = 0
    guardrails_failed: int = 0
    guardrails_warned: int = 0
    retries: int = 0
    files_generated: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    token_estimate: int = 0
    claude_session_id: str = ""
    claude_cost_usd: float | None = None
    claude_stop_reason: str = ""

    @property
    def elapsed(self) -> timedelta:
        """Time since start_time, or zero if not started."""
        if self.start_time:
            return datetime.now() - self.start_time
        return timedelta(0)

    @property
    def elapsed_str(self) -> str:
        """Human-readable elapsed time."""
        s = int(self.elapsed.total_seconds())
        if s < 60:
            return f"{s}s"
        if s < 3600:
            return f"{s // 60}m {s % 60}s"
        return f"{s // 3600}h {(s % 3600) // 60}m"


# ---------------------------------------------------------------------------
# Monitor core
# ---------------------------------------------------------------------------


class TeamMonitor:
    """
    Real-time terminal dashboard for AI-Team execution.

    Call the on_* methods from your CrewAI callbacks or flow hooks
    to feed data into the monitor.
    """

    MAX_LOG_LINES = 50
    MAX_GUARDRAIL_EVENTS = 20

    def __init__(self, project_name: str = "AI-Team Project") -> None:
        self.project_name = project_name
        self.current_phase: Phase = Phase.INTAKE
        self.agents: dict[str, AgentStatus] = {}
        self.log: list[LogEntry] = []
        self.guardrail_events: list[GuardrailEvent] = []
        self.metrics = Metrics()
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    # -- Lifecycle -----------------------------------------------------------

    def start(self) -> None:
        """Mark the run as started (no rendering — collection only)."""
        self.metrics.start_time = datetime.now()
        self._stop_event.clear()
        self._add_log("system", "Monitor started", "info")

    def stop(self, final_status: str = "complete") -> None:
        """Mark the run as finished and log a plain one-line summary."""
        logger.info(
            "run_summary",
            status=final_status,
            project=self.project_name,
            elapsed=self.metrics.elapsed_str,
            tasks_completed=self.metrics.tasks_completed,
            tasks_failed=self.metrics.tasks_failed,
            files_generated=self.metrics.files_generated,
            guardrails_passed=self.metrics.guardrails_passed,
            guardrails_failed=self.metrics.guardrails_failed,
            tests_passed=self.metrics.tests_passed,
            tests_failed=self.metrics.tests_failed,
        )

    def update(self) -> None:
        """Kept for callers; rendering removed — no-op."""

    # -- Event hooks (call these from your flow/callbacks) -------------------

    def on_claude_result(
        self,
        session_id: str | None,
        cost_usd: float | None,
        stop_reason: str | None = None,
    ) -> None:
        """Record Claude Agent SDK session id and spend for the metrics panel."""
        with self._lock:
            if session_id:
                self.metrics.claude_session_id = session_id
            if cost_usd is not None:
                self.metrics.claude_cost_usd = cost_usd
            if stop_reason:
                self.metrics.claude_stop_reason = stop_reason
            if session_id or cost_usd is not None:
                self._add_log(
                    "claude",
                    f"session={session_id or '—'} cost=${cost_usd if cost_usd is not None else '—'}",
                    "info",
                )
        self.update()

    def on_phase_change(self, phase: str | Phase) -> None:
        """Called when the flow transitions to a new phase."""
        with self._lock:
            if isinstance(phase, Phase):
                self.current_phase = phase
            else:
                with contextlib.suppress(ValueError):
                    self.current_phase = Phase(phase)
            icon = PHASE_ICONS.get(self.current_phase, "")
            self._add_log(
                "system",
                f"Phase → {icon} {self.current_phase.value.upper()}",
                "success",
            )
        self.update()

    def on_agent_start(self, role: str, task: str, model: str = "") -> None:
        """Called when an agent begins working on a task."""
        with self._lock:
            if role not in self.agents:
                self.agents[role] = AgentStatus(role=role, model=model)
            agent = self.agents[role]
            agent.status = "working"
            agent.current_task = task[:80]
            agent.last_active = datetime.now()
            agent.model = model or agent.model
            self._add_log(role, f"Started: {task[:60]}", "info")
        self.update()

    def on_agent_finish(self, role: str, task: str = "") -> None:
        """Called when an agent completes a task."""
        with self._lock:
            if role in self.agents:
                agent = self.agents[role]
                agent.status = "done"
                agent.current_task = ""
                agent.tasks_completed += 1
                agent.last_active = datetime.now()
            self.metrics.tasks_completed += 1
            msg = f"Completed: {task[:60]}" if task else "Task completed"
            self._add_log(role, msg, "success")
        self.update()

    def on_agent_error(self, role: str, error: str) -> None:
        """Called when an agent encounters an error."""
        with self._lock:
            if role in self.agents:
                self.agents[role].status = "error"
                self.agents[role].current_task = f"ERROR: {error[:50]}"
            self.metrics.tasks_failed += 1
            self._add_log(role, f"Error: {error[:80]}", "error")
        self.update()

    def on_guardrail(
        self,
        category: str,
        name: str,
        status: str,
        message: str = "",
    ) -> None:
        """Called when a guardrail check completes."""
        with self._lock:
            evt = GuardrailEvent(
                timestamp=datetime.now(),
                category=category,
                name=name,
                status=status,
                message=message[:80],
            )
            self.guardrail_events.append(evt)
            if len(self.guardrail_events) > self.MAX_GUARDRAIL_EVENTS:
                self.guardrail_events = self.guardrail_events[-self.MAX_GUARDRAIL_EVENTS :]
            if status == "pass":
                self.metrics.guardrails_passed += 1
            elif status == "fail":
                self.metrics.guardrails_failed += 1
            elif status == "warn":
                self.metrics.guardrails_warned += 1
            level = "warn" if status != "pass" else "info"
            self._add_log("guardrail", f"[{category}] {name}: {status.upper()}", level)
        self.update()

    def on_retry(self, role: str, reason: str = "") -> None:
        """Called when a task is retried."""
        with self._lock:
            self.metrics.retries += 1
            self._add_log(role, f"Retry: {reason[:60]}", "warn")
        self.update()

    def on_file_generated(self, path: str) -> None:
        """Called when a file is generated."""
        with self._lock:
            self.metrics.files_generated += 1
            self._add_log("system", f"File: {path}", "info")
        self.update()

    def on_test_result(self, passed: int, failed: int) -> None:
        """Called when test results are available."""
        with self._lock:
            self.metrics.tests_passed = passed
            self.metrics.tests_failed = failed
            status = "success" if failed == 0 else "warn"
            self._add_log("qa_engineer", f"Tests: {passed} passed, {failed} failed", status)
        self.update()

    def on_log(self, agent: str, message: str, level: str = "info") -> None:
        """Generic log entry."""
        with self._lock:
            self._add_log(agent, message, level)
        self.update()

    def on_langgraph_update(self, chunk: dict[str, Any]) -> None:
        """
        Map LangGraph ``stream_mode=updates`` chunks to phase and activity log (Phase 8).

        Each ``chunk`` maps node names to partial state updates.
        """
        with self._lock:
            for node_name, update in chunk.items():
                if not isinstance(update, dict):
                    self._add_log(
                        "langgraph",
                        f"{node_name}: {str(update)[:120]}",
                        "info",
                    )
                    continue
                phase = update.get("current_phase")
                if isinstance(phase, str):
                    try:
                        self.current_phase = Phase(phase)
                    except ValueError:
                        self._add_log(
                            "langgraph",
                            f"{node_name} → {phase}",
                            "info",
                        )
                    else:
                        self._add_log(
                            "langgraph",
                            f"{node_name} → phase {phase}",
                            "success",
                        )
                errs = update.get("errors")
                if isinstance(errs, list) and errs:
                    self._add_log("langgraph", f"{node_name}: {errs[-1]}", "warn")
        self.update()

    # -- Internal rendering --------------------------------------------------

    def _add_log(self, agent: str, message: str, level: str) -> None:
        self.log.append(
            LogEntry(
                timestamp=datetime.now(),
                agent=agent,
                message=message,
                level=level,
            )
        )
        if len(self.log) > self.MAX_LOG_LINES:
            self.log = self.log[-self.MAX_LOG_LINES :]


class MonitorCallback:
    """
    Drop-in callback adapter for CrewAI step_callback / task_callback.

    CrewAI step_callback receives AgentAction or AgentFinish (no .agent);
    task_callback receives TaskOutput (has .agent and .description).
    """

    def __init__(self, monitor: TeamMonitor) -> None:
        self.monitor = monitor

    def on_step(self, step_output: Any) -> None:
        """CrewAI step_callback handler (receives AgentAction or AgentFinish)."""
        try:
            # CrewAI passes formatted_answer with .output (AgentFinish) or .text (both)
            text = (str(getattr(step_output, "output", "") or getattr(step_output, "text", "")))[
                :100
            ]
            agent_role = getattr(step_output, "agent", None)
            if agent_role is not None and hasattr(agent_role, "role"):
                agent_role = agent_role.role
            role_key = (
                str(agent_role).lower().replace(" ", "_") if agent_role is not None else "agent"
            )
            self.monitor.on_agent_start(role_key, text or "Working...")
        except Exception as e:
            structlog.get_logger(__name__).warning("monitor_step_callback_error", error=str(e))

    def on_task(self, task_output: Any) -> None:
        """CrewAI task_callback handler (receives TaskOutput with .agent, .description)."""
        try:
            agent_role = getattr(task_output, "agent", "unknown")
            if hasattr(agent_role, "role"):
                agent_role = agent_role.role
            role_key = str(agent_role).lower().replace(" ", "_")
            task_desc = str(getattr(task_output, "description", ""))[:60]
            self.monitor.on_agent_finish(role_key, task_desc)
        except Exception as e:
            structlog.get_logger(__name__).warning("monitor_task_callback_error", error=str(e))


# ---------------------------------------------------------------------------
# Demo mode — shows the monitor with simulated agent activity
# ---------------------------------------------------------------------------
