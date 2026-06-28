"""Custom Textual widgets for the AI-Team TUI dashboard."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

if TYPE_CHECKING:
    from ai_team.monitor import AgentStatus, GuardrailEvent, LogEntry, Metrics


# ---------------------------------------------------------------------------
# Phase pipeline bar
# ---------------------------------------------------------------------------

PHASE_DISPLAY = [
    ("intake", "INTAKE"),
    ("planning", "PLANNING"),
    ("development", "DEVELOPMENT"),
    ("testing", "TESTING"),
    ("deployment", "DEPLOYMENT"),
    ("complete", "COMPLETE"),
]

PHASE_ICONS = {
    "intake": "\u2b07",
    "planning": "\U0001f4cb",
    "development": "\U0001f4bb",
    "testing": "\U0001f9ea",
    "deployment": "\U0001f680",
    "complete": "\u2705",
    "error": "\u274c",
}


class PhasePipeline(Static):
    """Horizontal phase progress indicator."""

    current_phase: reactive[str] = reactive("intake")

    def render(self) -> Text:
        parts: list[tuple[str, str]] = []
        phase_names = [p[0] for p in PHASE_DISPLAY]
        current_idx = (
            phase_names.index(self.current_phase) if self.current_phase in phase_names else -1
        )

        for i, (key, label) in enumerate(PHASE_DISPLAY):
            icon = PHASE_ICONS.get(key, "")
            if self.current_phase == "error":
                style = "bold red" if key == "complete" else "dim"
                marker = "\u2717" if key == "complete" else "\u25cb"
            elif key == self.current_phase and key != "complete":
                style = "bold yellow"
                marker = "\u25b6"
            elif i < current_idx or key == self.current_phase == "complete":
                style = "bold green"
                marker = "\u2713"
            else:
                style = "dim"
                marker = "\u25cb"
            parts.append((f" {marker} {icon} {label} ", style))
            if i < len(PHASE_DISPLAY) - 1:
                parts.append((" \u2192 ", "dim"))

        if self.current_phase == "error":
            parts.append((" \u2192 ", "dim"))
            parts.append((f" \u2717 {PHASE_ICONS['error']} ERROR ", "bold red"))

        return Text.assemble(*parts)


# ---------------------------------------------------------------------------
# Agent table
# ---------------------------------------------------------------------------

AGENT_ICONS = {
    "manager": "\U0001f454",
    "product_owner": "\U0001f4dd",
    "architect": "\U0001f3d7\ufe0f",
    "backend_developer": "\u2699\ufe0f",
    "frontend_developer": "\U0001f3a8",
    "fullstack_developer": "\U0001f528",
    "devops": "\U0001f527",
    "cloud_engineer": "\u2601\ufe0f",
    "qa_engineer": "\U0001f50d",
}

STATUS_STYLES = {
    "working": ("bold yellow", "\u25cf ACTIVE"),
    "done": ("bold green", "\u25cf DONE"),
    "error": ("bold red", "\u25cf ERROR"),
    "idle": ("dim", "\u25cb IDLE"),
}


class AgentTable(Static):
    """Displays agent statuses in a table."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._agents: dict[str, AgentStatus] = {}

    def update_agents(self, agents: dict[str, AgentStatus]) -> None:
        self._agents = agents
        self.refresh()

    def render(self) -> Text:
        if not self._agents:
            return Text("  Waiting for agents...", style="dim italic")

        lines: list[Text] = []
        header = Text.assemble(
            ("  Agent", "bold"),
            (" " * 16, ""),
            ("Status", "bold"),
            (" " * 6, ""),
            ("Task", "bold"),
            (" " * 20, ""),
            ("Done", "bold"),
        )
        lines.append(header)
        lines.append(Text("  " + "\u2500" * 70, style="dim"))

        for role, agent in self._agents.items():
            icon = AGENT_ICONS.get(role, "\U0001f916")
            name = f"  {icon} {role.replace('_', ' ').title()}"
            style, status_text = STATUS_STYLES.get(agent.status, ("dim", "\u25cb IDLE"))
            task = (agent.current_task or "\u2014")[:35]
            done = str(agent.tasks_completed)

            line = Text()
            line.append(f"{name:<24}", style="bold")
            line.append(f"{status_text:<14}", style=style)
            line.append(f"{task:<38}", style="white" if agent.current_task else "dim")
            line.append(f"{done:>4}", style="cyan")
            lines.append(line)

        return Text("\n").join(lines)


# ---------------------------------------------------------------------------
# Activity log
# ---------------------------------------------------------------------------

LOG_LEVEL_STYLES = {
    "error": "red",
    "warn": "yellow",
    "success": "green",
    "info": "white",
}


class ActivityLog(Static):
    """Scrolling activity log."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._entries: list[LogEntry] = []

    def update_log(self, entries: list[LogEntry]) -> None:
        self._entries = entries[-30:]
        self.refresh()

    def render(self) -> Text:
        if not self._entries:
            return Text("  Waiting for activity...", style="dim italic")

        lines: list[Text] = []
        for entry in self._entries:
            ts = entry.timestamp.strftime("%H:%M:%S")
            icon = AGENT_ICONS.get(entry.agent, "\U0001f4cc")
            style = LOG_LEVEL_STYLES.get(entry.level, "white")
            line = Text.assemble(
                (f"  {ts} ", "dim"),
                (f"{icon} ", ""),
                (f"{entry.agent:<16} ", "bold"),
                (entry.message, style),
            )
            lines.append(line)
        return Text("\n").join(lines)


# ---------------------------------------------------------------------------
# Metrics panel
# ---------------------------------------------------------------------------


class MetricsPanel(Static):
    """Key execution metrics."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._metrics: Metrics | None = None

    def update_metrics(self, metrics: Metrics) -> None:
        self._metrics = metrics
        self.refresh()

    def render(self) -> Text:
        if not self._metrics:
            return Text("  No data yet", style="dim")

        m = self._metrics
        gr_total = m.guardrails_passed + m.guardrails_failed + m.guardrails_warned

        lines: list[Text] = []

        def row(label: str, value: str, style: str = "white") -> None:
            lines.append(
                Text.assemble(
                    (f"  {label:<20}", "bold"),
                    (f"{value:>8}", style),
                )
            )

        row("Elapsed", m.elapsed_str, "cyan")
        row("Tasks completed", str(m.tasks_completed), "green")
        row("Tasks failed", str(m.tasks_failed), "red" if m.tasks_failed else "dim")
        if m.retries:
            row("Retries", f"✓ Self-corrected ×{m.retries}", "green")
        else:
            row("Retries", str(m.retries), "dim")
        row("Files generated", str(m.files_generated), "blue")
        lines.append(Text("  " + "\u2500" * 28, style="dim"))
        row("Guardrails total", str(gr_total))
        row("  \u2713 Passed", str(m.guardrails_passed), "green")
        row("  \u2717 Failed", str(m.guardrails_failed), "red" if m.guardrails_failed else "dim")
        row("  \u26a0 Warned", str(m.guardrails_warned), "yellow" if m.guardrails_warned else "dim")

        if m.tests_passed or m.tests_failed:
            lines.append(Text("  " + "\u2500" * 28, style="dim"))
            row("Tests passed", str(m.tests_passed), "green")
            row("Tests failed", str(m.tests_failed), "red" if m.tests_failed else "dim")

        return Text("\n").join(lines)


# ---------------------------------------------------------------------------
# Guardrails log
# ---------------------------------------------------------------------------


class GuardrailsLog(Static):
    """Recent guardrail check results."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._events: list[GuardrailEvent] = []

    def update_events(self, events: list[GuardrailEvent]) -> None:
        self._events = events[-15:]
        self.refresh()

    def render(self) -> Text:
        if not self._events:
            return Text("  No guardrail checks yet", style="dim italic")

        lines: list[Text] = []
        for evt in self._events:
            ts = evt.timestamp.strftime("%H:%M:%S")
            if evt.status == "pass":
                icon, style = "\u2713", "green"
            elif evt.status == "fail":
                icon, style = "\u2717", "bold red"
            else:
                icon, style = "\u26a0", "yellow"

            cat_short = evt.category[:3].upper()
            line = Text.assemble(
                (f"  {ts} ", "dim"),
                (f"{icon} ", style),
                (f"[{cat_short}] ", "dim"),
                (evt.name, style),
            )
            if evt.message and evt.status != "pass":
                line.append(f" \u2014 {evt.message[:40]}", style="dim")
            lines.append(line)

        return Text("\n").join(lines)


# ---------------------------------------------------------------------------
# Backend comparison widget
# ---------------------------------------------------------------------------


class BackendComparisonTable(Static):
    """Side-by-side backend comparison with direction hints."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._data: dict[str, dict] = {}
        self._verdict: str = ""

    def update_comparison(self, data: dict[str, dict], verdict: str = "") -> None:
        self._data = data
        self._verdict = verdict
        self.refresh()

    def render(self) -> Text:
        if not self._data:
            return Text("  Run backends to see comparison...", style="dim italic")

        lines: list[Text] = []
        if self._verdict:
            lines.append(Text(f"  {self._verdict}", style="bold cyan"))
            lines.append(Text(""))

        backends = list(self._data.keys())

        # Header
        header = Text("  ")
        header.append(f"{'Metric':<22}", style="bold")
        for b in backends:
            header.append(f"{b:>16}", style="bold cyan")
        lines.append(header)
        lines.append(Text("  " + "\u2500" * (22 + 16 * len(backends)), style="dim"))

        # Rows
        all_keys = set()
        for d in self._data.values():
            all_keys.update(d.keys())

        for key in sorted(all_keys):
            row = Text("  ")
            row.append(f"{key:<22}", style="bold")
            for b in backends:
                val = self._data.get(b, {}).get(key, "\u2014")
                row.append(f"{str(val):>16}", style="white")
            lines.append(row)

        return Text("\n").join(lines)


class AgentTimeline(Static):
    """Agent handoff timeline derived from monitor agents."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._agents: dict[str, AgentStatus] = {}
        self._phase: str = "intake"
        self._retries: int = 0

    def update_timeline(
        self,
        agents: dict[str, AgentStatus],
        phase: str,
        retries: int = 0,
    ) -> None:
        self._agents = agents
        self._phase = phase
        self._retries = retries
        self.refresh()

    def render(self) -> Text:
        if not self._agents:
            return Text("  Waiting for agents...", style="dim italic")

        lines: list[Text] = []
        phases = ["intake", "planning", "development", "testing", "deployment"]
        phase_line = Text("  Phases: ", style="bold")
        for i, p in enumerate(phases):
            style = "bold yellow" if p == self._phase else "dim"
            if self._phase in phases and phases.index(self._phase) > i:
                style = "green"
            phase_line.append(f"{p} ", style)
        lines.append(phase_line)

        if self._retries:
            lines.append(Text(f"  ✓ Self-corrected ×{self._retries}", style="green"))

        active = next((a for a in self._agents.values() if a.status == "working"), None)
        if active:
            lines.append(
                Text(f"  Current owner: {active.role.replace('_', ' ')}", style="bold cyan")
            )

        for role, agent in self._agents.items():
            icon = AGENT_ICONS.get(role, "\U0001f916")
            style, status_text = STATUS_STYLES.get(agent.status, ("dim", "\u25cb IDLE"))
            task = (agent.current_task or "")[:40]
            line = Text.assemble(
                (f"  {icon} {role.replace('_', ' '):<20} ", "bold"),
                (status_text, style),
                (f"  {task}", "dim" if not task else "white"),
            )
            lines.append(line)

        return Text("\n").join(lines)


class RunSummaryPanel(Static):
    """Terminal run summary (estimate vs actual when available)."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._run: dict | None = None
        self._monitor: dict | None = None

    def update_summary(self, run: dict | None, monitor: dict | None) -> None:
        self._run = run
        self._monitor = monitor
        self.refresh()

    def render(self) -> Text:
        if not self._run or not self._monitor:
            return Text("")

        run = self._run
        monitor = self._monitor
        lines: list[Text] = []
        lines.append(Text("  Run summary", style="bold underline"))
        lines.append(Text(f"  Outcome: {run.get('status', '—')}", style="bold"))
        lines.append(Text(f"  Backend: {run.get('backend')} · Profile: {run.get('profile')}"))
        lines.append(Text(f"  Elapsed: {monitor.get('elapsed', '—')}", style="cyan"))

        estimate = run.get("estimate_usd")
        actual = monitor.get("cost_usd")
        if run.get("backend") != "demo":
            if actual is not None:
                cost = f"  Actual ${float(actual):.4f}"
                if estimate is not None:
                    delta = float(actual) - float(estimate)
                    cost += f" · Est ${float(estimate):.4f} ({delta:+.4f})"
                lines.append(Text(cost))
            elif estimate is not None:
                lines.append(
                    Text(f"  Est ${float(estimate):.4f} (actual not recorded)", style="dim")
                )
            else:
                lines.append(Text("  estimate not run", style="dim"))

        if run.get("error"):
            lines.append(Text(f"  Error: {run['error']}", style="red"))
        return Text("\n").join(lines)
