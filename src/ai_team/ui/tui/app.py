"""
AI-Team TUI — Textual-based terminal dashboard for multi-agent orchestration.

Provides real-time monitoring, backend execution, and comparison views.

Usage:
    ai-team-tui              # Launch the TUI
    ai-team-tui --demo       # Launch with simulated demo data
"""

from __future__ import annotations

import argparse
import contextlib
import json
import time
from datetime import datetime
from pathlib import Path

from ai_team.ui.tui.widgets import (
    ActivityLog,
    AgentTable,
    BackendComparisonTable,
    GuardrailsLog,
    MetricsPanel,
    PhasePipeline,
)
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    RichLog,
    Select,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
)

CSS_PATH = Path(__file__).parent / "app.tcss"


# ---------------------------------------------------------------------------
# Dashboard Tab — real-time monitoring
# ---------------------------------------------------------------------------


class DashboardPane(Container):
    """Main monitoring dashboard with agents, metrics, logs, guardrails."""

    def compose(self) -> ComposeResult:
        with Container(id="dashboard-grid"):
            yield PhasePipeline(id="phase-pipeline")
            with VerticalScroll(id="agents-panel"):
                yield AgentTable(id="agent-table")
            yield MetricsPanel(id="metrics-panel")
            with VerticalScroll(id="log-panel"):
                yield ActivityLog(id="activity-log")
            with VerticalScroll(id="guardrails-panel"):
                yield GuardrailsLog(id="guardrails-log")


# ---------------------------------------------------------------------------
# Run Tab — launch backend execution
# ---------------------------------------------------------------------------


class RunPane(Container):
    """Form to configure and launch a backend run."""

    def compose(self) -> ComposeResult:
        with Vertical(id="run-form"):
            yield Label("Backend")
            yield Select(
                [("LangGraph", "langgraph"), ("CrewAI", "crewai")],
                value="langgraph",
                id="backend-select",
            )
            yield Label("Team Profile")
            yield Input(value="full", id="team-input", placeholder="e.g. full, backend-api")
            yield Label("Project Description")
            yield TextArea(id="description-area")
            yield Label("Complexity")
            yield Select(
                [("Simple", "simple"), ("Medium", "medium"), ("Complex", "complex")],
                value="medium",
                id="complexity-select",
            )
            with Horizontal():
                yield Button("Run", variant="success", id="run-btn")
                yield Button("Estimate Cost", variant="primary", id="estimate-btn")
                yield Button("Demo Mode", variant="warning", id="demo-btn")
        yield RichLog(id="run-output", highlight=True, markup=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        app: AITeamTUI = self.app  # type: ignore[assignment]
        if event.button.id == "run-btn":
            app.start_run()
        elif event.button.id == "estimate-btn":
            app.show_estimate()
        elif event.button.id == "demo-btn":
            app.run_demo()


# ---------------------------------------------------------------------------
# Compare Tab — side-by-side backend comparison
# ---------------------------------------------------------------------------


class ComparePane(Container):
    """Compare CrewAI vs LangGraph execution."""

    def compose(self) -> ComposeResult:
        with Horizontal(id="compare-grid"):
            with VerticalScroll(id="compare-left"):
                yield Static("[bold cyan]CrewAI[/bold cyan]", id="compare-crewai-header")
                yield RichLog(id="compare-crewai-log", highlight=True, markup=True)
            with VerticalScroll(id="compare-right"):
                yield Static("[bold cyan]LangGraph[/bold cyan]", id="compare-lg-header")
                yield RichLog(id="compare-lg-log", highlight=True, markup=True)
        yield BackendComparisonTable(id="compare-summary")


# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------


class AITeamTUI(App):
    """AI-Team Terminal Dashboard — monitor, run, and compare multi-agent backends."""

    TITLE = "AI-Team Dashboard"
    SUB_TITLE = "Multi-Agent Orchestration Monitor"
    CSS_PATH = "app.tcss"

    BINDINGS = [
        Binding("d", "switch_tab('dashboard')", "Dashboard", show=True),
        Binding("r", "switch_tab('run')", "Run", show=True),
        Binding("c", "switch_tab('compare')", "Compare", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    # Reactive state from monitor
    current_phase: reactive[str] = reactive("intake")
    is_running: reactive[bool] = reactive(False)

    def __init__(self, demo_mode: bool = False, **kwargs) -> None:
        super().__init__(**kwargs)
        self._demo_mode = demo_mode
        self._monitor = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(initial="dashboard"):
            with TabPane("Dashboard", id="dashboard"):
                yield DashboardPane()
            with TabPane("Run", id="run"):
                yield RunPane()
            with TabPane("Compare", id="compare"):
                yield ComparePane()
        yield Footer()

    def on_mount(self) -> None:
        if self._demo_mode:
            self.run_demo()

    def action_switch_tab(self, tab_id: str) -> None:
        self.query_one(TabbedContent).active = tab_id

    # -- Monitor integration ---------------------------------------------------

    def _get_or_create_monitor(self, project_name: str = "AI-Team Project"):
        """Get or create a TeamMonitor wired to update TUI widgets."""
        from ai_team.monitor import TeamMonitor

        monitor = TeamMonitor(project_name=project_name)
        self._monitor = monitor
        return monitor

    def _refresh_dashboard(self) -> None:
        """Pull data from monitor and push to widgets."""
        if not self._monitor:
            return
        m = self._monitor

        try:
            pipeline = self.query_one("#phase-pipeline", PhasePipeline)
            pipeline.current_phase = m.current_phase.value
        except Exception:
            pass

        with contextlib.suppress(Exception):
            self.query_one("#agent-table", AgentTable).update_agents(m.agents)

        with contextlib.suppress(Exception):
            self.query_one("#metrics-panel", MetricsPanel).update_metrics(m.metrics)

        with contextlib.suppress(Exception):
            self.query_one("#activity-log", ActivityLog).update_log(m.log)

        with contextlib.suppress(Exception):
            self.query_one("#guardrails-log", GuardrailsLog).update_events(m.guardrail_events)

    # -- Run backend -----------------------------------------------------------

    @work(thread=True, exclusive=True, group="run")
    def start_run(self) -> None:
        """Run selected backend in a worker thread."""
        try:
            backend_name = self.query_one("#backend-select", Select).value
            team_name = self.query_one("#team-input", Input).value or "full"
            description = self.query_one("#description-area", TextArea).text
            complexity = str(self.query_one("#complexity-select", Select).value)
        except Exception:
            return

        if not description.strip():
            self._log_output("[red]Please enter a project description.[/red]")
            return

        self.is_running = True
        self._log_output(f"[cyan]Starting {backend_name} run ({complexity})...[/cyan]")

        try:
            from ai_team.backends.registry import get_backend
            from ai_team.core.team_profile import load_team_profile

            profile = load_team_profile(team_name.strip())
            monitor = self._get_or_create_monitor(description[:50])
            # Don't call monitor.start() — we drive the display ourselves
            monitor.metrics.start_time = datetime.now()
            backend = get_backend(str(backend_name))

            if str(backend_name) == "langgraph":
                self._run_langgraph_stream(backend, description.strip(), profile, monitor)
            else:
                result = backend.run(
                    description.strip(),
                    profile,
                    env=None,
                    monitor=monitor,
                )
                self._log_output(json.dumps(result.model_dump(), indent=2, default=str))

            self.call_from_thread(self._refresh_dashboard)
            self._log_output("[green]Run complete.[/green]")
        except Exception as e:
            self._log_output(f"[red]Error: {e}[/red]")
        finally:
            self.is_running = False

    def _run_langgraph_stream(self, backend, description, profile, monitor) -> None:
        """Stream LangGraph events, updating dashboard in real-time."""
        from ai_team.backends.langgraph_backend.backend import LangGraphBackend

        if not isinstance(backend, LangGraphBackend):
            self._log_output("[red]Expected LangGraph backend.[/red]")
            return

        for ev in backend.iter_stream_events(description, profile, monitor=monitor):
            self._log_output(json.dumps(ev, default=str, indent=2))
            self.call_from_thread(self._refresh_dashboard)

    def _log_output(self, message: str) -> None:
        """Write to the run output log."""

        def _write():
            try:
                log = self.query_one("#run-output", RichLog)
                log.write(message)
            except Exception:
                pass

        self.call_from_thread(_write)

    # -- Cost estimate ---------------------------------------------------------

    @work(thread=True, exclusive=True, group="estimate")
    def show_estimate(self) -> None:
        """Show cost estimate for selected configuration."""
        try:
            complexity = str(self.query_one("#complexity-select", Select).value)
        except Exception:
            complexity = "medium"

        try:
            from ai_team.config.cost_estimator import estimate_run_cost
            from ai_team.config.models import OpenRouterSettings

            settings = OpenRouterSettings()
            rows, total, within_budget = estimate_run_cost(settings, complexity)

            lines = [f"[bold cyan]Cost Estimate ({complexity})[/bold cyan]", ""]
            for r in rows:
                lines.append(f"  {r.role:<24} {r.model_id:<30} ${r.cost_usd:.4f}")
            lines.append(f"\n  [bold]Total (with 20% buffer): ${total:.4f}[/bold]")
            budget_style = "green" if within_budget else "red"
            lines.append(f"  [{budget_style}]Within budget: {within_budget}[/{budget_style}]")

            self._log_output("\n".join(lines))
        except Exception as e:
            self._log_output(f"[red]Estimate error: {e}[/red]")

    # -- Demo mode -------------------------------------------------------------

    @work(thread=True, exclusive=True, group="demo")
    def run_demo(self) -> None:
        """Run simulated demo to show dashboard capabilities."""

        monitor = self._get_or_create_monitor("Demo: Flask REST API")
        monitor.metrics.start_time = datetime.now()
        self.is_running = True
        self._log_output("[cyan]Starting demo simulation...[/cyan]")

        agents = [
            ("manager", "qwen3:14b"),
            ("product_owner", "qwen3:14b"),
            ("architect", "deepseek-r1:14b"),
            ("backend_developer", "qwen2.5-coder:14b"),
            ("qa_engineer", "qwen3:14b"),
            ("devops", "qwen2.5-coder:14b"),
        ]

        def step(fn, delay: float = 0.5):
            fn()
            self.call_from_thread(self._refresh_dashboard)
            time.sleep(delay)

        try:
            step(lambda: monitor.on_phase_change("intake"), 1.0)
            step(
                lambda: monitor.on_log(
                    "system", "Received project: Create a Flask REST API", "info"
                )
            )

            step(lambda: monitor.on_phase_change("planning"))
            step(
                lambda: monitor.on_agent_start(
                    "manager", "Coordinating planning phase", agents[0][1]
                ),
                1.0,
            )

            step(
                lambda: monitor.on_agent_start(
                    "product_owner", "Gathering requirements", agents[1][1]
                ),
                1.5,
            )
            step(lambda: monitor.on_guardrail("behavioral", "role_adherence", "pass"))
            step(lambda: monitor.on_guardrail("quality", "requirements_completeness", "pass"))
            step(lambda: monitor.on_agent_finish("product_owner", "Requirements gathering"))

            step(
                lambda: monitor.on_agent_start(
                    "architect", "Designing system architecture", agents[2][1]
                ),
                2.0,
            )
            step(lambda: monitor.on_guardrail("behavioral", "scope_control", "pass"))
            step(
                lambda: monitor.on_guardrail(
                    "quality", "architecture_completeness", "warn", "Missing deployment diagram"
                )
            )
            step(lambda: monitor.on_agent_finish("architect", "Architecture design"))
            step(lambda: monitor.on_agent_finish("manager", "Planning coordination"))

            step(lambda: monitor.on_phase_change("development"))
            step(
                lambda: monitor.on_agent_start(
                    "backend_developer", "Implementing Flask routes: /health, /items", agents[3][1]
                ),
                2.0,
            )
            step(lambda: monitor.on_guardrail("security", "code_safety", "pass"))
            step(lambda: monitor.on_guardrail("security", "secret_detection", "pass"))
            step(lambda: monitor.on_file_generated("app.py"))
            step(lambda: monitor.on_file_generated("requirements.txt"))
            step(lambda: monitor.on_file_generated("config.py"))
            step(lambda: monitor.on_guardrail("quality", "code_quality", "pass"))
            step(lambda: monitor.on_agent_finish("backend_developer", "Flask API implementation"))

            step(
                lambda: monitor.on_agent_start(
                    "devops", "Creating Dockerfile and CI config", agents[5][1]
                ),
                1.5,
            )
            step(lambda: monitor.on_guardrail("security", "code_safety", "pass"))
            step(lambda: monitor.on_file_generated("Dockerfile"))
            step(lambda: monitor.on_file_generated(".github/workflows/ci.yml"))
            step(lambda: monitor.on_agent_finish("devops", "DevOps setup"))

            step(lambda: monitor.on_phase_change("testing"))
            step(
                lambda: monitor.on_agent_start(
                    "qa_engineer", "Generating test cases", agents[4][1]
                ),
                1.5,
            )
            step(lambda: monitor.on_file_generated("test_app.py"))
            step(lambda: monitor.on_guardrail("quality", "test_coverage", "pass"))
            step(lambda: monitor.on_log("qa_engineer", "Running pytest...", "info"), 2.0)
            step(lambda: monitor.on_test_result(passed=8, failed=1))

            step(
                lambda: monitor.on_retry(
                    "qa_engineer", "1 test failed: test_create_item_validation"
                )
            )
            step(
                lambda: monitor.on_agent_start(
                    "backend_developer", "Fixing validation in POST /items", agents[3][1]
                ),
                1.5,
            )
            step(lambda: monitor.on_guardrail("security", "code_safety", "pass"))
            step(lambda: monitor.on_agent_finish("backend_developer", "Bug fix: input validation"))
            step(lambda: monitor.on_log("qa_engineer", "Re-running pytest...", "info"), 1.5)
            step(lambda: monitor.on_test_result(passed=9, failed=0))
            step(lambda: monitor.on_agent_finish("qa_engineer", "Test suite"))

            step(lambda: monitor.on_phase_change("deployment"))
            step(
                lambda: monitor.on_agent_start(
                    "devops", "Packaging project with Docker", agents[5][1]
                ),
                1.5,
            )
            step(lambda: monitor.on_file_generated("docker-compose.yml"))
            step(lambda: monitor.on_guardrail("quality", "docs_validation", "pass"))
            step(lambda: monitor.on_file_generated("README.md"))
            step(lambda: monitor.on_agent_finish("devops", "Deployment packaging"))

            step(lambda: monitor.on_phase_change("complete"), 2.0)
            self._log_output("[green]Demo complete![/green]")

        except Exception as e:
            self._log_output(f"[red]Demo error: {e}[/red]")
        finally:
            self.is_running = False


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="AI-Team TUI Dashboard")
    parser.add_argument("--demo", action="store_true", help="Start with simulated demo")
    args = parser.parse_args()

    app = AITeamTUI(demo_mode=args.demo)
    app.run()


if __name__ == "__main__":
    main()
