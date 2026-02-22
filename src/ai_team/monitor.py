"""
AI-Team Monitor — Real-time terminal dashboard for multi-agent execution.

A Rich-based TUI that displays live agent activity, phase progress,
guardrail results, and execution metrics. No extra dependencies beyond
``rich`` (already in project deps).

Usage:
    As a standalone demo (simulated activity)::

        python -m ai_team.monitor

    Integrated into your flow::

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
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import structlog
from rich.align import Align
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

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
        self._live: Live | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    # -- Lifecycle -----------------------------------------------------------

    def start(self) -> None:
        """Start the live-updating terminal display."""
        self.metrics.start_time = datetime.now()
        self._stop_event.clear()
        console = Console()
        self._live = Live(
            self._render(),
            console=console,
            refresh_per_second=2,
            screen=True,
            transient=False,
        )
        self._live.start()
        self._add_log("system", "Monitor started", "info")

    def stop(self, final_status: str = "complete") -> None:
        """Stop the live display and print final summary."""
        if self._live:
            self._live.update(self._render())
            self._live.stop()
            self._live = None
        self._print_summary(final_status)

    def update(self) -> None:
        """Force a display refresh (called automatically by Live)."""
        if self._live:
            self._live.update(self._render())

    # -- Event hooks (call these from your flow/callbacks) -------------------

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

    def _render(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3),
        )
        layout["body"].split_row(
            Layout(name="left", ratio=3),
            Layout(name="right", ratio=2),
        )
        layout["left"].split_column(
            Layout(name="phases", size=6),
            Layout(name="tree", size=8),
            Layout(name="agents", size=12),
            Layout(name="log"),
        )
        layout["right"].split_column(
            Layout(name="metrics", size=14),
            Layout(name="guardrails"),
        )

        layout["header"].update(self._render_header())
        layout["phases"].update(self._render_phases())
        layout["tree"].update(self._render_tree())
        layout["agents"].update(self._render_agents())
        layout["log"].update(self._render_log())
        layout["metrics"].update(self._render_metrics())
        layout["guardrails"].update(self._render_guardrails())
        layout["footer"].update(self._render_footer())

        return layout

    def _render_header(self) -> Panel:
        icon = PHASE_ICONS.get(self.current_phase, "")
        phase_text = f"{icon} {self.current_phase.value.upper()}"
        title = Text.assemble(
            ("🤖 AI-TEAM MONITOR", "bold cyan"),
            ("  │  ", "dim"),
            (self.project_name, "bold white"),
            ("  │  ", "dim"),
            (phase_text, "bold yellow"),
            ("  │  ", "dim"),
            (f"⏱ {self.metrics.elapsed_str}", "bold green"),
        )
        return Panel(Align.center(title), style="cyan", padding=(0, 1))

    def _render_tree(self) -> Panel:
        """Tree-style view: Phase → Crew → current task(s)."""
        phase = self.current_phase
        icon = PHASE_ICONS.get(phase, "")
        crew_name = f"{phase.value.replace('_', ' ').title()} crew"
        lines: list[Text] = []
        lines.append(Text.assemble((f"  {icon} ", "bold"), (phase.value.upper(), "bold yellow")))
        lines.append(Text.assemble(("    └─ ", "dim"), (crew_name, "cyan")))
        working = [(r, a) for r, a in self.agents.items() if a.status == "working"]
        if working:
            for i, (role, agent) in enumerate(working):
                branch = "    ├─ " if i < len(working) - 1 else "    └─ "
                name = role.replace("_", " ").title()
                task = (agent.current_task or "Thinking…")[:48]
                lines.append(
                    Text.assemble(
                        (branch, "dim"),
                        (f"{name}: ", "bold"),
                        (task, "yellow"),
                    )
                )
        else:
            lines.append(Text("        — idle", style="dim italic"))
        return Panel(
            Group(*lines),
            title="[bold]Current activity[/bold]",
            border_style="blue",
            padding=(0, 1),
        )

    def _render_phases(self) -> Panel:
        parts: list[Text] = []
        for i, phase in enumerate(PHASE_ORDER):
            icon = PHASE_ICONS[phase]
            if phase == self.current_phase and phase != Phase.COMPLETE:
                style = "bold yellow"
                marker = "▶"
            elif PHASE_ORDER.index(phase) < PHASE_ORDER.index(self.current_phase):
                style = "bold green"
                marker = "✓"
            else:
                style = "dim"
                marker = "○"
            label = f" {marker} {icon} {phase.value.capitalize()}"
            parts.append(Text(label, style=style))
            if i < len(PHASE_ORDER) - 1:
                parts.append(Text(" → ", style="dim"))
        return Panel(
            Text.assemble(*parts),
            title="[bold]Pipeline[/bold]",
            border_style="blue",
            padding=(0, 1),
        )

    def _render_agents(self) -> Panel:
        table = Table(expand=True, show_header=True, header_style="bold", box=None, padding=(0, 1))
        table.add_column("Agent", width=18)
        table.add_column("Status", width=10)
        table.add_column("Task", ratio=1)
        table.add_column("Done", width=5, justify="right")

        if not self.agents:
            table.add_row(
                "[dim]Waiting for first step…[/dim]",
                "[dim]Crew running[/dim]",
                "[dim]Agents appear after the first LLM response[/dim]",
                "",
            )
        else:
            for role, agent in self.agents.items():
                icon = AGENT_ICONS.get(role, "🤖")
                name = f"{icon} {role.replace('_', ' ').title()}"

                if agent.status == "working":
                    status = Text("● ACTIVE", style="bold yellow")
                elif agent.status == "done":
                    status = Text("● DONE", style="bold green")
                elif agent.status == "error":
                    status = Text("● ERROR", style="bold red")
                else:
                    status = Text("○ IDLE", style="dim")

                task_text = agent.current_task or "—"
                task = Text(task_text, style="dim" if not agent.current_task else "white")
                done = str(agent.tasks_completed)
                table.add_row(name, status, task, done)

        return Panel(
            table,
            title="[bold]Agents[/bold]",
            border_style="green",
            padding=(0, 1),
        )

    def _render_log(self) -> Panel:
        lines: list[Text] = []
        display_log = self.log[-30:]
        for entry in display_log:
            ts = entry.timestamp.strftime("%H:%M:%S")
            icon = AGENT_ICONS.get(entry.agent, "📌")

            if entry.level == "error":
                style = "red"
            elif entry.level == "warn":
                style = "yellow"
            elif entry.level == "success":
                style = "green"
            else:
                style = "white"

            line = Text.assemble(
                (f"{ts} ", "dim"),
                (f"{icon} ", ""),
                (f"{entry.agent:<16} ", "bold"),
                (entry.message, style),
            )
            lines.append(line)

        if not lines:
            lines.append(Text("Waiting for activity...", style="dim italic"))

        return Panel(
            Group(*lines),
            title="[bold]Activity Log[/bold]",
            border_style="yellow",
            padding=(0, 1),
        )

    def _render_metrics(self) -> Panel:
        m = self.metrics
        gr_total = m.guardrails_passed + m.guardrails_failed + m.guardrails_warned

        table = Table(show_header=False, box=None, expand=True, padding=(0, 1))
        table.add_column("Label", style="bold", width=20)
        table.add_column("Value", justify="right")

        table.add_row("Elapsed", f"[cyan]{m.elapsed_str}[/cyan]")
        table.add_row("Tasks completed", f"[green]{m.tasks_completed}[/green]")
        table.add_row(
            "Tasks failed",
            f"[red]{m.tasks_failed}[/red]" if m.tasks_failed else "[dim]0[/dim]",
        )
        table.add_row(
            "Retries",
            f"[yellow]{m.retries}[/yellow]" if m.retries else "[dim]0[/dim]",
        )
        table.add_row("Files generated", f"[blue]{m.files_generated}[/blue]")
        table.add_row("─" * 18, "─" * 6)
        table.add_row("Guardrails total", str(gr_total))
        table.add_row("  ✓ Passed", f"[green]{m.guardrails_passed}[/green]")
        table.add_row(
            "  ✗ Failed",
            f"[red]{m.guardrails_failed}[/red]" if m.guardrails_failed else "[dim]0[/dim]",
        )
        table.add_row(
            "  \u26a0 Warned",
            f"[yellow]{m.guardrails_warned}[/yellow]" if m.guardrails_warned else "[dim]0[/dim]",
        )
        if m.tests_passed or m.tests_failed:
            table.add_row("─" * 18, "─" * 6)
            table.add_row("Tests passed", f"[green]{m.tests_passed}[/green]")
            table.add_row(
                "Tests failed",
                f"[red]{m.tests_failed}[/red]" if m.tests_failed else "[dim]0[/dim]",
            )

        return Panel(
            table,
            title="[bold]Metrics[/bold]",
            border_style="magenta",
            padding=(0, 1),
        )

    def _render_guardrails(self) -> Panel:
        lines = []
        display_events = self.guardrail_events[-15:]
        for evt in display_events:
            ts = evt.timestamp.strftime("%H:%M:%S")
            if evt.status == "pass":
                icon, style = "✓", "green"
            elif evt.status == "fail":
                icon, style = "✗", "bold red"
            else:
                icon, style = "⚠", "yellow"

            cat_short = evt.category[:3].upper()
            line = Text.assemble(
                (f"{ts} ", "dim"),
                (f"{icon} ", style),
                (f"[{cat_short}] ", "dim"),
                (evt.name, style),
            )
            if evt.message and evt.status != "pass":
                line.append(f" — {evt.message[:40]}", style="dim")
            lines.append(line)

        if not lines:
            lines.append(Text("No guardrail checks yet", style="dim italic"))

        return Panel(
            Group(*lines),
            title="[bold]Guardrails[/bold]",
            border_style="red",
            padding=(0, 1),
        )

    def _render_footer(self) -> Panel:
        active_count = sum(1 for a in self.agents.values() if a.status == "working")
        footer = Text.assemble(
            ("Active agents: ", "dim"),
            (str(active_count), "bold cyan"),
            ("  │  ", "dim"),
            ("Ctrl+C to stop", "dim italic"),
        )
        return Panel(Align.center(footer), style="dim", padding=(0, 1))

    def _print_summary(self, status: str) -> None:
        """Print a final summary after the monitor stops."""
        console = Console()
        console.print()

        m = self.metrics
        table = Table(
            title="🤖 AI-Team Execution Summary",
            show_header=False,
            border_style="cyan",
        )
        table.add_column("", style="bold")
        table.add_column("")

        status_style = "bold green" if status == "complete" else "bold red"
        table.add_row("Status", Text(status.upper(), style=status_style))
        table.add_row("Duration", m.elapsed_str)
        table.add_row("Tasks", f"{m.tasks_completed} completed, {m.tasks_failed} failed")
        table.add_row("Files", str(m.files_generated))
        table.add_row("Retries", str(m.retries))
        table.add_row(
            "Guardrails",
            f"{m.guardrails_passed}✓ {m.guardrails_failed}✗ {m.guardrails_warned}⚠",
        )
        if m.tests_passed or m.tests_failed:
            table.add_row("Tests", f"{m.tests_passed} passed, {m.tests_failed} failed")

        console.print(table)
        console.print()


# ---------------------------------------------------------------------------
# CrewAI callback adapter
# ---------------------------------------------------------------------------


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
            text = (
                str(getattr(step_output, "output", "") or getattr(step_output, "text", ""))
            )[:100]
            agent_role = getattr(step_output, "agent", None)
            if agent_role is not None and hasattr(agent_role, "role"):
                agent_role = agent_role.role
            role_key = (
                str(agent_role).lower().replace(" ", "_")
                if agent_role is not None
                else "agent"
            )
            self.monitor.on_agent_start(role_key, text or "Working...")
        except Exception as e:
            structlog.get_logger(__name__).warning(
                "monitor_step_callback_error", error=str(e)
            )

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
            structlog.get_logger(__name__).warning(
                "monitor_task_callback_error", error=str(e)
            )


# ---------------------------------------------------------------------------
# Demo mode — shows the monitor with simulated agent activity
# ---------------------------------------------------------------------------


def _run_demo() -> None:
    """Simulate a full AI-Team run so you can see the monitor in action."""
    monitor = TeamMonitor(project_name="Demo: Flask REST API")
    monitor.start()

    agents = [
        ("manager", "qwen3:14b"),
        ("product_owner", "qwen3:14b"),
        ("architect", "deepseek-r1:14b"),
        ("backend_developer", "qwen2.5-coder:14b"),
        ("qa_engineer", "qwen3:14b"),
        ("devops", "qwen2.5-coder:14b"),
    ]

    try:
        monitor.on_phase_change("intake")
        time.sleep(1)
        monitor.on_log("system", "Received project: Create a Flask REST API", "info")
        time.sleep(0.5)

        monitor.on_phase_change("planning")
        time.sleep(0.5)

        monitor.on_agent_start("manager", "Coordinating planning phase", agents[0][1])
        time.sleep(1)

        monitor.on_agent_start(
            "product_owner", "Gathering requirements from description", agents[1][1]
        )
        time.sleep(1.5)
        monitor.on_guardrail("behavioral", "role_adherence", "pass")
        monitor.on_guardrail("quality", "requirements_completeness", "pass")
        monitor.on_agent_finish("product_owner", "Requirements gathering")
        time.sleep(0.5)

        monitor.on_agent_start("architect", "Designing system architecture", agents[2][1])
        time.sleep(2)
        monitor.on_guardrail("behavioral", "scope_control", "pass")
        monitor.on_guardrail(
            "quality", "architecture_completeness", "warn", "Missing deployment diagram"
        )
        monitor.on_agent_finish("architect", "Architecture design")
        time.sleep(0.5)

        monitor.on_agent_finish("manager", "Planning coordination")

        monitor.on_phase_change("development")
        time.sleep(0.5)

        monitor.on_agent_start(
            "backend_developer", "Implementing Flask routes: /health, /items", agents[3][1]
        )
        time.sleep(2)
        monitor.on_guardrail("security", "code_safety", "pass")
        monitor.on_guardrail("security", "secret_detection", "pass")
        monitor.on_file_generated("app.py")
        time.sleep(0.5)
        monitor.on_file_generated("requirements.txt")
        monitor.on_file_generated("config.py")
        monitor.on_guardrail("quality", "code_quality", "pass")
        monitor.on_agent_finish("backend_developer", "Flask API implementation")
        time.sleep(0.5)

        monitor.on_agent_start("devops", "Creating Dockerfile and CI config", agents[5][1])
        time.sleep(1.5)
        monitor.on_guardrail("security", "code_safety", "pass")
        monitor.on_file_generated("Dockerfile")
        monitor.on_file_generated(".github/workflows/ci.yml")
        monitor.on_agent_finish("devops", "DevOps setup")

        monitor.on_phase_change("testing")
        time.sleep(0.5)

        monitor.on_agent_start("qa_engineer", "Generating test cases for Flask API", agents[4][1])
        time.sleep(1.5)
        monitor.on_file_generated("test_app.py")
        monitor.on_guardrail("quality", "test_coverage", "pass")
        time.sleep(0.5)

        monitor.on_log("qa_engineer", "Running pytest...", "info")
        time.sleep(2)
        monitor.on_test_result(passed=8, failed=1)
        time.sleep(0.5)

        monitor.on_retry("qa_engineer", "1 test failed: test_create_item_validation")
        monitor.on_agent_start(
            "backend_developer", "Fixing validation in POST /items", agents[3][1]
        )
        time.sleep(1.5)
        monitor.on_guardrail("security", "code_safety", "pass")
        monitor.on_agent_finish("backend_developer", "Bug fix: input validation")
        time.sleep(0.5)

        monitor.on_log("qa_engineer", "Re-running pytest...", "info")
        time.sleep(1.5)
        monitor.on_test_result(passed=9, failed=0)
        monitor.on_agent_finish("qa_engineer", "Test suite")

        monitor.on_phase_change("deployment")
        time.sleep(0.5)

        monitor.on_agent_start("devops", "Packaging project with Docker", agents[5][1])
        time.sleep(1.5)
        monitor.on_file_generated("docker-compose.yml")
        monitor.on_guardrail("quality", "docs_validation", "pass")
        monitor.on_file_generated("README.md")
        monitor.on_agent_finish("devops", "Deployment packaging")

        monitor.on_phase_change("complete")
        time.sleep(3)

    except KeyboardInterrupt:
        pass
    finally:
        monitor.stop("complete")


if __name__ == "__main__":
    _run_demo()
