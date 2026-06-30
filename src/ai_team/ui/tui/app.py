"""
AI-Team TUI — Textual terminal dashboard with full parity to the web UI.

When ``ai-team-web`` is running, the TUI uses the same REST + WebSocket API as
the React dashboard (run history, cancel/delete, HITL, compare, artifacts).
Local execution remains as a fallback when the API is unreachable.

Usage:
    ai-team-web &           # recommended — enables full parity
    ai-team-tui             # connect to http://127.0.0.1:8421
    ai-team-tui --local     # force offline/local mode
    ai-team-tui --demo      # auto-start sample run
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import time
from datetime import datetime
from typing import Any

from ai_team.ui.api_client import DEFAULT_API_BASE, DashboardApiClient
from ai_team.ui.compare_summary import build_compare_verdict, monitor_metric_rows
from ai_team.ui.tui.widgets import (
    ActivityLog,
    AgentTable,
    AgentTimeline,
    BackendComparisonTable,
    GuardrailsLog,
    MetricsPanel,
    PhasePipeline,
    RunSummaryPanel,
)
from ai_team.ui.ws_client import run_monitor_sync, run_start_sync
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    RichLog,
    Select,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
)

SAMPLE_RUN_LABEL = "Play sample run (free · no files)"
TERMINAL_STATUSES = {"complete", "error", "cancelled"}
LIVE_STATUSES = {"running", "awaiting_human", "cancelling"}


def _flatten_tree(nodes: list[dict[str, Any]], prefix: str = "") -> list[tuple[str, str]]:
    """Return (label, path) pairs from an artifact tree."""
    out: list[tuple[str, str]] = []
    for node in nodes:
        path = node.get("path") or node.get("name", "")
        label = f"{prefix}{node.get('name', path)}"
        if node.get("type") == "file":
            out.append((label, path))
        for child in node.get("children") or []:
            out.extend(_flatten_tree([child], prefix=f"{label}/"))
    return out


class DashboardPane(Vertical):
    """Dashboard with run sidebar + live monitor (web parity)."""

    def compose(self) -> ComposeResult:
        yield Static("", id="connection-banner")
        yield Static("", id="hitl-banner")
        with Horizontal(id="dashboard-layout"):
            with Vertical(id="run-sidebar"):
                yield Label("Runs")
                yield Input(placeholder="Search runs…", id="run-search")
                yield Select(
                    [
                        ("All statuses", ""),
                        ("Running", "running"),
                        ("Awaiting human", "awaiting_human"),
                        ("Complete", "complete"),
                        ("Error", "error"),
                        ("Cancelled", "cancelled"),
                    ],
                    id="run-status-filter",
                    value="",
                )
                yield ListView(id="run-list")
                yield Static(
                    "[dim]s[/] stop · [dim]x[/] delete · [dim]r[/] retry · [dim]e[/] edit",
                    id="run-sidebar-hints",
                )
            with VerticalScroll(id="dashboard-main"):
                yield PhasePipeline(id="phase-pipeline")
                yield AgentTimeline(id="agent-timeline")
                yield RunSummaryPanel(id="run-summary")
                with Horizontal(id="dashboard-panels"):
                    with VerticalScroll(id="agents-panel"):
                        yield AgentTable(id="agent-table")
                    yield MetricsPanel(id="metrics-panel")
                with Horizontal(id="dashboard-log-row"):
                    with VerticalScroll(id="log-panel"):
                        yield ActivityLog(id="activity-log")
                    with VerticalScroll(id="guardrails-panel"):
                        yield GuardrailsLog(id="guardrails-log")
                yield Static("", id="how-it-works")
                with Vertical(id="hitl-panel", classes="hidden"):
                    yield Label("Human review required")
                    yield TextArea(id="hitl-feedback")
                    with Horizontal():
                        yield Button("Approve", id="hitl-approve", variant="success")
                        yield Button("Request changes", id="hitl-changes", variant="warning")
                        yield Button("Reject", id="hitl-reject", variant="error")
                        yield Button("Submit", id="hitl-submit", variant="primary")


class RunPane(Vertical):
    """Launch form — mirrors web Run page."""

    def compose(self) -> ComposeResult:
        with Vertical(id="run-form"):
            yield Label("Backend")
            yield Select(
                [
                    ("LangGraph", "langgraph"),
                    ("CrewAI", "crewai"),
                    ("Claude Agent SDK", "claude-agent-sdk"),
                ],
                id="backend-select",
                value="langgraph",
            )
            yield Static("", id="backend-key-hint")
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
                yield Button(SAMPLE_RUN_LABEL, variant="warning", id="demo-btn")
            yield Static(
                "Sample runs simulate agent activity with no files or cost.", id="demo-helper"
            )
        yield RichLog(id="run-output", highlight=True, markup=True)


class ComparePane(Vertical):
    """Three-way backend comparison (web parity)."""

    def compose(self) -> ComposeResult:
        with Vertical(id="compare-form"):
            yield Label("Team Profile")
            yield Input(value="full", id="compare-profile")
            yield Label("Complexity")
            yield Select(
                [("Simple", "simple"), ("Medium", "medium"), ("Complex", "complex")],
                value="medium",
                id="compare-complexity",
            )
            yield Label("Project Description")
            yield TextArea(id="compare-description")
            with Horizontal():
                yield Button("Run All Backends", variant="success", id="compare-submit")
                yield Button(SAMPLE_RUN_LABEL, variant="warning", id="compare-demo")
                yield Button("Estimate Cost", id="compare-estimate")
        with Horizontal(id="compare-grid"):
            with VerticalScroll(id="compare-crewai"):
                yield Static("[bold]CrewAI[/bold]", id="compare-crewai-header")
                yield RichLog(id="compare-crewai-log", highlight=True)
            with VerticalScroll(id="compare-langgraph"):
                yield Static("[bold]LangGraph[/bold]", id="compare-lg-header")
                yield RichLog(id="compare-lg-log", highlight=True)
            with VerticalScroll(id="compare-claude"):
                yield Static("[bold]Claude Agent SDK[/bold]", id="compare-claude-header")
                yield RichLog(id="compare-claude-log", highlight=True)
        yield BackendComparisonTable(id="compare-summary")


class ArtifactsPane(Vertical):
    """Artifact browser — files, tests summary, architecture snippet."""

    def compose(self) -> ComposeResult:
        yield Label("Project")
        yield Select([], id="artifact-project-select")
        with Horizontal(id="artifacts-layout"):
            with VerticalScroll(id="artifact-files-panel"):
                yield Label("Files")
                yield ListView(id="artifact-file-list")
            with VerticalScroll(id="artifact-content-panel"):
                yield Static("Select a project and file.", id="artifact-content")
                yield Static("", id="artifact-tests")
                yield Static("", id="artifact-architecture")


class AITeamTUI(App):
    """AI-Team terminal dashboard — full parity with ai-team-web when API is up."""

    TITLE = "AI-Team Dashboard"
    SUB_TITLE = "Multi-Agent Orchestration Monitor"
    CSS_PATH = "app.tcss"

    BINDINGS = [
        Binding("d", "switch_tab('dashboard')", "Dashboard", show=True),
        Binding("n", "switch_tab('run')", "Run", show=True),
        Binding("c", "switch_tab('compare')", "Compare", show=True),
        Binding("a", "switch_tab('artifacts')", "Artifacts", show=True),
        Binding("s", "stop_selected_run", "Stop", show=True),
        Binding("x", "delete_selected_run", "Delete", show=True),
        Binding("r", "retry_run", "Retry", show=True),
        Binding("e", "edit_rerun", "Edit", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    current_phase: reactive[str] = reactive("intake")
    is_running: reactive[bool] = reactive(False)
    api_connected: reactive[bool] = reactive(False)

    def __init__(
        self,
        demo_mode: bool = False,
        api_url: str | None = None,
        force_local: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._demo_mode = demo_mode
        self._force_local = force_local
        self._api_url = api_url or DEFAULT_API_BASE
        self._api: DashboardApiClient | None = None
        self._monitor = None
        self._runs: list[dict[str, Any]] = []
        self._selected_run_id: str | None = None
        self._selected_monitor: dict[str, Any] | None = None
        self._last_estimate_usd: float | None = None
        self._compare_results: dict[str, dict[str, Any]] = {}
        self._watch_worker_active = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(initial="dashboard"):
            with TabPane("Dashboard", id="dashboard"):
                yield DashboardPane()
            with TabPane("Run", id="run"):
                yield RunPane()
            with TabPane("Compare", id="compare"):
                yield ComparePane()
            with TabPane("Artifacts", id="artifacts"):
                yield ArtifactsPane()
        yield Footer()

    def on_mount(self) -> None:
        if not self._force_local:
            self._api = DashboardApiClient(self._api_url)
            self.api_connected = self._api.is_available()
        self._set_connection_banner()
        if self.api_connected:
            self._load_catalog()
            self._refresh_run_list()
            self.set_interval(2.0, self._poll_runs_tick)
            self.set_interval(0.5, self._refresh_title_tick)
        else:
            self._init_local_backend_select()
            self._show_how_it_works(True)
        if self._demo_mode:
            if self.api_connected:
                self.run_sample_via_api()
            else:
                self.run_demo()

    def on_unmount(self) -> None:
        if self._api:
            self._api.close()

    def _set_connection_banner(self) -> None:
        banner = self.query_one("#connection-banner", Static)
        if self.api_connected:
            banner.update(f"[green]Connected[/green] to {self._api_url} — full web parity")
        else:
            banner.update(
                "[yellow]Offline mode[/yellow] — start [bold]ai-team-web[/] for run history, "
                "cancel/delete, compare, artifacts, and HITL resume."
            )

    def _show_how_it_works(self, show: bool) -> None:
        widget = self.query_one("#how-it-works", Static)
        if not show:
            widget.update("")
            return
        widget.update(
            "[bold]How it works[/bold]\n"
            "1. Describe a project on Run\n"
            "2. Watch agents build on Dashboard\n"
            "3. Browse artifacts when complete\n"
            "[dim]Real runs may cost money. CrewAI/LangGraph need OPENROUTER_API_KEY; "
            "Claude Agent SDK needs ANTHROPIC_API_KEY.[/dim]"
        )

    def _load_catalog(self) -> None:
        if not self._api:
            return
        try:
            backends = self._api.backends()
            options = []
            for b in backends:
                label = b.get("label", b.get("name", ""))
                if b.get("configured") is False:
                    label += " (key missing)"
                options.append((label, b.get("name")))
            if options:
                self.query_one("#backend-select", Select).set_options(options)
            profiles = self._api.profiles()
            if profiles:
                first = next(iter(profiles.keys()))
                self.query_one("#team-input", Input).value = first
            registry = self._api.registry_runs()
            proj_opts = [
                (r.get("run_id", "?"), r.get("run_id")) for r in registry if r.get("run_id")
            ]
            if proj_opts:
                self.query_one("#artifact-project-select", Select).set_options(proj_opts)
        except Exception as exc:
            self._log_run_output(f"[red]Catalog error: {exc}[/red]")

    def _init_local_backend_select(self) -> None:
        self.query_one("#backend-select", Select).set_options(
            [
                ("CrewAI", "crewai"),
                ("LangGraph", "langgraph"),
                ("Claude Agent SDK", "claude-agent-sdk"),
            ]
        )
        default = os.environ.get("AI_TEAM_BACKEND", "crewai")
        with contextlib.suppress(Exception):
            self.query_one("#backend-select", Select).value = default

    def action_switch_tab(self, tab_id: str) -> None:
        self.query_one(TabbedContent).active = tab_id

    # -- Run list / dashboard ------------------------------------------------

    def _poll_runs_tick(self) -> None:
        if self.api_connected:
            self._refresh_run_list()

    def _refresh_title_tick(self) -> None:
        run = self._selected_run()
        if run and run.get("status") == "awaiting_human":
            self.title = "⏸ Action needed — AI-Team"
        else:
            self.title = self.TITLE

    def _selected_run(self) -> dict[str, Any] | None:
        if not self._selected_run_id:
            return None
        return next((r for r in self._runs if r.get("run_id") == self._selected_run_id), None)

    def _refresh_run_list(self) -> None:
        if not self._api:
            return
        try:
            self._runs = self._api.list_runs()
        except Exception:
            return
        search = self.query_one("#run-search", Input).value.lower().strip()
        status_filter = str(self.query_one("#run-status-filter", Select).value or "")
        filtered = []
        for run in self._runs:
            if status_filter and run.get("status") != status_filter:
                continue
            if search:
                hay = f"{run.get('description', '')} {run.get('backend', '')} {run.get('run_id', '')}".lower()
                if search not in hay:
                    continue
            filtered.append(run)
        filtered.sort(key=lambda r: r.get("started_at") or "", reverse=True)

        list_view = self.query_one("#run-list", ListView)
        list_view.clear()
        for run in filtered:
            sample = " [sample]" if run.get("is_sample") else ""
            desc = (run.get("description") or "No assignment")[:36]
            label = f"{run.get('status', '?'):<12} {desc}{sample}"
            item = ListItem(Label(label))
            item.run_id = run.get("run_id")  # type: ignore[attr-defined]
            list_view.append(item)

        if not self._selected_run_id and filtered:
            self._select_run(str(filtered[0].get("run_id")))
        elif self._selected_run_id:
            self._load_run_detail(self._selected_run_id)

        self._show_how_it_works(not filtered and not self._selected_run_id)

    @on(ListView.Selected, "#run-list")
    def on_run_selected(self, event: ListView.Selected) -> None:
        item = event.item
        run_id = getattr(item, "run_id", None)
        if run_id:
            self._select_run(str(run_id))

    @on(Input.Changed, "#run-search")
    @on(Select.Changed, "#run-status-filter")
    def on_run_filter_changed(self) -> None:
        self._refresh_run_list()

    def _select_run(self, run_id: str) -> None:
        self._selected_run_id = run_id
        self._load_run_detail(run_id)
        run = self._selected_run()
        if run and run.get("status") in LIVE_STATUSES and not self._watch_worker_active:
            self._watch_run_worker(run_id)

    def _load_run_detail(self, run_id: str) -> None:
        if not self._api:
            return
        try:
            detail = self._api.get_run(run_id)
        except Exception:
            return
        self._selected_monitor = detail.get("monitor")
        self._apply_monitor_dict(self._selected_monitor, detail)
        hitl = detail.get("status") == "awaiting_human"
        banner = self.query_one("#hitl-banner", Static)
        panel = self.query_one("#hitl-panel")
        if hitl:
            banner.update("[bold yellow]⏸ Action needed[/] — this run is paused for human review.")
            panel.remove_class("hidden")
        else:
            banner.update("")
            panel.add_class("hidden")

    def _apply_monitor_dict(self, monitor: dict[str, Any] | None, run: dict[str, Any]) -> None:
        if not monitor:
            return
        phase = str(monitor.get("phase", "intake"))
        self.current_phase = phase
        with contextlib.suppress(Exception):
            self.query_one("#phase-pipeline", PhasePipeline).current_phase = phase

        agents_raw = monitor.get("agents") or {}
        from ai_team.monitor import AgentStatus

        agents = {
            role: AgentStatus(
                role=role,
                status=data.get("status", "idle"),
                current_task=data.get("current_task", ""),
                tasks_completed=data.get("tasks_completed", 0),
                model=data.get("model", ""),
            )
            for role, data in agents_raw.items()
        }
        metrics_raw = monitor.get("metrics") or {}
        from ai_team.monitor import Metrics

        metrics = Metrics(
            tasks_completed=metrics_raw.get("tasks_completed", 0),
            tasks_failed=metrics_raw.get("tasks_failed", 0),
            retries=metrics_raw.get("retries", 0),
            files_generated=metrics_raw.get("files_generated", 0),
            guardrails_passed=metrics_raw.get("guardrails_passed", 0),
            guardrails_failed=metrics_raw.get("guardrails_failed", 0),
            guardrails_warned=metrics_raw.get("guardrails_warned", 0),
            tests_passed=metrics_raw.get("tests_passed", 0),
            tests_failed=metrics_raw.get("tests_failed", 0),
        )
        if monitor.get("elapsed"):
            metrics.start_time = datetime.now()

        from ai_team.monitor import GuardrailEvent, LogEntry

        log_entries = []
        for e in monitor.get("log") or []:
            with contextlib.suppress(Exception):
                log_entries.append(
                    LogEntry(
                        timestamp=datetime.fromisoformat(str(e.get("timestamp"))),
                        agent=e.get("agent", ""),
                        message=e.get("message", ""),
                        level=e.get("level", "info"),
                    )
                )
        gr_events = []
        for e in monitor.get("guardrail_events") or []:
            with contextlib.suppress(Exception):
                gr_events.append(
                    GuardrailEvent(
                        timestamp=datetime.fromisoformat(str(e.get("timestamp"))),
                        category=e.get("category", ""),
                        name=e.get("name", ""),
                        status=e.get("status", "pass"),
                        message=e.get("message", ""),
                    )
                )

        with contextlib.suppress(Exception):
            self.query_one("#agent-timeline", AgentTimeline).update_timeline(
                agents, phase, metrics.retries
            )
            self.query_one("#agent-table", AgentTable).update_agents(agents)
            self.query_one("#metrics-panel", MetricsPanel).update_metrics(metrics)
            self.query_one("#activity-log", ActivityLog).update_log(log_entries)
            self.query_one("#guardrails-log", GuardrailsLog).update_events(gr_events)
            self.query_one("#run-summary", RunSummaryPanel).update_summary(run, monitor)

    @work(thread=True, group="watch")
    def _watch_run_worker(self, run_id: str) -> None:
        if not self._api:
            return
        self._watch_worker_active = True

        def on_msg(msg: dict[str, Any]) -> None:
            if msg.get("type") == "monitor_update":
                data = msg.get("data") or {}
                self._selected_monitor = data
                run = self._selected_run() or {"run_id": run_id}
                self.call_from_thread(self._apply_monitor_dict, data, run)
            elif msg.get("type") == "hitl_required":
                self.call_from_thread(self._load_run_detail, run_id)

        try:
            run_monitor_sync(self._api.ws_base, run_id, on_msg)
        finally:
            self._watch_worker_active = False
            self.call_from_thread(self._refresh_run_list)

    # -- Stop / delete / HITL / retry -----------------------------------------

    def action_stop_selected_run(self) -> None:
        run = self._selected_run()
        if not run or not self._api or run.get("status") not in LIVE_STATUSES:
            return
        try:
            self._api.cancel_run(str(run["run_id"]))
            self.notify(f"Stopping run {run['run_id']}…")
            self._refresh_run_list()
        except Exception as exc:
            self.notify(f"Cancel failed: {exc}", severity="error")

    def action_delete_selected_run(self) -> None:
        run = self._selected_run()
        if not run or not self._api or run.get("status") not in TERMINAL_STATUSES:
            return
        try:
            self._api.delete_run(str(run["run_id"]))
            self.notify(f"Deleted run {run['run_id']}")
            self._selected_run_id = None
            self._refresh_run_list()
        except Exception as exc:
            self.notify(f"Delete failed: {exc}", severity="error")

    @on(Button.Pressed, "#hitl-approve")
    def _hitl_approve(self) -> None:
        self.query_one("#hitl-feedback", TextArea).text = "Approved. Proceed with the plan."

    @on(Button.Pressed, "#hitl-changes")
    def _hitl_changes(self) -> None:
        self.query_one(
            "#hitl-feedback", TextArea
        ).text = "Request changes: please revise before continuing."

    @on(Button.Pressed, "#hitl-reject")
    def _hitl_reject(self) -> None:
        self.query_one("#hitl-feedback", TextArea).text = "Rejected. Stop and report blockers."

    @on(Button.Pressed, "#hitl-submit")
    def _hitl_submit(self) -> None:
        run = self._selected_run()
        if not run or not self._api:
            return
        feedback = self.query_one("#hitl-feedback", TextArea).text.strip()
        if not feedback:
            self.notify("Feedback required", severity="warning")
            return
        try:
            self._api.resume_run(str(run["run_id"]), feedback)
            self.notify("Run resumed")
            self._refresh_run_list()
        except Exception as exc:
            self.notify(f"Resume failed: {exc}", severity="error")

    def action_retry_run(self) -> None:
        run = self._selected_run()
        if not run or run.get("status") not in {"error", "cancelled"}:
            return
        self._prefill_and_start_run(run, auto_start=True)

    def action_edit_rerun(self) -> None:
        run = self._selected_run()
        if not run:
            return
        self._prefill_run_form(run)
        self.action_switch_tab("run")

    def _prefill_run_form(self, run: dict[str, Any]) -> None:
        with contextlib.suppress(Exception):
            self.query_one("#backend-select", Select).value = run.get("backend")
            self.query_one("#team-input", Input).value = run.get("profile", "full")
            self.query_one("#description-area", TextArea).text = run.get("description", "")
            if run.get("complexity"):
                self.query_one("#complexity-select", Select).value = run.get("complexity")

    def _prefill_and_start_run(self, run: dict[str, Any], auto_start: bool = False) -> None:
        self._prefill_run_form(run)
        if auto_start:
            self.action_switch_tab("run")
            self.start_run_via_api()

    # -- Run tab ---------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "run-btn":
            if self.api_connected:
                self.start_run_via_api()
            else:
                self.start_run()
        elif bid == "estimate-btn":
            self.show_estimate()
        elif bid == "demo-btn":
            if self.api_connected:
                self.run_sample_via_api()
            else:
                self.run_demo()
        elif bid == "compare-submit":
            self.start_compare()
        elif bid == "compare-demo":
            self.start_compare_demo()
        elif bid == "compare-estimate":
            self.show_compare_estimate()

    @work(thread=True, exclusive=True, group="api-run")
    def start_run_via_api(self) -> None:
        if not self._api:
            return
        try:
            backend = str(self.query_one("#backend-select", Select).value)
            profile = self.query_one("#team-input", Input).value or "full"
            description = self.query_one("#description-area", TextArea).text.strip()
            complexity = str(self.query_one("#complexity-select", Select).value)
        except Exception:
            return
        if not description:
            self._log_run_output("[red]Please enter a project description.[/red]")
            return

        payload = {
            "backend": backend,
            "profile": profile,
            "description": description,
            "complexity": complexity,
            "estimate_usd": self._last_estimate_usd,
        }

        def on_msg(msg: dict[str, Any]) -> None:
            self._log_run_output(json.dumps(msg, default=str)[:500])
            if msg.get("type") == "run_started":
                rid = msg.get("run_id")
                if rid:
                    self.call_from_thread(self._select_run, str(rid))
                    self.call_from_thread(self.action_switch_tab, "dashboard")

        self._log_run_output(f"[cyan]Starting {backend} via API…[/cyan]")
        try:
            run_start_sync(self._api.ws_base, payload, on_msg)
            self.call_from_thread(self._refresh_run_list)
        except Exception as exc:
            self._log_run_output(f"[red]Run error: {exc}[/red]")

    @work(thread=True, exclusive=True, group="demo")
    def run_sample_via_api(self) -> None:
        if not self._api:
            return
        try:
            result = self._api.start_demo()
            run_id = str(result.get("run_id"))
            self._log_run_output(f"[cyan]Sample run started: {run_id}[/cyan]")
            self.call_from_thread(self._select_run, run_id)
            self.call_from_thread(self.action_switch_tab, "dashboard")
        except Exception as exc:
            self._log_run_output(f"[red]Sample run error: {exc}[/red]")

    @work(thread=True, exclusive=True, group="estimate")
    def show_estimate(self) -> None:
        try:
            complexity = str(self.query_one("#complexity-select", Select).value)
        except Exception:
            complexity = "medium"
        if self.api_connected and self._api:
            try:
                data = self._api.estimate(complexity)
                self._last_estimate_usd = float(data.get("total_usd", 0))
                self._log_run_output(
                    f"[cyan]Estimate ({complexity}): ${self._last_estimate_usd:.4f}[/cyan]"
                )
                return
            except Exception as exc:
                self._log_run_output(f"[red]Estimate error: {exc}[/red]")
                return
        self._estimate_local(complexity)

    def _estimate_local(self, complexity: str) -> None:
        try:
            from ai_team.config.cost_estimator import estimate_run_cost
            from ai_team.config.models import OpenRouterSettings

            settings = OpenRouterSettings()
            rows, total, within_budget = estimate_run_cost(settings, complexity)
            self._last_estimate_usd = total
            lines = [f"[bold cyan]Cost Estimate ({complexity})[/bold cyan]", ""]
            for r in rows:
                lines.append(f"  {r.role:<24} {r.model_id:<30} ${r.cost_usd:.4f}")
            lines.append(f"\n  [bold]Total: ${total:.4f}[/bold]")
            budget_style = "green" if within_budget else "red"
            lines.append(f"  [{budget_style}]Within budget: {within_budget}[/{budget_style}]")
            self._log_run_output("\n".join(lines))
        except Exception as exc:
            self._log_run_output(f"[red]Estimate error: {exc}[/red]")

    # -- Compare ---------------------------------------------------------------

    @work(thread=True, exclusive=True, group="compare")
    def start_compare(self) -> None:
        if not self._api:
            self._log_compare("[red]Start ai-team-web for compare.[/red]")
            return
        description = self.query_one("#compare-description", TextArea).text.strip()
        if not description:
            return
        profile = self.query_one("#compare-profile", Input).value or "full"
        complexity = str(self.query_one("#compare-complexity", Select).value)
        backends = ["crewai", "langgraph", "claude-agent-sdk"]
        logs = {
            "crewai": "compare-crewai-log",
            "langgraph": "compare-lg-log",
            "claude-agent-sdk": "compare-claude-log",
        }
        self._compare_results = {}

        for backend in backends:
            payload = {
                "backend": backend,
                "profile": profile,
                "description": description,
                "complexity": complexity,
            }
            monitor_data: dict[str, Any] = {}

            def make_cb(log_id: str, key: str, snapshot: dict[str, Any] = monitor_data):
                def cb(msg: dict[str, Any]) -> None:
                    if msg.get("type") == "monitor_update":
                        snapshot.update(msg.get("data") or {})
                    self.call_from_thread(self._log_to, log_id, json.dumps(msg, default=str)[:200])

                return cb

            try:
                run_start_sync(self._api.ws_base, payload, make_cb(logs[backend], backend))
                if monitor_data:
                    self._compare_results[backend] = monitor_metric_rows(monitor_data)
            except Exception as exc:
                self.call_from_thread(self._log_to, logs[backend], f"[red]{exc}[/red]")

        self.call_from_thread(self._update_compare_summary)

    @work(thread=True, exclusive=True, group="compare-demo")
    def start_compare_demo(self) -> None:
        if not self._api:
            return
        self._compare_results = {}
        for backend, log_id in [
            ("crewai", "compare-crewai-log"),
            ("langgraph", "compare-lg-log"),
            ("claude-agent-sdk", "compare-claude-log"),
        ]:
            try:
                result = self._api.start_demo()
                run_id = str(result.get("run_id"))
                monitor_data: dict[str, Any] = {}

                def cb(
                    msg: dict[str, Any],
                    _log=log_id,
                    snapshot: dict[str, Any] = monitor_data,
                    demo_run_id: str = run_id,
                ) -> None:
                    if msg.get("type") == "monitor_update":
                        snapshot.update(msg.get("data") or {})
                    self.call_from_thread(
                        self._log_to, _log, f"demo {demo_run_id}: {msg.get('type')}"
                    )

                run_monitor_sync(self._api.ws_base, run_id, cb)
                if monitor_data:
                    self._compare_results[backend] = monitor_metric_rows(monitor_data)
            except Exception as exc:
                self.call_from_thread(self._log_to, log_id, f"[red]{exc}[/red]")
        self.call_from_thread(self._update_compare_summary)

    def _update_compare_summary(self) -> None:
        if not self._compare_results:
            return
        table_data = {
            k: {
                "elapsed": v.get("elapsed"),
                "cost": f"${v['cost_usd']:.4f}" if v.get("cost_usd") is not None else "—",
                "tests": v.get("tests_passed"),
                "retries": v.get("retries"),
            }
            for k, v in self._compare_results.items()
        }
        rows = [
            {"key": k, "label": k, "failed": False, **v} for k, v in self._compare_results.items()
        ]
        verdict = build_compare_verdict(
            rows,
            [
                ("cost", "min", lambda r: float(r.get("cost_usd") or 999999)),
                ("tests passed", "max", lambda r: float(r.get("tests_passed", 0))),
            ],
        )
        self.query_one("#compare-summary", BackendComparisonTable).update_comparison(
            table_data, verdict
        )

    @work(thread=True, exclusive=True, group="compare-est")
    def show_compare_estimate(self) -> None:
        if not self._api:
            return
        complexity = str(self.query_one("#compare-complexity", Select).value)
        try:
            data = self._api.estimate(complexity)
            total = float(data.get("total_usd", 0)) * 3
            self._log_compare(f"[cyan]Compare estimate (×3): ${total:.4f}[/cyan]")
        except Exception as exc:
            self._log_compare(f"[red]{exc}[/red]")

    # -- Artifacts -------------------------------------------------------------

    @on(Select.Changed, "#artifact-project-select")
    def on_artifact_project_changed(self, event: Select.Changed) -> None:
        project_id = str(event.value or "")
        if not project_id or not self._api:
            return
        try:
            tree = self._api.project_tree(project_id)
            files = _flatten_tree(tree)
            lv = self.query_one("#artifact-file-list", ListView)
            lv.clear()
            for label, path in files:
                item = ListItem(Label(label))
                item.file_path = path  # type: ignore[attr-defined]
                lv.append(item)
            tests = self._api.project_tests(project_id)
            arch = self._api.project_architecture(project_id)
            self.query_one("#artifact-tests", Static).update(
                f"Tests: {tests.get('passed', 0)}/{tests.get('total', 0)} passed"
            )
            overview = arch.get("system_overview") or arch.get("markdown_fallback") or ""
            self.query_one("#artifact-architecture", Static).update(str(overview)[:800])
        except Exception as exc:
            self.query_one("#artifact-content", Static).update(f"[red]{exc}[/red]")

    @on(ListView.Selected, "#artifact-file-list")
    def on_artifact_file_selected(self, event: ListView.Selected) -> None:
        path = getattr(event.item, "file_path", None)
        project_id = str(self.query_one("#artifact-project-select", Select).value or "")
        if not path or not project_id or not self._api:
            return
        try:
            content = self._api.project_file(project_id, str(path))
            text = content.get("content") or "(binary or empty)"
            if content.get("truncated"):
                text += "\n… truncated"
            self.query_one("#artifact-content", Static).update(str(text)[:4000])
        except Exception as exc:
            self.query_one("#artifact-content", Static).update(f"[red]{exc}[/red]")

    # -- Local fallback (offline) ----------------------------------------------

    @work(thread=True, exclusive=True, group="run")
    def start_run(self) -> None:
        """Run selected backend locally when API is unavailable."""
        try:
            backend_name = self.query_one("#backend-select", Select).value
            team_name = self.query_one("#team-input", Input).value or "full"
            description = self.query_one("#description-area", TextArea).text
            _complexity = str(self.query_one("#complexity-select", Select).value)
        except Exception:
            return
        if not description.strip():
            self._log_run_output("[red]Please enter a project description.[/red]")
            return
        self.is_running = True
        self._log_run_output(f"[cyan]Starting local {backend_name} run…[/cyan]")
        try:
            from ai_team.backends.registry import get_backend
            from ai_team.core.team_profile import load_team_profile

            profile = load_team_profile(team_name.strip())
            monitor = self._get_or_create_monitor(description[:50])
            monitor.metrics.start_time = datetime.now()
            backend = get_backend(str(backend_name))
            if str(backend_name) == "langgraph":
                from ai_team.backends.langgraph_backend.backend import LangGraphBackend

                if isinstance(backend, LangGraphBackend):
                    for ev in backend.iter_stream_events(
                        description.strip(), profile, monitor=monitor
                    ):
                        self._log_run_output(json.dumps(ev, default=str)[:300])
                        self.call_from_thread(self._refresh_dashboard)
            elif str(backend_name) == "claude-agent-sdk":
                import asyncio

                from ai_team.backends.claude_agent_sdk_backend.backend import ClaudeAgentBackend

                if isinstance(backend, ClaudeAgentBackend):

                    async def _consume() -> None:
                        async for ev in backend.stream(
                            description.strip(), profile, monitor=monitor
                        ):
                            self._log_run_output(json.dumps(ev, default=str)[:300])
                            self.call_from_thread(self._refresh_dashboard)

                    asyncio.run(_consume())
            else:
                result = backend.run(description.strip(), profile, monitor=monitor)
                self._log_run_output(json.dumps(result.model_dump(), default=str)[:500])
            self.call_from_thread(self._refresh_dashboard)
            self._log_run_output("[green]Run complete.[/green]")
        except Exception as exc:
            self._log_run_output(f"[red]Error: {exc}[/red]")
        finally:
            self.is_running = False

    def _get_or_create_monitor(self, project_name: str = "AI-Team Project"):
        from ai_team.monitor import TeamMonitor

        monitor = TeamMonitor(project_name=project_name)
        self._monitor = monitor
        return monitor

    def _refresh_dashboard(self) -> None:
        if not self._monitor:
            return
        m = self._monitor
        with contextlib.suppress(Exception):
            self.query_one("#phase-pipeline", PhasePipeline).current_phase = m.current_phase.value
            self.query_one("#agent-timeline", AgentTimeline).update_timeline(
                m.agents, m.current_phase.value, m.metrics.retries
            )
            self.query_one("#agent-table", AgentTable).update_agents(m.agents)
            self.query_one("#metrics-panel", MetricsPanel).update_metrics(m.metrics)
            self.query_one("#activity-log", ActivityLog).update_log(m.log)
            self.query_one("#guardrails-log", GuardrailsLog).update_events(m.guardrail_events)

    @work(thread=True, exclusive=True, group="demo")
    def run_demo(self) -> None:
        monitor = self._get_or_create_monitor("Demo: Flask REST API")
        monitor.metrics.start_time = datetime.now()
        self.is_running = True
        self._log_run_output("[cyan]Starting local demo simulation…[/cyan]")

        def step(fn, delay: float = 0.5):
            fn()
            self.call_from_thread(self._refresh_dashboard)
            time.sleep(delay)

        try:
            step(lambda: monitor.on_phase_change("intake"), 0.5)
            step(lambda: monitor.on_phase_change("planning"), 0.5)
            step(lambda: monitor.on_agent_start("product_owner", "Requirements", "qwen3"), 0.5)
            step(lambda: monitor.on_agent_finish("product_owner", "Done"), 0.5)
            step(lambda: monitor.on_phase_change("development"), 0.5)
            step(lambda: monitor.on_agent_start("backend_developer", "Coding", "coder"), 0.5)
            step(lambda: monitor.on_file_generated("app.py"), 0.5)
            step(lambda: monitor.on_agent_finish("backend_developer", "Done"), 0.5)
            step(lambda: monitor.on_phase_change("testing"), 0.5)
            step(lambda: monitor.on_retry("qa_engineer", "1 test failed"), 0.5)
            step(lambda: monitor.on_test_result(passed=9, failed=0), 0.5)
            step(lambda: monitor.on_phase_change("complete"), 0.5)
            self._log_run_output("[green]Demo complete![/green]")
        except Exception as exc:
            self._log_run_output(f"[red]Demo error: {exc}[/red]")
        finally:
            self.is_running = False

    # -- Logging helpers -------------------------------------------------------

    def _log_run_output(self, message: str) -> None:
        self._log_to("run-output", message)

    def _log_compare(self, message: str) -> None:
        self._log_to("compare-crewai-log", message)

    def _log_to(self, widget_id: str, message: str) -> None:
        def _write() -> None:
            with contextlib.suppress(Exception):
                self.query_one(f"#{widget_id}", RichLog).write(message)

        self.call_from_thread(_write)


def main() -> None:
    parser = argparse.ArgumentParser(description="AI-Team TUI Dashboard")
    parser.add_argument("--demo", action="store_true", help="Start with simulated demo")
    parser.add_argument(
        "--api-url", default=None, help=f"Web API base URL (default: {DEFAULT_API_BASE})"
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Force offline/local execution (no web API parity)",
    )
    args = parser.parse_args()

    app = AITeamTUI(
        demo_mode=args.demo,
        api_url=args.api_url,
        force_local=args.local,
    )
    app.run()


if __name__ == "__main__":
    main()
